#!/usr/bin/env python3
"""atlas — static-HTML site generator for an OpenDS toolkit run.

Ingests the toolkit's per-tool outputs (sprites from image-extract,
region maps from region-render, dialog from dialog-extract) and
produces a browsable directory of HTML pages. Drops on disk; opens
directly via `file://`; no JavaScript, no external assets.

Usage:

    python3 atlas.py build --games-dir <dir> -o <site-dir>

Auto-detects DS1 vs DS2 by filename presence (DSUN.EXE +
GPLDATA.GFF + RGN??.GFF). Drives the underlying tools as
subprocesses; falls back to skipping a section if the tool isn't
available or fails.

Stdlib-only; no third-party deps.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERSION = (HERE / "VERSION").read_text().strip()
WORKSPACE_ROOT = HERE.parent.parent

# ----- shared HTML chrome -----

CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
       max-width: 1200px; margin: 2em auto; padding: 0 1em; line-height: 1.5;
       color: #1a1a1a; background: #fafafa; }
h1 { border-bottom: 2px solid #333; padding-bottom: 0.3em; }
h2 { margin-top: 2em; border-bottom: 1px solid #ccc; padding-bottom: 0.2em; }
nav { background: #2a4d6e; color: #fafafa; padding: 0.8em 1em; border-radius: 4px;
      margin-bottom: 1em; }
nav a { color: #fafafa; margin-right: 1em; text-decoration: none; font-weight: 600; }
nav a:hover { text-decoration: underline; }
.stat { display: inline-block; margin-right: 1.2em; color: #555; }
.stat strong { color: #1a1a1a; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
        gap: 0.5em; margin: 1em 0; }
.thumb { background: #fff; border: 1px solid #ccc; border-radius: 3px; padding: 0.3em;
         text-align: center; }
.thumb img { max-width: 100%; image-rendering: pixelated; display: block; margin: 0 auto; }
.thumb .label { font-size: 0.75em; color: #555; margin-top: 0.2em;
                font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; }
.region { margin: 1em 0; padding: 1em; background: #fff; border: 1px solid #ddd; }
.region img { max-width: 100%; image-rendering: pixelated; border: 1px solid #bbb; }
.region h3 { margin: 0 0 0.5em 0; }
.note { color: #555; font-style: italic; }
.warn { color: #a04040; background: #fbe7e7; padding: 0.4em 0.6em; border-radius: 3px; }
"""


def chrome_open(title: str, sections: list[tuple[str, str]]) -> str:
    """Page <head> + opening <body> + nav bar. `sections` is
    `[(label, relative_url), ...]` for the top-level nav.
    """
    nav = "".join(f'<a href="{url}">{label}</a>' for label, url in sections)
    return (
        f"<!doctype html>\n"
        f'<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{escape(title)}</title>\n"
        f"<style>{CSS}</style>\n</head>\n<body>\n"
        f"<nav>{nav}</nav>\n"
    )


def chrome_close() -> str:
    return "</body></html>\n"


def escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
    )


# ----- tool discovery (mirrors the umbrella opends crate's pattern) -----

def find_binary(name: str) -> Path | None:
    """target/release/<name> > target/debug/<name> > $PATH."""
    for profile in ("release", "debug"):
        candidate = WORKSPACE_ROOT / "target" / profile / name
        if candidate.is_file():
            return candidate
    path = shutil.which(name)
    return Path(path) if path else None


def find_python_tool(crate_dir: str, script: str) -> Path | None:
    p = WORKSPACE_ROOT / "tools" / crate_dir / script
    return p if p.is_file() else None


# ----- game discovery -----

def discover_games(games_dir: Path) -> list[tuple[str, Path]]:
    """Look for game install directories. Each must contain DSUN.EXE
    and GPLDATA.GFF. Common layouts: `<games_dir>/ds1/`,
    `<games_dir>/ds2/`, or the games_dir itself if it's a single
    install.
    """
    candidates: list[Path] = []
    if (games_dir / "DSUN.EXE").is_file():
        candidates.append(games_dir)
    for child in sorted(games_dir.iterdir()):
        if child.is_dir() and (child / "DSUN.EXE").is_file():
            candidates.append(child)
    out: list[tuple[str, Path]] = []
    for c in candidates:
        label = c.name or "game"
        out.append((label, c))
    return out


# ----- sprite gallery -----

def build_sprite_gallery(
    out_dir: Path,
    game_label: str,
    gff: Path,
    image_extract: Path,
    sections: list[tuple[str, str]],
) -> tuple[Path, int, int]:
    """Run `image-extract --all` against `gff` to produce a flat
    PNG directory, then render one HTML page indexing every
    successfully-decoded sprite. Returns
    `(html_path, sprite_count, skipped_count)`.
    """
    pngs_dir = out_dir / game_label / "sprites" / gff.stem
    pngs_dir.mkdir(parents=True, exist_ok=True)
    res = subprocess.run(
        [str(image_extract), str(gff), "--all", "-o", str(pngs_dir)],
        capture_output=True, text=True,
    )
    written = sorted(p.name for p in pngs_dir.glob("*.png"))
    skipped = 0
    # image-extract prints per-failure warnings to stderr; count
    # them as "skipped" without parsing the message text.
    for line in res.stderr.splitlines():
        if "warn" in line.lower() or "skipped" in line.lower():
            skipped += 1

    html_path = out_dir / game_label / f"sprites-{gff.stem}.html"
    parts = [chrome_open(f"sprites — {game_label} / {gff.name}", sections)]
    parts.append(f"<h1>Sprites: {escape(game_label)} / {escape(gff.name)}</h1>")
    parts.append(
        f'<p><span class="stat">decoded sprites: <strong>{len(written)}</strong></span>'
        f'<span class="stat">skipped: <strong>{skipped}</strong></span></p>'
    )
    if not written:
        parts.append('<p class="warn">No sprites decoded; check that image-extract ran cleanly.</p>')
    else:
        parts.append('<div class="grid">')
        for name in written:
            rel = f"sprites/{gff.stem}/{name}"
            parts.append(
                f'<div class="thumb">'
                f'<a href="{rel}"><img src="{rel}" alt="{escape(name)}"></a>'
                f'<div class="label">{escape(name)}</div>'
                f'</div>'
            )
        parts.append("</div>")
    parts.append(chrome_close())
    html_path.write_text("".join(parts), encoding="utf-8")
    return html_path, len(written), skipped


# ----- region gallery -----

def build_region_gallery(
    out_dir: Path,
    game_label: str,
    rgn_gffs: list[Path],
    region_render: Path,
    sections: list[tuple[str, str]],
) -> tuple[Path, int, int]:
    """Render each RGN*.GFF into a PNG and build an index page."""
    pngs_dir = out_dir / game_label / "regions"
    pngs_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[Path] = []
    failed: list[tuple[str, str]] = []
    for rgn in rgn_gffs:
        out_png = pngs_dir / f"{rgn.stem}.png"
        res = subprocess.run(
            [str(region_render), str(rgn), "-o", str(out_png)],
            capture_output=True, text=True,
        )
        if res.returncode == 0 and out_png.is_file():
            rendered.append(out_png)
        else:
            failed.append((rgn.name, (res.stderr.strip() or res.stdout.strip())[:200]))

    html_path = out_dir / game_label / "regions.html"
    parts = [chrome_open(f"regions — {game_label}", sections)]
    parts.append(f"<h1>Regions: {escape(game_label)}</h1>")
    parts.append(
        f'<p><span class="stat">rendered: <strong>{len(rendered)}</strong></span>'
        f'<span class="stat">failed: <strong>{len(failed)}</strong></span></p>'
    )
    for p in rendered:
        rel = f"regions/{p.name}"
        parts.append(
            f'<div class="region"><h3>{escape(p.stem)}</h3>'
            f'<a href="{rel}"><img src="{rel}" alt="{escape(p.stem)}"></a>'
            f'</div>'
        )
    for name, err in failed:
        parts.append(
            f'<div class="warn">region-render failed on {escape(name)}: <code>{escape(err)}</code></div>'
        )
    parts.append(chrome_close())
    html_path.write_text("".join(parts), encoding="utf-8")
    return html_path, len(rendered), len(failed)


# ----- dialog -----

def build_dialog_page(
    out_dir: Path,
    game_label: str,
    gpldata: Path,
    text_source: Path,
    dialog_extract: Path,
    sections: list[tuple[str, str]],
) -> tuple[Path, bool]:
    """Drive `dialog-extract --format html` and stash the result.
    Wraps in our nav chrome by sandwiching its <body> into ours.
    """
    raw_html_path = out_dir / game_label / "dialog-raw.html"
    raw_html_path.parent.mkdir(parents=True, exist_ok=True)
    res = subprocess.run(
        [
            "python3", str(dialog_extract),
            str(gpldata),
            "--text-source", str(text_source),
            "--format", "html",
            "-o", str(raw_html_path),
        ],
        capture_output=True, text=True,
    )
    if res.returncode != 0 or not raw_html_path.is_file():
        # Drop a stub explaining the failure.
        stub = out_dir / game_label / "dialog.html"
        parts = [chrome_open(f"dialog — {game_label} (FAILED)", sections)]
        parts.append(f"<h1>Dialog: {escape(game_label)}</h1>")
        parts.append(
            f'<p class="warn">dialog-extract failed: <code>{escape((res.stderr or res.stdout)[:400])}</code></p>'
        )
        parts.append(chrome_close())
        stub.write_text("".join(parts), encoding="utf-8")
        return stub, False

    # The raw HTML is already a complete page; we leave it alone
    # and link to it directly from the index. The nav-chrome
    # wrapping pass adds the cross-section nav bar by
    # post-editing the <body> tag.
    body = raw_html_path.read_text(encoding="utf-8")
    nav = "".join(f'<a href="../{url}">{label}</a>' for label, url in sections)
    body = body.replace("<body>", f'<body>\n<nav>{nav}</nav>\n', 1)
    # Inject our shared CSS (after the existing one).
    body = body.replace("</style>", f"</style>\n<style>{CSS}</style>", 1)
    raw_html_path.write_text(body, encoding="utf-8")
    return raw_html_path, True


# ----- index -----

def build_index(
    out_dir: Path,
    game_label: str,
    summary: dict,
    sections: list[tuple[str, str]],
) -> Path:
    """Per-game landing page summarising the sections."""
    html_path = out_dir / game_label / "index.html"
    parts = [chrome_open(f"atlas — {game_label}", sections)]
    parts.append(f"<h1>OpenDS atlas: {escape(game_label)}</h1>")
    parts.append(
        f'<p class="note">Generated by tools/atlas/ v{VERSION}. '
        f"Static HTML; opens via file://; no JavaScript.</p>"
    )
    parts.append("<h2>Sections</h2><ul>")
    if summary.get("sprite_html"):
        s = summary["sprite_html"]
        parts.append(
            f'<li><a href="{Path(s["path"]).name}">Sprites</a>: '
            f'{s["count"]} decoded, {s["skipped"]} skipped (per source GFF).</li>'
        )
    if summary.get("regions"):
        r = summary["regions"]
        parts.append(
            f'<li><a href="regions.html">Regions</a>: {r["count"]} rendered, '
            f'{r["failed"]} failed.</li>'
        )
    if summary.get("dialog"):
        d = summary["dialog"]
        if d["ok"]:
            parts.append(f'<li><a href="{Path(d["path"]).name}">Dialog</a>: '
                         f'every NPC line as a single browsable page.</li>')
        else:
            parts.append(f'<li><a href="{Path(d["path"]).name}">Dialog (failed)</a></li>')
    parts.append("</ul>")
    parts.append(chrome_close())
    html_path.write_text("".join(parts), encoding="utf-8")
    return html_path


def build_root_index(out_dir: Path, games: list[tuple[str, Path]]) -> Path:
    """The single entry-point page linking to every per-game index."""
    nav_sections = [("Home", "index.html")]
    html_path = out_dir / "index.html"
    parts = [chrome_open("OpenDS atlas", nav_sections)]
    parts.append("<h1>OpenDS atlas</h1>")
    parts.append(
        f'<p class="note">Generated by tools/atlas/ v{VERSION}. '
        f"Run <code>atlas build --games-dir DIR -o OUT</code> to rebuild.</p>"
    )
    parts.append("<h2>Games</h2><ul>")
    for label, _ in games:
        parts.append(f'<li><a href="{label}/index.html">{escape(label)}</a></li>')
    parts.append("</ul>")
    parts.append("<h2>About</h2>")
    parts.append("<p>This static site is the umbrella browser for an OpenDS toolkit run. "
                 "Sprites come from <code>image-extract --all</code>; regions from "
                 "<code>region-render</code>; dialog from "
                 "<code>dialog-extract --format html</code>. Every link is local; no network needed.</p>")
    parts.append(chrome_close())
    html_path.write_text("".join(parts), encoding="utf-8")
    return html_path


# ----- driver -----

def cmd_build(args: argparse.Namespace) -> int:
    out_dir: Path = args.output
    games_dir: Path = args.games_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    image_extract = find_binary("image-extract")
    region_render = find_binary("region-render")
    dialog_extract = find_python_tool("dialog-extract", "dialog-extract.py")

    games = discover_games(games_dir)
    if not games:
        print(f"error: no game installs found under {games_dir} "
              "(looking for DSUN.EXE)", file=sys.stderr)
        return 2

    print(f"atlas: building site at {out_dir}")
    print(f"atlas: found {len(games)} game(s): {', '.join(label for label,_ in games)}")
    if image_extract is None:
        print("atlas: WARN image-extract not found; sprites skipped", file=sys.stderr)
    if region_render is None:
        print("atlas: WARN region-render not found; regions skipped", file=sys.stderr)
    if dialog_extract is None:
        print("atlas: WARN dialog-extract.py not found; dialog skipped", file=sys.stderr)

    for label, game_dir in games:
        print(f"atlas: --- {label} ({game_dir}) ---")
        sections = [
            ("Home", "../index.html"),
            ("Game", "index.html"),
            ("Sprites", "sprites-RESOURCE.html"),
            ("Regions", "regions.html"),
            ("Dialog", "dialog-raw.html"),
        ]
        summary: dict = {}

        # Sprites from RESOURCE.GFF (the densest source).
        resource = game_dir / "RESOURCE.GFF"
        if image_extract and resource.is_file():
            print(f"  sprites: extracting {resource.name}...")
            html, count, skipped = build_sprite_gallery(
                out_dir, label, resource, image_extract, sections,
            )
            summary["sprite_html"] = {"path": str(html), "count": count, "skipped": skipped}
            print(f"    -> {count} sprites, {skipped} skipped")

        # Regions: every RGN*.GFF.
        if region_render:
            rgns = sorted(game_dir.glob("RGN*.GFF"))
            if rgns:
                print(f"  regions: rendering {len(rgns)} regions...")
                html, count, failed = build_region_gallery(
                    out_dir, label, rgns, region_render, sections,
                )
                summary["regions"] = {"count": count, "failed": failed}
                print(f"    -> {count} rendered, {failed} failed")

        # Dialog: drive dialog-extract on GPLDATA.GFF.
        gpldata = game_dir / "GPLDATA.GFF"
        if dialog_extract and gpldata.is_file() and resource.is_file():
            print(f"  dialog: extracting {gpldata.name}...")
            html, ok = build_dialog_page(
                out_dir, label, gpldata, resource, dialog_extract, sections,
            )
            summary["dialog"] = {"path": str(html), "ok": ok}
            print(f"    -> {'ok' if ok else 'FAILED'}")

        build_index(out_dir, label, summary, sections)

    build_root_index(out_dir, games)
    print(f"atlas: site ready. open {out_dir / 'index.html'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="atlas", description=__doc__.splitlines()[0])
    p.add_argument("--version", action="version", version=f"atlas {VERSION}")
    sub = p.add_subparsers(dest="cmd", required=True)
    pb = sub.add_parser("build", help="generate the static site")
    pb.add_argument("--games-dir", type=Path, required=True,
                    help="directory containing one or more game installs (DSUN.EXE marker)")
    pb.add_argument("-o", "--output", type=Path, required=True,
                    help="output site directory (created if missing)")
    args = p.parse_args(argv)
    if args.cmd == "build":
        return cmd_build(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
