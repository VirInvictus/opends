//! gpl-disasm: disassembler for SSI's GPL bytecode (Dark Sun).
//!
//! v0.1.0 ships a byte-annotation pass: every byte of a chunk gets
//! a row tagged with libgff's opcode name. We do not yet decode
//! parameter bytes, so instruction boundaries are not aligned with
//! the real program flow (a parameter byte that happens to equal
//! `0x12` will be labelled "gpl jump" by mistake). v0.2.0 will
//! consume each opcode's parameters correctly via a port of
//! libgff's `gpl_read_number` / `gpl_get_parameters`.
//!
//! The opcode catalogue is sourced from libgff's `gpl_commands`
//! table in `dsoageofheroes/libgff` (`src/gpl/parse.c`,
//! MIT-licensed; see `OPCODES` below for the entries).

use std::fmt;

/// Embedded opcode catalogue. Index = opcode byte (0x00..=0x80).
/// Sourced verbatim from libgff's `gpl_commands` table at
/// `dsoageofheroes/libgff` `src/gpl/parse.c` lines 1554-1684.
/// MIT-licensed; attribution intentional.
///
/// Bytes 0x81..=0xFF are not part of libgff's table; we treat them
/// as unknown.
pub const OPCODES: &[&str] = &[
    "gpl zero",              // 0x00
    "gpl long divide equal", // 0x01
    "gpl byte dec",          // 0x02
    "gpl word dec",          // 0x03
    "gpl long dec",          // 0x04
    "gpl byte inc",          // 0x05
    "gpl word inc",          // 0x06
    "gpl long inc",          // 0x07
    "gpl hunt",              // 0x08
    "gpl getxy",             // 0x09
    "gpl string copy",       // 0x0A
    "gpl p damage",          // 0x0B
    "gpl changemoney",       // 0x0C
    "gpl setvar",            // 0x0D
    "gpl toggle accum",      // 0x0E
    "gpl getstatus",         // 0x0F
    "gpl getlos",            // 0x10
    "gpl long times equal",  // 0x11
    "gpl jump",              // 0x12
    "gpl local sub",         // 0x13
    "gpl global sub",        // 0x14
    "gpl local ret",         // 0x15
    "gpl load variable",     // 0x16
    "gpl compare",           // 0x17
    "gpl load accum",        // 0x18
    "gpl global ret",        // 0x19
    "gpl nextto",            // 0x1A
    "gpl inlostrigger",      // 0x1B
    "gpl notinlostrigger",   // 0x1C
    "gpl clear los",         // 0x1D
    "gpl nametonum",         // 0x1E
    "gpl numtoname",         // 0x1F
    "gpl bitsnoop",          // 0x20
    "gpl award",             // 0x21
    "gpl request",           // 0x22
    "gpl source trace",      // 0x23
    "gpl shop",              // 0x24
    "gpl clone",             // 0x25
    "gpl default",           // 0x26
    "gpl ifcompare",         // 0x27
    "gpl trace var",         // 0x28
    "gpl orelse",            // 0x29
    "gpl clearpic",          // 0x2A
    "gpl continue",          // 0x2B
    "gpl log",               // 0x2C
    "gpl damage",            // 0x2D
    "gpl source line num",   // 0x2E
    "gpl drop",              // 0x2F
    "gpl passtime",          // 0x30
    "gpl exit gpl",          // 0x31
    "gpl fetch",             // 0x32
    "gpl search",            // 0x33
    "gpl getparty",          // 0x34
    "gpl fight",             // 0x35
    "gpl flee",              // 0x36
    "gpl follow",            // 0x37
    "gpl getyn",             // 0x38
    "gpl give",              // 0x39
    "gpl go",                // 0x3A
    "gpl input bignum",      // 0x3B
    "gpl goxy",              // 0x3C
    "gpl readorders",        // 0x3D
    "gpl if",                // 0x3E
    "gpl else",              // 0x3F
    "gpl setrecord",         // 0x40
    "gpl setother",          // 0x41
    "gpl input string",      // 0x42
    "gpl input number",      // 0x43
    "gpl input money",       // 0x44
    "gpl joinparty",         // 0x45
    "gpl leaveparty",        // 0x46
    "gpl lockdoor",          // 0x47
    "gpl menu",              // 0x48
    "gpl setthing",          // 0x49
    "gpl default",           // 0x4A
    "gpl local sub trace",   // 0x4B
    "gpl default",           // 0x4C
    "gpl default",           // 0x4D
    "gpl default",           // 0x4E
    "gpl print string",      // 0x4F
    "gpl print number",      // 0x50
    "gpl printnl",           // 0x51
    "gpl rand",              // 0x52
    "gpl default",           // 0x53
    "gpl showpic",           // 0x54
    "gpl default",           // 0x55
    "gpl default",           // 0x56
    "gpl default",           // 0x57
    "gpl skillroll",         // 0x58
    "gpl statroll",          // 0x59
    "gpl string compare",    // 0x5A
    "gpl match string",      // 0x5B
    "gpl take",              // 0x5C
    "gpl sound",             // 0x5D
    "gpl tport",             // 0x5E
    "gpl music",             // 0x5F
    "gpl default",           // 0x60
    "gpl cmpend",            // 0x61
    "gpl wait",              // 0x62
    "gpl while",             // 0x63
    "gpl wend",              // 0x64
    "gpl attacktrigger",     // 0x65
    "gpl looktrigger",       // 0x66
    "gpl endif",             // 0x67
    "gpl move tiletrigger",  // 0x68
    "gpl door tiletrigger",  // 0x69
    "gpl move boxtrigger",   // 0x6A
    "gpl door boxtrigger",   // 0x6B
    "gpl pickup itemtrigger", // 0x6C
    "gpl usetrigger",        // 0x6D
    "gpl talktotrigger",     // 0x6E
    "gpl noorderstrigger",   // 0x6F
    "gpl usewithtrigger",    // 0x70
    "gpl default",           // 0x71
    "gpl default",           // 0x72
    "gpl default",           // 0x73
    "gpl default",           // 0x74
    "gpl default",           // 0x75
    "gpl byte plus equal",   // 0x76
    "gpl byte minus equal",  // 0x77
    "gpl byte times equal",  // 0x78
    "gpl byte divide equal", // 0x79
    "gpl word plus equal",   // 0x7A
    "gpl word minus equal",  // 0x7B
    "gpl word times equal",  // 0x7C
    "gpl word divide equal", // 0x7D
    "gpl long plus equal",   // 0x7E
    "gpl long minus equal",  // 0x7F
    "gpl get range",         // 0x80
];

/// Highest opcode byte known to libgff (`0x80`). Bytes above this
/// are emitted as `db 0xNN ; ??` by [`disassemble`].
pub const MAX_KNOWN_OPCODE: u8 = 0x80;

/// Look up an opcode byte's libgff name.
pub fn opcode_name(byte: u8) -> Option<&'static str> {
    if (byte as usize) < OPCODES.len() {
        Some(OPCODES[byte as usize])
    } else {
        None
    }
}

/// One row of disassembler output. Always corresponds to a single
/// byte in the input in v0.1.0.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Annotation {
    /// Byte offset in the chunk (0-based).
    pub offset: usize,
    /// The byte itself.
    pub byte: u8,
    /// libgff opcode name, or `None` for bytes above `MAX_KNOWN_OPCODE`.
    pub mnemonic: Option<&'static str>,
    /// If this byte starts an ASCII run of `min_string_len` or
    /// more printable bytes (including this one and the bytes
    /// after), the run is captured here and inlined as a comment.
    /// Only the byte at the start of the run carries this; later
    /// bytes in the same run have `string_run: None` to avoid
    /// duplicate annotations.
    pub string_run: Option<String>,
}

impl fmt::Display for Annotation {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let m = self.mnemonic.unwrap_or("db");
        write!(f, "{:04x}  {:02x}  {:<22}", self.offset, self.byte, m)?;
        if self.mnemonic.is_none() {
            write!(f, "  ; ??")?;
        }
        if let Some(ref s) = self.string_run {
            // Escape internal control bytes for safer display.
            let escaped: String = s
                .chars()
                .map(|c| match c {
                    '\r' => "\\r".to_string(),
                    '\n' => "\\n".to_string(),
                    '\t' => "\\t".to_string(),
                    '"' => "\\\"".to_string(),
                    c if c.is_ascii_graphic() || c == ' ' => c.to_string(),
                    c => format!("\\x{:02x}", c as u8),
                })
                .collect();
            write!(f, "  ; \"{}\"", escaped)?;
        }
        Ok(())
    }
}

/// Threshold for the inline ASCII-run detector. Runs shorter than
/// this are not annotated.
pub const MIN_STRING_LEN: usize = 4;

/// Disassemble a GPL chunk's bytes into a sequence of one
/// [`Annotation`] per input byte. v0.1.0 makes no attempt to
/// consume opcode parameters; every byte gets a row.
pub fn disassemble(bytes: &[u8]) -> Vec<Annotation> {
    let runs = find_string_runs(bytes, MIN_STRING_LEN);
    let run_starts: std::collections::HashMap<usize, String> = runs
        .into_iter()
        .map(|(start, s)| (start, s))
        .collect();

    bytes
        .iter()
        .enumerate()
        .map(|(offset, &byte)| Annotation {
            offset,
            byte,
            mnemonic: opcode_name(byte),
            string_run: run_starts.get(&offset).cloned(),
        })
        .collect()
}

/// Find ASCII printable runs of length >= `min_len`. Returns a
/// vector of `(start_offset, string)` tuples. A byte is considered
/// printable if it is in `0x20..=0x7E` or one of `\t \n \r`.
fn find_string_runs(bytes: &[u8], min_len: usize) -> Vec<(usize, String)> {
    let mut runs = Vec::new();
    let mut start: Option<usize> = None;
    for (i, &b) in bytes.iter().enumerate() {
        if is_printable(b) {
            start.get_or_insert(i);
        } else if let Some(s) = start.take() {
            if i - s >= min_len {
                runs.push((s, String::from_utf8_lossy(&bytes[s..i]).into_owned()));
            }
        }
    }
    if let Some(s) = start {
        if bytes.len() - s >= min_len {
            runs.push((s, String::from_utf8_lossy(&bytes[s..]).into_owned()));
        }
    }
    runs
}

#[inline]
fn is_printable(b: u8) -> bool {
    (0x20..=0x7E).contains(&b) || matches!(b, b'\t' | b'\n' | b'\r')
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn opcodes_table_covers_0x00_through_0x80() {
        assert_eq!(OPCODES.len(), 0x81);
        assert_eq!(opcode_name(0x00), Some("gpl zero"));
        assert_eq!(opcode_name(0x12), Some("gpl jump"));
        assert_eq!(opcode_name(0x3E), Some("gpl if"));
        assert_eq!(opcode_name(0x67), Some("gpl endif"));
        assert_eq!(opcode_name(0x80), Some("gpl get range"));
        assert_eq!(opcode_name(0x81), None);
        assert_eq!(opcode_name(0xFF), None);
    }

    #[test]
    fn disassembles_each_byte_to_one_annotation() {
        let anns = disassemble(&[0x00, 0x12, 0x67, 0xFF]);
        assert_eq!(anns.len(), 4);
        assert_eq!(anns[0].mnemonic, Some("gpl zero"));
        assert_eq!(anns[1].mnemonic, Some("gpl jump"));
        assert_eq!(anns[2].mnemonic, Some("gpl endif"));
        assert_eq!(anns[3].mnemonic, None);
    }

    #[test]
    fn detects_ascii_string_runs() {
        // Embed a string mid-stream.
        let mut bytes = vec![0x12, 0x00];
        bytes.extend_from_slice(b"Garn");
        bytes.push(0xFF);
        let anns = disassemble(&bytes);
        // The run starts at offset 2 ("G") and is 4 bytes long.
        assert_eq!(anns[2].string_run.as_deref(), Some("Garn"));
        // Bytes inside the run after the start carry no annotation.
        assert_eq!(anns[3].string_run, None);
        assert_eq!(anns[4].string_run, None);
        assert_eq!(anns[5].string_run, None);
    }

    #[test]
    fn ignores_short_ascii_runs() {
        // Only 3 printable bytes in a row; below MIN_STRING_LEN.
        let anns = disassemble(&[0x12, b'h', b'i', b'!', 0xFF]);
        assert!(anns.iter().all(|a| a.string_run.is_none()));
    }

    #[test]
    fn annotation_display_format() {
        let ann = Annotation {
            offset: 0x10,
            byte: 0x12,
            mnemonic: Some("gpl jump"),
            string_run: None,
        };
        assert_eq!(format!("{ann}"), "0010  12  gpl jump              ");
    }

    #[test]
    fn unknown_byte_displays_with_dd_hex_and_query() {
        let ann = Annotation {
            offset: 0,
            byte: 0xFF,
            mnemonic: None,
            string_run: None,
        };
        assert_eq!(format!("{ann}"), "0000  ff  db                      ; ??");
    }
}
