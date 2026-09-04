# RE Tooling (host)

Host reverse-engineering tooling for `DSUN.EXE`. Not a repo
dependency: nothing under `tools/` imports any of it, and the
stdlib-only rule for the Python tools is unaffected. Moved here
from `dsun-exe-re.md` 8 (2026-09-04) so the behavioural doc stays
about the binary.

Installed 2026-08-08.

| Tool | Where | What it is for here |
|---|---|---|
| **Ghidra 12.1.2** | `~/.local/share/ghidra_12.1.2_PUBLIC` | Static analysis and decompilation of `DSUN.EXE`. The heavy tool `dsun-exe-re.md` has always named as "when r2 stalls". |
| Temurin **JDK 21** | `~/.local/share/jdk/jdk-21.0.12+8` | Ghidra requires JDK 21; Fedora 44 ships only 25/26. Pinned via `JAVA_HOME_OVERRIDE` so the system JDK is untouched. |
| `pwntools` 4.15 | uv tool, Python 3.13 | `pwn asm` / `pwn disasm` at `arch='i386', bits=16` for authoring patch bytes. Not used for exploitation here. |

## Ghidra against these binaries: read this before importing

Three things are specific to a Borland-overlaid real-mode target
and will waste a pass if assumed wrong.

1. **Do not install an LE/LX loader extension.** The obvious
   search result for "Ghidra + DOS game" is `ghidra-lx-loader`, for
   the LX/LE linear-executable format. That is the DOS/4GW format
   `dsun-exe-re.md` 1 disproved. It cannot load these binaries and
   its presence would only re-suggest the wrong mental model.
   Ghidra loads plain MZ and `x86:LE:16:Real Mode` natively, which
   is what is needed.
2. **The MZ loader already selects `x86:LE:16:Real Mode`.** So an
   MZ import needs no manual language choice. A raw-binary import
   does, and the failure mode is convincing nonsense, not an error
   (the same class of bug as the Capstone `CS_MODE_32` trap in
   `dsun-exe-re.md` 6).
3. **Ghidra does not understand Borland overlays.** A plain import
   leaves the overlay area as undifferentiated bytes. The fix is
   `ovr-map` (Phase 5.5): its JSON carries each segment's base,
   file range and entry stubs, which a Ghidra script replays as
   overlay memory blocks with all 935 (DS1) / 854 (DS2) entry
   points labelled. The headless pipeline (Phase 5.6.0):

   ```sh
   # 1. Generate the Java scripts from ovr-map. The generated files
   #    must live in a dot-free directory: Ghidra resolves bare
   #    -postScript names against $PWD first, and any path element
   #    starting with '.' (e.g. the .gitrepos checkout) is rejected
   #    as a script source location.
   mkdir -p /tmp/ovrscripts
   python3 tools/ovr-map/ovr-map.py .games/ds1/DSUN.EXE --ghidra -o /tmp/ovrscripts/OvrMap.java
   python3 tools/ovr-map/ovr-map.py .games/ds1/DSUN.EXE        --ghidra-rename tools/ovr-map/syms/ds1.toml -o /tmp/ovrscripts/OvrRename.java

   # 2. Run analyzeHeadless. Project location must also be dot-free.
   #    Pass -postScript as absolute dot-free paths (see note 1).
   rm -rf /tmp/ghidra_proj && mkdir -p /tmp/ghidra_proj
   ~/.local/share/ghidra_12.1.2_PUBLIC/support/analyzeHeadless \
       /tmp/ghidra_proj ds1_proj \
       -import .games/ds1/DSUN.EXE \
       -scriptPath /tmp/ovrscripts \
       -postScript /tmp/ovrscripts/OvrMap.java \
       -postScript /tmp/ovrscripts/OvrRename.java \
       -postScript "$PWD/tools/ovr-map/ghidra/OvrExport.java" \
                  /abs/path/scratch/ghidra_project/export/ds1-functions.txt \
       -overwrite
   ```

   The three post-scripts: `OvrMap.java` creates one overlay memory
   block per segment at its correct base and labels every entry
   stub; `OvrRename.java` (generated from the curated catalogue,
   `--ghidra-rename`) creates named functions with confidence and
   evidence comments; `OvrExport.java` (checked in at
   `tools/ovr-map/ghidra/`) writes the final function list as TSV.
   Re-prove status 2026-09-04: import, analysis and project
   persistence re-proven (project kept under `scratch/
   ghidra_project/`); script execution is currently blocked by a
   host-level Ghidra OSGi breakage, below.

Temper expectations on the decompiler: Ghidra's output is much
weaker on 16-bit segmented code than on 32/64-bit. Far pointers
and overlay thunks decompile badly. It still beats reading bytes
by eye, but it will not hand over clean C.

## Troubleshooting: "Failed to get OSGi bundle containing script"

Ghidra compiles Java scripts through its Felix/OSGi layer, and
that layer broke on this host between 2026-08-29 (last successful
compile; the bundle cache has the artifacts) and 2026-09-04.
Symptoms: every script, including a trivial do-nothing one, fails
with `ClassNotFoundException: Failed to get OSGi bundle`; the
per-script directory under
`~/.config/ghidra/ghidra_12.1.2_PUBLIC/osgi/compiled-bundles/` is
created empty; no javac diagnostic is logged anywhere. The script
source is not the problem: compiling the same file by hand with
the pinned JDK produces no errors:

```sh
CP=$(fd -g '*.jar' ~/.local/share/ghidra_12.1.2_PUBLIC/Ghidra | tr '\n' ':')
~/.local/share/jdk/jdk-21.0.12+8/bin/javac -cp "$CP" -d /tmp/ovrtest /tmp/ovrscripts/OvrMap.java
```

That manual compile is also the standing syntax check for
generated scripts while the OSGi layer is broken (cache nuking
was tried; it did not help). Until the layer is fixed, the
Ghidra-side function list cannot be re-exported;
`scripts/propose-exe-symbols.py --census` is the ndisasm-based
stand-in for a function-level worklist.

## Not applicable

`pwndbg` is installed on this machine for CTF work. It is a gdb
plugin for live Linux ELF processes and does nothing for this
project: the binaries run under DOSBox, and the debugger for that
is DOSBox's own, already driven over IPC by `opcode-fuzz` (Phase
5). Recorded here so it is not mistaken for opends tooling.
