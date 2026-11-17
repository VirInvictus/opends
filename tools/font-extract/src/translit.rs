//! GPL transliteration: display-character to game-glyph mapping for
//! fan translations (ported from `TimQuester/DarkSunTools`
//! `Common/Gpl/GplTransliteration.cs`, Apache-2.0).
//!
//! GPL strings are 7-bit, so a Russian translation typed in Cyrillic
//! is stored as the ASCII glyph codes whose bitmaps the FONT
//! resource replaced. Rules are authored in display order
//! (`From` = game glyph, `To` = what that glyph shows on screen);
//! encoding walks the reverse map. Only 1:1 rules apply: a
//! multi-character replacement would change the string length, and
//! GPL string spans are fixed-length.

use std::collections::HashMap;

/// One rule: `from` is the game's glyph code (ASCII), `to` is the
/// character that glyph displays.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Rule {
    pub from: char,
    pub to: char,
}

#[derive(Debug, thiserror::Error)]
pub enum RulesError {
    #[error("translit rule {line}: malformed pair {pair:?} (expected From=To, 1:1 chars only)")]
    Malformed { line: usize, pair: String },
}

/// Parse the rules-file format upstream commits
/// (`A=А;a=а;B=Б;...`, semicolon-separated `From=To` pairs; a
/// `0xNN=char` pair names the glyph by hex byte; `#` starts a
/// comment line). Multi-character pairs are refused rather than
/// silently skipped: upstream's encoder skips them, but a rules
/// file that contains any is one the caller should know about.
pub fn parse_rules(text: &str) -> Result<Vec<Rule>, RulesError> {
    let mut rules = Vec::new();
    for (idx, raw_line) in text.lines().enumerate() {
        let line_no = idx + 1;
        let line = raw_line.trim_start_matches('\u{feff}').trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        for pair in line.split(';') {
            let pair = pair.trim();
            if pair.is_empty() {
                continue;
            }
            let (from, to) = pair.split_once('=').ok_or(RulesError::Malformed {
                line: line_no,
                pair: pair.to_string(),
            })?;
            let from = parse_char(from).ok_or(RulesError::Malformed {
                line: line_no,
                pair: pair.to_string(),
            })?;
            let mut to_chars = to.chars();
            let (to, extra) = (to_chars.next(), to_chars.next());
            if extra.is_some() {
                return Err(RulesError::Malformed {
                    line: line_no,
                    pair: pair.to_string(),
                });
            }
            let to = to.ok_or(RulesError::Malformed {
                line: line_no,
                pair: pair.to_string(),
            })?;
            rules.push(Rule { from, to });
        }
    }
    Ok(rules)
}

/// `0xNN` names a glyph byte; anything else is the literal
/// character.
fn parse_char(text: &str) -> Option<char> {
    if let Some(hex) = text.strip_prefix("0x").or_else(|| text.strip_prefix("0X")) {
        let byte = u8::from_str_radix(hex, 16).ok()?;
        Some(byte as char)
    } else {
        let mut chars = text.chars();
        let (c, extra) = (chars.next(), chars.next());
        if extra.is_none() { c } else { None }
    }
}

fn display_to_game(rules: &[Rule]) -> HashMap<char, char> {
    let mut map = HashMap::new();
    for rule in rules {
        // Identity pairs are skipped so encoding never "rewrites" a
        // glyph onto itself; upstream does the same.
        if rule.from != rule.to {
            map.insert(rule.to, rule.from);
        }
    }
    map
}

fn game_to_display(rules: &[Rule]) -> HashMap<char, char> {
    let mut map = HashMap::new();
    for rule in rules {
        if rule.from != rule.to {
            map.insert(rule.from, rule.to);
        }
    }
    map
}

/// Map display characters back to game glyph codes. Characters not
/// covered by a rule are left untouched; non-7-bit leftovers are
/// reported by the string encoder when the text is packed.
pub fn encode_to_game_charset(input: &str, rules: &[Rule]) -> String {
    if rules.is_empty() {
        return input.to_string();
    }
    let map = display_to_game(rules);
    if map.is_empty() {
        return input.to_string();
    }
    input
        .chars()
        .map(|c| map.get(&c).copied().unwrap_or(c))
        .collect()
}

/// Map game glyph codes to the characters they display. Useful for
/// previews; translation editing uses [`encode_to_game_charset`].
pub fn decode_to_display(input: &str, rules: &[Rule]) -> String {
    if rules.is_empty() {
        return input.to_string();
    }
    let map = game_to_display(rules);
    if map.is_empty() {
        return input.to_string();
    }
    input
        .chars()
        .map(|c| map.get(&c).copied().unwrap_or(c))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    const SAMPLE: &str = "A=А;a=а;X=Ц;%=Щ";

    #[test]
    fn parse_round_trip_shapes() {
        let rules = parse_rules(SAMPLE).expect("parse");
        assert_eq!(rules.len(), 4);
        assert_eq!(
            rules[0],
            Rule {
                from: 'A', to: 'А'
            }
        );
        assert_eq!(
            rules[3],
            Rule {
                from: '%', to: 'Щ'
            }
        );
    }

    #[test]
    fn hex_glyph_names_parse() {
        let rules = parse_rules("0xC2=@;0x41=А").expect("parse");
        assert_eq!(rules[0].from, 0xC2 as char);
        assert_eq!(rules[1].from, 'A');
    }

    #[test]
    fn encode_maps_display_to_game() {
        let rules = parse_rules(SAMPLE).unwrap();
        assert_eq!(encode_to_game_charset("ЦАЩ", &rules), "XA%");
    }

    #[test]
    fn decode_maps_game_to_display() {
        let rules = parse_rules(SAMPLE).unwrap();
        assert_eq!(decode_to_display("XA%", &rules), "ЦАЩ");
    }

    #[test]
    fn uncovered_characters_pass_through() {
        let rules = parse_rules(SAMPLE).unwrap();
        assert_eq!(encode_to_game_charset("ЦA z", &rules), "XA z");
    }

    #[test]
    fn identity_pairs_are_skipped() {
        let rules = parse_rules("A=A;B=Б").unwrap();
        // A=A is identity (glyph A displays A): encoding display
        // text maps Б back to glyph B and leaves A alone.
        assert_eq!(encode_to_game_charset("AБ", &rules), "AB");
    }

    #[test]
    fn multi_char_rules_are_refused() {
        assert!(parse_rules("AB=Щ").is_err());
        assert!(parse_rules("A=ЮЯ").is_err());
    }

    #[test]
    fn comments_and_bom_are_ignored() {
        let text = "# a comment\n\u{feff}A=А\n";
        let rules = parse_rules(text).expect("parse");
        assert_eq!(rules.len(), 1);
    }
}
