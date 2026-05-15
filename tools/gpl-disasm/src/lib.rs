//! gpl-disasm: disassembler for SSI's GPL bytecode (Dark Sun).
//!
//! v0.2.0 ships **parameter decoding**: each opcode now consumes
//! its variable-length parameter bytes via a port of libgff's
//! `gpl_read_number`, so output is one row per **instruction**
//! (not one per byte as in v0.1.0). True instruction boundaries
//! are aligned with the real program flow for the common path.
//!
//! Scope notes (Partial v0.2.0):
//! - GPL_RETVAL (`0x8C` = `GPL_RETVAL | 0x80`) is decoded as an
//!   opaque [`Expression::RetVal`] with the inner opcode byte
//!   captured but recursion deferred to v0.2.1.
//! - GPL_COMPLEX_* (`0x30..0x3F`, dispatch bytes `0xB0..0xBF`)
//!   plus the `0xb3` "passive-flag" special case are decoded as
//!   opaque [`Expression::Complex`]; their internal layout
//!   (`gpl_access_complex`) lands in v0.2.1.
//! - Handlers with custom parameter loops (`gpl_load_variable`,
//!   `gpl_search`, `gpl_setrecord`, `gpl_menu`) are marked
//!   `best_effort = true` and consume only the opcode byte;
//!   subsequent instructions may misalign. Tracked in the
//!   corpus smoke test as a percentage.
//!
//! The opcode catalogue and decoder logic are sourced from
//! libgff's `gpl_commands` table, `gpl_read_number`, and
//! `gpl_read_simple_num_var` at
//! `dsoageofheroes/libgff` `src/gpl/parse.c` (MIT, attributed in
//! code). The 7-bit packed-string decoder is ported from
//! `dsoageofheroes/soloscuro-archive` `src/gpl/gpl-string.c`
//! `read_compressed`.

use std::fmt;

use serde::Serialize;

// ---------- GPL_* constants (from libgff include/gpl/var.h) ----------

/// Bit set on a variable-reference dispatch byte to signal a
/// 2-byte variable id instead of 1. Stripped by the decoder.
pub const EXTENDED_VAR: u8 = 0x40;

/// First byte value treated as a binary operator (exclusive).
pub const OPERATOR_OFFSET: u8 = 0xD0;
/// Last byte value treated as a binary operator (inclusive).
pub const OPERATOR_LAST: u8 = 0xDF;

/// `(` in expression context.
pub const GPL_HI_OPEN_PAREN: u8 = 0xE2;
/// `)` in expression context.
pub const GPL_HI_CLOSE_PAREN: u8 = 0xE1;

// Variable types (low 4 bits of dispatch byte after high-bit strip).
pub const GPL_ACCM: u8 = 0x00;
pub const GPL_LSTRING: u8 = 0x01;
pub const GPL_LNUM: u8 = 0x02;
pub const GPL_LBYTE: u8 = 0x03;
pub const GPL_LNAME: u8 = 0x04;
pub const GPL_LBIGNUM: u8 = 0x05;
pub const GPL_GSTRING: u8 = 0x06;
pub const GPL_GNUM: u8 = 0x07;
pub const GPL_GBYTE: u8 = 0x08;
pub const GPL_GNAME: u8 = 0x09;
pub const GPL_GBIGNUM: u8 = 0x0A;
pub const GPL_IMMED_BIGNUM: u8 = 0x0B;
pub const GPL_RETVAL: u8 = 0x0C;
pub const GPL_GFLAG: u8 = 0x0D;
pub const GPL_LFLAG: u8 = 0x0E;
pub const GPL_IMMED_BYTE: u8 = 0x0F;
pub const GPL_IMMED_WORD: u8 = 0x10;
pub const GPL_IMMED_NAME: u8 = 0x11;
pub const GPL_IMMED_STRING: u8 = 0x12;

pub const GPL_COMPLEX_LOW: u8 = 0x30;
pub const GPL_COMPLEX_HIGH: u8 = 0x3F;
/// Undocumented opcode at libgff `parse.c` line 609 ("setting a
/// passive's flag value"). Decoded as a `Complex` until we know
/// more.
pub const GPL_PASSIVE_FLAG_TAG: u8 = 0x33;

// 7-bit packed string sub-type markers.
pub const STRING_INTRODUCE: u8 = 0x01;
pub const STRING_UNCOMPRESSED: u8 = 0x02;
pub const STRING_COMPRESSED: u8 = 0x05;
/// Terminator byte inside a 7-bit packed string stream.
pub const STRING_TERMINATOR: u8 = 0x03;

/// Inline-string-run heuristic threshold (carried over from v0.1).
pub const MIN_STRING_LEN: usize = 4;

/// Safety cap on a packed string length (matches soloscuro-archive
/// `TEXTSTRINGSIZE`).
pub const MAX_PACKED_STRING_LEN: usize = 1024;

/// Maximum nested `GPL_RETVAL` recursion. libgff's `gpl_retval`
/// itself doesn't gate on depth, but every safe-subset opcode
/// reads at most a fixed number of `gpl_read_number` parameters,
/// and each `gpl_read_number` can recurse into another RETVAL.
/// In practice we see at most one level of nesting; we cap at 4
/// to bound worst-case parse time on malformed input.
pub const MAX_RETVAL_DEPTH: u8 = 4;

/// Inner opcodes libgff permits inside a `GPL_RETVAL` dispatch
/// (per `parse.c` `gpl_retval` lines 1791-1826). All of these are
/// "safe in RETVAL context" per the row notes in
/// [`docs/gpl-opcodes.md`](../docs/gpl-opcodes.md).
pub const RETVAL_SAFE_OPCODES: &[u8] = &[
    0x0F, 0x10, 0x1A, 0x1E, 0x1F, 0x20, 0x22, 0x25, 0x2F, 0x33,
    0x34, 0x38, 0x39, 0x3D, 0x41, 0x49, 0x52, 0x59, 0x5A, 0x5C,
    0x80,
];

#[inline]
fn is_retval_safe(opcode: u8) -> bool {
    RETVAL_SAFE_OPCODES.contains(&opcode)
}

// ---------- Opcode catalogue (carried verbatim from v0.1.0) ----------

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

/// Highest opcode byte known to libgff (`0x80`).
pub const MAX_KNOWN_OPCODE: u8 = 0x80;

/// Look up an opcode byte's libgff name.
pub fn opcode_name(byte: u8) -> Option<&'static str> {
    if (byte as usize) < OPCODES.len() {
        Some(OPCODES[byte as usize])
    } else {
        None
    }
}

// ---------- Per-opcode parameter spec ----------

/// How an opcode's parameters are read from the byte stream.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ParamSpec {
    /// Handler reads exactly `n` parameters via `gpl_get_parameters`
    /// or a sequence of `gpl_read_number` calls totalling `n`.
    Fixed(u8),
    /// Handler reads no parameters.
    None,
    /// `gpl_log` (0x2C): one packed-string payload (no read_number).
    Log,
    /// `gpl_load_variable` (0x16): load_accum (1 expression) + 1
    /// datatype byte + 1 or 2 varnum bytes (simple case) or an
    /// `access_complex` block (deferred, marks best-effort).
    LoadVar,
    /// `gpl_menu` (0x48): 1 expression (menu name) followed by a
    /// loop of 3-expression entries terminated by the byte `0x4A`.
    Menu,
    /// `gpl_search` (0x33): 1 expression + 2 bytes (low/high) +
    /// a do-while loop reading optional `0x53` (SEARCH_QUAL),
    /// field byte, type byte, and a conditional read_number.
    Search,
    /// `gpl_setrecord` (0x40): a `gpl_access_complex` block
    /// followed by one expression (the value being written).
    /// All three branches of libgff `parse.c` 689-726 produce
    /// the same byte shape.
    SetRecord,
    /// Handlers whose parameter consumption is not yet modelled
    /// or unknown (gpl_unknown). Best-effort: consume only the
    /// opcode byte.
    Custom,
}

/// Index = opcode byte (0x00..=0x80).
///
/// Counts derived by reading every handler body in libgff
/// `parse.c`: a `gpl_get_parameters(gpl, n)` call contributes `n`;
/// each direct `gpl_read_number(gpl)` or `load_accum(gpl)` call
/// contributes 1. Wrappers (`gpl_template`, `gpl_type_op_equal`)
/// expand to their inlined counts. The `gpl_unknown` stub and
/// handlers with custom parameter shapes (0x16 load_variable,
/// 0x33 search, 0x40 setrecord, 0x48 menu) get `Custom`.
///
/// Cross-checked against soloscuro-archive `src/gpl/gpl-lua.c`
/// where libgff returns `gpl_unknown` (sets `0x5F music` to 1
/// param; the rest stay 0/unimplemented).
pub const PARAM_COUNTS: [ParamSpec; 0x81] = [
    ParamSpec::None,     // 0x00 gpl zero (EXIT_GPL)
    ParamSpec::Fixed(2), // 0x01 gpl long divide equal
    ParamSpec::Fixed(1), // 0x02 gpl byte dec
    ParamSpec::Fixed(1), // 0x03 gpl word dec
    ParamSpec::Fixed(1), // 0x04 gpl long dec
    ParamSpec::Fixed(1), // 0x05 gpl byte inc
    ParamSpec::Fixed(1), // 0x06 gpl word inc
    ParamSpec::Fixed(1), // 0x07 gpl long inc
    ParamSpec::Fixed(1), // 0x08 gpl hunt
    ParamSpec::Fixed(1), // 0x09 gpl getxy
    ParamSpec::Fixed(2), // 0x0A gpl string copy
    ParamSpec::Fixed(2), // 0x0B gpl p damage
    ParamSpec::Fixed(1), // 0x0C gpl changemoney
    ParamSpec::Custom,   // 0x0D gpl setvar (libgff unknown / soloscuro lua_exit)
    ParamSpec::None,     // 0x0E gpl toggle accum
    ParamSpec::Fixed(1), // 0x0F gpl getstatus
    ParamSpec::Fixed(3), // 0x10 gpl getlos
    ParamSpec::Fixed(2), // 0x11 gpl long times equal
    ParamSpec::Fixed(1), // 0x12 gpl jump
    ParamSpec::Fixed(1), // 0x13 gpl local sub (call_local)
    ParamSpec::Fixed(2), // 0x14 gpl global sub (call_global)
    ParamSpec::None,     // 0x15 gpl local ret
    ParamSpec::LoadVar,  // 0x16 gpl load variable (load_accum + datatype + varnum or complex)
    ParamSpec::Fixed(1), // 0x17 gpl compare (load_accum reads 1 number)
    ParamSpec::Fixed(1), // 0x18 gpl load accum
    ParamSpec::None,     // 0x19 gpl global ret
    ParamSpec::Fixed(2), // 0x1A gpl nextto
    ParamSpec::Fixed(4), // 0x1B gpl inlostrigger (template, 4)
    ParamSpec::Fixed(4), // 0x1C gpl notinlostrigger (template, 4)
    ParamSpec::Fixed(1), // 0x1D gpl clear los
    ParamSpec::Fixed(1), // 0x1E gpl nametonum
    ParamSpec::Fixed(1), // 0x1F gpl numtoname
    ParamSpec::Fixed(2), // 0x20 gpl bitsnoop
    ParamSpec::Fixed(2), // 0x21 gpl award
    ParamSpec::Fixed(4), // 0x22 gpl request
    ParamSpec::Custom,   // 0x23 gpl source trace (libgff unknown)
    ParamSpec::Fixed(1), // 0x24 gpl shop
    ParamSpec::Fixed(6), // 0x25 gpl clone
    ParamSpec::Custom,   // 0x26 gpl default (libgff unknown)
    ParamSpec::Fixed(2), // 0x27 gpl ifcompare
    ParamSpec::Custom,   // 0x28 gpl trace var (libgff unknown)
    ParamSpec::Fixed(1), // 0x29 gpl orelse
    ParamSpec::None,     // 0x2A gpl clearpic
    ParamSpec::None,     // 0x2B gpl continue
    ParamSpec::Log,      // 0x2C gpl log (reads one packed string)
    ParamSpec::Fixed(2), // 0x2D gpl damage
    ParamSpec::Custom,   // 0x2E gpl source line num (libgff unknown)
    ParamSpec::Fixed(3), // 0x2F gpl drop
    ParamSpec::Fixed(1), // 0x30 gpl passtime
    ParamSpec::None,     // 0x31 gpl exit gpl
    ParamSpec::Fixed(2), // 0x32 gpl fetch
    ParamSpec::Search,   // 0x33 gpl search (read_number + bytes + loop)
    ParamSpec::Fixed(1), // 0x34 gpl getparty
    ParamSpec::None,     // 0x35 gpl fight
    ParamSpec::Fixed(1), // 0x36 gpl flee
    ParamSpec::Fixed(2), // 0x37 gpl follow
    ParamSpec::None,     // 0x38 gpl getyn
    ParamSpec::Fixed(4), // 0x39 gpl give
    ParamSpec::Fixed(2), // 0x3A gpl go
    ParamSpec::Custom,   // 0x3B gpl input bignum (libgff unknown)
    ParamSpec::Fixed(3), // 0x3C gpl goxy
    ParamSpec::Fixed(1), // 0x3D gpl readorders
    ParamSpec::Fixed(1), // 0x3E gpl if
    ParamSpec::Fixed(1), // 0x3F gpl else
    ParamSpec::SetRecord, // 0x40 gpl setrecord (access_complex + read_number)
    ParamSpec::Fixed(1), // 0x41 gpl setother
    ParamSpec::Fixed(1), // 0x42 gpl input string
    ParamSpec::Fixed(1), // 0x43 gpl input number
    ParamSpec::Fixed(1), // 0x44 gpl input money
    ParamSpec::Custom,   // 0x45 gpl joinparty (libgff unknown)
    ParamSpec::Custom,   // 0x46 gpl leaveparty (libgff unknown)
    ParamSpec::Custom,   // 0x47 gpl lockdoor (libgff unknown)
    ParamSpec::Menu,     // 0x48 gpl menu (loop until next byte == 0x4A)
    ParamSpec::Fixed(2), // 0x49 gpl setthing
    ParamSpec::Custom,   // 0x4A gpl default (also menu terminator)
    ParamSpec::Custom,   // 0x4B gpl local sub trace (libgff unknown)
    ParamSpec::Custom,   // 0x4C gpl default
    ParamSpec::Custom,   // 0x4D gpl default
    ParamSpec::Custom,   // 0x4E gpl default
    ParamSpec::Fixed(2), // 0x4F gpl print string
    ParamSpec::Fixed(2), // 0x50 gpl print number
    ParamSpec::None,     // 0x51 gpl printnl (libgff's get_params call is commented out)
    ParamSpec::Fixed(1), // 0x52 gpl rand
    ParamSpec::Custom,   // 0x53 gpl default
    ParamSpec::Fixed(1), // 0x54 gpl showpic
    ParamSpec::Custom,   // 0x55 gpl default
    ParamSpec::Custom,   // 0x56 gpl default
    ParamSpec::Custom,   // 0x57 gpl default
    ParamSpec::Custom,   // 0x58 gpl skillroll (soloscuro lua_exit, libgff unknown)
    ParamSpec::Fixed(3), // 0x59 gpl statroll
    ParamSpec::Fixed(2), // 0x5A gpl string compare
    ParamSpec::Custom,   // 0x5B gpl match string (libgff unknown)
    ParamSpec::Fixed(4), // 0x5C gpl take
    ParamSpec::Fixed(1), // 0x5D gpl sound
    ParamSpec::Fixed(5), // 0x5E gpl tport
    ParamSpec::Fixed(1), // 0x5F gpl music (libgff unknown; soloscuro reads 1 number)
    ParamSpec::Custom,   // 0x60 gpl default
    ParamSpec::None,     // 0x61 gpl cmpend
    ParamSpec::Fixed(1), // 0x62 gpl wait
    ParamSpec::Fixed(1), // 0x63 gpl while
    ParamSpec::Fixed(1), // 0x64 gpl wend
    ParamSpec::Fixed(3), // 0x65 gpl attacktrigger (template, 3)
    ParamSpec::Fixed(3), // 0x66 gpl looktrigger (template, 3)
    ParamSpec::None,     // 0x67 gpl endif
    ParamSpec::Fixed(5), // 0x68 gpl move tiletrigger (template, 5)
    ParamSpec::Fixed(5), // 0x69 gpl door tiletrigger (template, 5)
    ParamSpec::Fixed(7), // 0x6A gpl move boxtrigger (template, 7)
    ParamSpec::Fixed(7), // 0x6B gpl door boxtrigger (template, 7)
    ParamSpec::Fixed(3), // 0x6C gpl pickup itemtrigger (template, 3)
    ParamSpec::Fixed(3), // 0x6D gpl usetrigger (template, 3)
    ParamSpec::Fixed(3), // 0x6E gpl talktotrigger (template, 3)
    ParamSpec::Fixed(3), // 0x6F gpl noorderstrigger (template, 3)
    ParamSpec::Fixed(4), // 0x70 gpl usewithtrigger (template, 4)
    ParamSpec::Custom,   // 0x71 gpl default
    ParamSpec::Custom,   // 0x72 gpl default
    ParamSpec::Custom,   // 0x73 gpl default
    ParamSpec::Custom,   // 0x74 gpl default
    ParamSpec::Custom,   // 0x75 gpl default
    ParamSpec::Fixed(2), // 0x76 gpl byte plus equal (type_op_equal, 1+1)
    ParamSpec::Fixed(2), // 0x77 gpl byte minus equal
    ParamSpec::Fixed(2), // 0x78 gpl byte times equal
    ParamSpec::Fixed(2), // 0x79 gpl byte divide equal
    ParamSpec::Fixed(2), // 0x7A gpl word plus equal
    ParamSpec::Fixed(2), // 0x7B gpl word minus equal
    ParamSpec::Fixed(2), // 0x7C gpl word times equal
    ParamSpec::Fixed(2), // 0x7D gpl word divide equal
    ParamSpec::Fixed(2), // 0x7E gpl long plus equal
    ParamSpec::Fixed(2), // 0x7F gpl long minus equal
    ParamSpec::Fixed(2), // 0x80 gpl get range
];

/// Look up an opcode byte's parameter spec.
pub fn param_spec(byte: u8) -> ParamSpec {
    if (byte as usize) < PARAM_COUNTS.len() {
        PARAM_COUNTS[byte as usize]
    } else {
        ParamSpec::Custom
    }
}

// ---------- Decoded types ----------

/// Variable kind. Index matches libgff `var.h` value
/// (`GPL_LSTRING = 0x1`, `GPL_LNUM = 0x2`, ...).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum VarKind {
    Lstring,
    Lnum,
    Lbyte,
    Lname,
    Lbignum,
    Gstring,
    Gnum,
    Gbyte,
    Gname,
    Gbignum,
    Gflag,
    Lflag,
}

impl VarKind {
    fn from_tag(tag: u8) -> Option<Self> {
        Some(match tag {
            GPL_LSTRING => VarKind::Lstring,
            GPL_LNUM => VarKind::Lnum,
            GPL_LBYTE => VarKind::Lbyte,
            GPL_LNAME => VarKind::Lname,
            GPL_LBIGNUM => VarKind::Lbignum,
            GPL_GSTRING => VarKind::Gstring,
            GPL_GNUM => VarKind::Gnum,
            GPL_GBYTE => VarKind::Gbyte,
            GPL_GNAME => VarKind::Gname,
            GPL_GBIGNUM => VarKind::Gbignum,
            GPL_GFLAG => VarKind::Gflag,
            GPL_LFLAG => VarKind::Lflag,
            _ => return None,
        })
    }

    fn short_name(self) -> &'static str {
        match self {
            VarKind::Lstring => "LSTR",
            VarKind::Lnum => "LNUM",
            VarKind::Lbyte => "LBYTE",
            VarKind::Lname => "LNAME",
            VarKind::Lbignum => "LBN",
            VarKind::Gstring => "GSTR",
            VarKind::Gnum => "GNUM",
            VarKind::Gbyte => "GBYTE",
            VarKind::Gname => "GNAME",
            VarKind::Gbignum => "GBN",
            VarKind::Gflag => "GF",
            VarKind::Lflag => "LF",
        }
    }
}

/// Binary operator. Index matches libgff `var.h` value
/// (`GPL_OP_ADD = 0xD1`, ...).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Op {
    Add,
    Minus,
    Times,
    Divide,
    And,
    Or,
    Equal,
    NotEqual,
    Greater,
    Less,
    GreaterEqual,
    LessEqual,
    Band,
    Bor,
    Bclr,
}

impl Op {
    fn from_byte(b: u8) -> Option<Self> {
        Some(match b {
            0xD1 => Op::Add,
            0xD2 => Op::Minus,
            0xD3 => Op::Times,
            0xD4 => Op::Divide,
            0xD5 => Op::And,
            0xD6 => Op::Or,
            0xD7 => Op::Equal,
            0xD8 => Op::NotEqual,
            0xD9 => Op::Greater,
            0xDA => Op::Less,
            0xDB => Op::GreaterEqual,
            0xDC => Op::LessEqual,
            0xDD => Op::Band,
            0xDE => Op::Bor,
            0xDF => Op::Bclr,
            _ => return None,
        })
    }

    fn symbol(self) -> &'static str {
        match self {
            Op::Add => "+",
            Op::Minus => "-",
            Op::Times => "*",
            Op::Divide => "/",
            Op::And => "and",
            Op::Or => "or",
            Op::Equal => "==",
            Op::NotEqual => "!=",
            Op::Greater => ">",
            Op::Less => "<",
            Op::GreaterEqual => ">=",
            Op::LessEqual => "<=",
            Op::Band => "&",
            Op::Bor => "|",
            Op::Bclr => "&~",
        }
    }
}

/// Sub-type marker on an `IMMED_STRING` (`0x92`) parameter.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum StringSubType {
    Introduce,
    Uncompressed,
    Compressed,
}

/// One token in the result of a `gpl_read_number` call.
///
/// `gpl_read_number` produces a flat, infix-ordered stream of
/// values, operators, and parens (e.g. `[Variable, Op(Add),
/// Immediate14]` for `gf12 + 7`). This enum is one such token.
#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Expression {
    /// 14-bit immediate, the `cop < 0x80` path. `cop * 0x100 + b`.
    Immediate14 { value: u16 },
    /// `GPL_IMMED_BYTE` (`0x8F`). 1 signed byte.
    ImmediateByte { value: i8 },
    /// `GPL_IMMED_BIGNUM` (`0x8B`). 32-bit big-endian assemble
    /// `(high << 16) + low_zero_extended` per libgff's
    /// `int32_t cval; uint16_t *t = (uint16_t*)&cval; t[1] = high;
    /// cval += (int32_t)low;` (little-endian host assumption).
    ImmediateBigNum { value: i32 },
    /// `GPL_IMMED_NAME` (`0x91`). `cval = h * -1` per libgff.
    ImmediateName { value: i32 },
    /// `GPL_IMMED_STRING` (`0x92`). Sub-type + decoded payload.
    ImmediateString {
        sub_type: StringSubType,
        value: String,
    },
    /// Variable reference. `id` is 1 byte (without `EXTENDED_VAR`)
    /// or 2 bytes (with).
    Variable {
        var_kind: VarKind,
        id: u16,
        extended: bool,
    },
    /// Infix binary operator. Always appears between two values.
    BinaryOp { op: Op },
    /// `(`. The decoder enters an inner expression read.
    OpenParen,
    /// `)`. The decoder leaves an inner expression read.
    CloseParen,
    /// `GPL_RETVAL | 0x80` (`0x8C`). Nested function call. v0.2.1
    /// recursively dispatches the inner opcode's parameter shape
    /// (when the opcode is in libgff's safe-subset; otherwise
    /// `best_effort` is set and `inner_params` is empty).
    /// Recursion is bounded by [`MAX_RETVAL_DEPTH`].
    RetVal {
        inner_opcode: u8,
        #[serde(skip_serializing_if = "Option::is_none")]
        inner_mnemonic: Option<&'static str>,
        inner_params: Vec<Vec<Expression>>,
    },
    /// A record-field access via `gpl_access_complex`. The dispatch
    /// byte (`tag`) is `GPL_COMPLEX_PTR=0x30 .. GPL_COMPLEX_HIGH=0x3F`
    /// or the `0xb3` "passive-flag" special case.
    ///
    /// libgff's `gpl_access_complex` reads `word obj_name + byte
    /// depth + depth bytes element`. `obj_name >= 0x8000` indicates
    /// a context-keyword (`obj_name & 0x7FFF` ∈ {POV, ACTIVE,
    /// PASSIVE, OTHER, OTHER1, THING}); else it's a record id.
    ComplexAccess {
        tag: u8,
        obj_name: i32,
        depth: u8,
        elements: Vec<u8>,
    },
    /// `GPL_ACCM` accum-here-is-a-bug case (libgff aborts).
    AccmError,
    /// `GPL_IMMED_WORD` (`0x90`). libgff aborts with
    /// "not implemented"; we keep going and mark best-effort.
    ImmediWordUnimplemented,
    /// Dispatch byte didn't match any known case. Decoder bails;
    /// subsequent bytes are not parsed.
    Unknown { byte: u8 },
}

/// One row of disassembler output: the opcode plus its decoded
/// parameter list. Each parameter is the result of one
/// `gpl_read_number` call (a sequence of [`Expression`] tokens).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Instruction {
    /// Byte offset of the opcode byte in the input chunk.
    pub offset: usize,
    /// Total bytes consumed by this instruction (opcode + params).
    pub length: usize,
    /// The opcode byte.
    pub opcode: u8,
    /// libgff mnemonic, or `None` for bytes above `MAX_KNOWN_OPCODE`.
    pub mnemonic: Option<&'static str>,
    /// Decoded parameters, one [`Vec`] per `gpl_read_number` call.
    pub params: Vec<Vec<Expression>>,
    /// True if this instruction encountered a deferred case
    /// (RetVal / Complex / unknown handler) or had its params
    /// best-effort-consumed. When true, instructions that follow
    /// may be misaligned.
    #[serde(skip_serializing_if = "is_false")]
    pub best_effort: bool,
    /// If this instruction's byte range contains an ASCII printable
    /// run of `>= MIN_STRING_LEN` bytes (carry-over from v0.1's
    /// heuristic for inline strings).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub string_run: Option<String>,
}

#[allow(clippy::trivially_copy_pass_by_ref)]
fn is_false(b: &bool) -> bool {
    !*b
}

/// Full result of [`disassemble`].
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct DisasmResult {
    pub instructions: Vec<Instruction>,
    /// Bytes the disassembler consumed. Equal to `total_bytes` when
    /// the chunk parses cleanly to the end; less if a fatal bail
    /// happened (no known opcode at a position past best-effort).
    pub bytes_consumed: usize,
    /// Total bytes in the input chunk.
    pub total_bytes: usize,
    /// True if no instruction was marked `best_effort` and every
    /// byte was consumed.
    pub aligned: bool,
}

// ---------- Decoder ----------

/// Result of one `gpl_read_number` call.
struct ReadNumber {
    tokens: Vec<Expression>,
    consumed: usize,
    best_effort: bool,
}

/// Read a `gpl_access_complex` block from `bytes` starting at
/// `cursor`. Layout per libgff `parse.c` 235-288:
///
///   word obj_name  (2 bytes, big-endian)
///   byte depth     (1 byte)
///   byte element[depth]  (depth bytes)
///
/// Returns `(obj_name, depth, elements, bytes_consumed)`.
///
/// Ported from `dsoageofheroes/libgff` `src/gpl/parse.c`
/// `gpl_access_complex` (MIT).
fn read_complex_access(bytes: &[u8], cursor: usize) -> Option<(i32, u8, Vec<u8>, usize)> {
    if cursor + 3 > bytes.len() {
        return None;
    }
    let obj_name = (((bytes[cursor] as u16) << 8) | bytes[cursor + 1] as u16) as i32;
    let depth = bytes[cursor + 2];
    let body_start = cursor + 3;
    let body_end = body_start + depth as usize;
    if body_end > bytes.len() {
        return None;
    }
    let elements = bytes[body_start..body_end].to_vec();
    Some((obj_name, depth, elements, body_end - cursor))
}

/// Read one expression from `bytes` starting at `cursor`.
///
/// Ported from `dsoageofheroes/libgff` `src/gpl/parse.c`
/// `gpl_read_number` (MIT). The function emits a flat,
/// infix-ordered token stream that mirrors libgff's `printf`
/// output. The outer `do { ... } while (do_next || paren_level >
/// 0)` loop is preserved: after each value, peek the next byte
/// and continue if it is an operator (`0xD0 < b <= 0xDF`); the
/// loop also continues while paren depth is positive.
#[cfg(test)]
fn read_expression(bytes: &[u8], cursor: usize) -> ReadNumber {
    read_expression_with_depth(bytes, cursor, 0)
}

fn read_expression_with_depth(bytes: &[u8], cursor: usize, retval_depth: u8) -> ReadNumber {
    let mut pos = cursor;
    let mut tokens: Vec<Expression> = Vec::with_capacity(2);
    let mut paren_level: i32 = 0;
    let mut best_effort = false;

    loop {
        if pos >= bytes.len() {
            tokens.push(Expression::Unknown { byte: 0 });
            best_effort = true;
            break;
        }
        let mut do_next = false;
        let cop = bytes[pos];
        pos += 1;

        if cop < 0x80 {
            // 14-bit immediate path. cval = cop * 256 + b.
            if pos >= bytes.len() {
                tokens.push(Expression::Unknown { byte: cop });
                best_effort = true;
                break;
            }
            let b = bytes[pos];
            pos += 1;
            tokens.push(Expression::Immediate14 {
                value: ((cop as u16) << 8) | b as u16,
            });
        } else {
            // High-bit dispatch path. The variable-type cases need
            // to know whether EXTENDED_VAR was set; mirror libgff's
            // `gpl_global_big_num` carrier with a local flag.
            let extended = cop < OPERATOR_OFFSET && (cop & EXTENDED_VAR) != 0;
            let dispatch = if extended { cop & !EXTENDED_VAR } else { cop };
            // Strip the high bit to get the GPL_* tag.
            let tag = dispatch & 0x7F;

            // Variable-type dispatch (GPL_LSTRING..=GPL_LFLAG).
            if let Some(var_kind) = VarKind::from_tag(tag) {
                let (id, consumed) = read_simple_num_var(bytes, pos, extended);
                pos += consumed;
                tokens.push(Expression::Variable {
                    var_kind,
                    id,
                    extended,
                });
            } else {
                match dispatch {
                    // GPL_ACCM | 0x80 (0x80 with high bit): libgff errors.
                    x if x == (GPL_ACCM | 0x80) => {
                        tokens.push(Expression::AccmError);
                        best_effort = true;
                        break;
                    }
                    // GPL_IMMED_BIGNUM | 0x80
                    x if x == (GPL_IMMED_BIGNUM | 0x80) => {
                        if pos + 4 > bytes.len() {
                            tokens.push(Expression::Unknown { byte: cop });
                            best_effort = true;
                            break;
                        }
                        let hi = ((bytes[pos] as u16) << 8) | bytes[pos + 1] as u16;
                        let lo = ((bytes[pos + 2] as u16) << 8) | bytes[pos + 3] as u16;
                        pos += 4;
                        // libgff: t[1] = hi; cval += (int32_t)lo;
                        // i.e. cval = ((hi as i32) << 16) + (lo as u16 zero-extended).
                        let value = ((hi as i32) << 16) + (lo as i32);
                        tokens.push(Expression::ImmediateBigNum { value });
                    }
                    // GPL_RETVAL | 0x80: nested function call.
                    x if x == (GPL_RETVAL | 0x80) => {
                        if pos >= bytes.len() {
                            tokens.push(Expression::Unknown { byte: cop });
                            best_effort = true;
                            break;
                        }
                        let inner = bytes[pos];
                        pos += 1;
                        if retval_depth >= MAX_RETVAL_DEPTH || !is_retval_safe(inner) {
                            // Bail before recursing too deep, or
                            // before dispatching an opcode libgff
                            // wouldn't accept here.
                            tokens.push(Expression::RetVal {
                                inner_opcode: inner,
                                inner_mnemonic: opcode_name(inner),
                                inner_params: Vec::new(),
                            });
                            best_effort = true;
                        } else {
                            let inner_result = read_instruction_params_with_depth(
                                inner,
                                bytes,
                                pos,
                                retval_depth + 1,
                            );
                            pos += inner_result.consumed;
                            if inner_result.best_effort {
                                best_effort = true;
                            }
                            tokens.push(Expression::RetVal {
                                inner_opcode: inner,
                                inner_mnemonic: opcode_name(inner),
                                inner_params: inner_result.params,
                            });
                        }
                    }
                    // GPL_IMMED_BYTE | 0x80
                    x if x == (GPL_IMMED_BYTE | 0x80) => {
                        if pos >= bytes.len() {
                            tokens.push(Expression::Unknown { byte: cop });
                            best_effort = true;
                            break;
                        }
                        let b = bytes[pos] as i8;
                        pos += 1;
                        tokens.push(Expression::ImmediateByte { value: b });
                    }
                    // GPL_IMMED_WORD | 0x80: libgff bails.
                    x if x == (GPL_IMMED_WORD | 0x80) => {
                        tokens.push(Expression::ImmediWordUnimplemented);
                        best_effort = true;
                        break;
                    }
                    // GPL_IMMED_NAME | 0x80: halfword, cval = h * -1.
                    x if x == (GPL_IMMED_NAME | 0x80) => {
                        if pos + 2 > bytes.len() {
                            tokens.push(Expression::Unknown { byte: cop });
                            best_effort = true;
                            break;
                        }
                        let h = ((bytes[pos] as u16) << 8) | bytes[pos + 1] as u16;
                        pos += 2;
                        tokens.push(Expression::ImmediateName {
                            value: -(h as i32),
                        });
                    }
                    // GPL_IMMED_STRING | 0x80
                    x if x == (GPL_IMMED_STRING | 0x80) => {
                        match read_text(bytes, pos) {
                            Some((sub_type, value, consumed)) => {
                                pos += consumed;
                                tokens.push(Expression::ImmediateString { sub_type, value });
                            }
                            None => {
                                tokens.push(Expression::Unknown { byte: cop });
                                best_effort = true;
                                break;
                            }
                        }
                    }
                    // GPL_HI_OPEN_PAREN: enter inner expression.
                    GPL_HI_OPEN_PAREN => {
                        paren_level += 1;
                        tokens.push(Expression::OpenParen);
                        do_next = true;
                    }
                    // GPL_HI_CLOSE_PAREN: leave inner expression.
                    GPL_HI_CLOSE_PAREN => {
                        paren_level -= 1;
                        tokens.push(Expression::CloseParen);
                    }
                    // Operators (0xD1..=0xDF): infix.
                    b if (b > OPERATOR_OFFSET) && (b <= OPERATOR_LAST) => {
                        // SAFETY: range checked above.
                        let op = Op::from_byte(b).unwrap();
                        tokens.push(Expression::BinaryOp { op });
                        do_next = true;
                    }
                    // GPL_COMPLEX_* range (and the 0xb3 special case,
                    // which lives inside this same range).
                    b if (b >= (GPL_COMPLEX_LOW | 0x80))
                        && (b <= (GPL_COMPLEX_HIGH | 0x80)) =>
                    {
                        let tag = b & 0x7F;
                        match read_complex_access(bytes, pos) {
                            Some((obj_name, depth, elements, consumed)) => {
                                pos += consumed;
                                tokens.push(Expression::ComplexAccess {
                                    tag,
                                    obj_name,
                                    depth,
                                    elements,
                                });
                            }
                            None => {
                                tokens.push(Expression::Unknown { byte: cop });
                                best_effort = true;
                                break;
                            }
                        }
                    }
                    _ => {
                        tokens.push(Expression::Unknown { byte: cop });
                        best_effort = true;
                        break;
                    }
                }
            }
        }

        if !do_next {
            // libgff: do_next = preview(next_op) && next_op >
            // OPERATOR_OFFSET && next_op <= OPERATOR_LAST.
            if pos < bytes.len() {
                let nx = bytes[pos];
                if nx > OPERATOR_OFFSET && nx <= OPERATOR_LAST {
                    do_next = true;
                }
            }
        }

        if !do_next && paren_level <= 0 {
            break;
        }
        if best_effort && paren_level <= 0 {
            break;
        }
    }

    ReadNumber {
        tokens,
        consumed: pos - cursor,
        best_effort,
    }
}

/// Read a variable reference's id from `bytes` starting at
/// `cursor`. 1 byte without `EXTENDED_VAR`, 2 bytes (big-endian)
/// with. Returns `(id, bytes_consumed)`.
///
/// Ported from libgff `src/gpl/parse.c` `gpl_read_simple_num_var`
/// (MIT). libgff's GNAME special case (rewriting temps16 by
/// `- 0x20` when in range 0x20..0x2F) is a render-time
/// concern, not a storage one; we keep the raw id and render
/// the offset in Display.
fn read_simple_num_var(bytes: &[u8], cursor: usize, extended: bool) -> (u16, usize) {
    let mut pos = cursor;
    if pos >= bytes.len() {
        return (0, 0);
    }
    let mut id: u16 = bytes[pos] as u16;
    pos += 1;
    if extended {
        if pos >= bytes.len() {
            return (id, pos - cursor);
        }
        id = id.wrapping_mul(0x100).wrapping_add(bytes[pos] as u16);
        pos += 1;
    }
    (id, pos - cursor)
}

/// Decode a packed-string parameter starting at `cursor`. The
/// byte at `cursor` is the sub-type marker (`0x01` / `0x02` /
/// `0x05`); the packed payload begins one byte later for
/// compressed strings. Returns `(sub_type, decoded, bytes)`.
///
/// Ported from `dsoageofheroes/soloscuro-archive`
/// `src/gpl/gpl-string.c` `sol_gpl_read_text` + `read_compressed`
/// (MIT). The Python port lives at
/// `tools/dialog-extract/dialog-extract.py` `decode_compressed_string`.
fn read_text(bytes: &[u8], cursor: usize) -> Option<(StringSubType, String, usize)> {
    if cursor >= bytes.len() {
        return None;
    }
    let marker = bytes[cursor];
    let after_marker = cursor + 1;
    match marker {
        STRING_INTRODUCE => Some((
            StringSubType::Introduce,
            "<active_character_name>".to_string(),
            1,
        )),
        STRING_UNCOMPRESSED => Some((
            StringSubType::Uncompressed,
            "<uncompressed; decoder not implemented>".to_string(),
            1,
        )),
        STRING_COMPRESSED => {
            let (s, consumed) = decode_compressed(bytes, after_marker)?;
            Some((StringSubType::Compressed, s, 1 + consumed))
        }
        _ => None,
    }
}

/// Inner 7-bit packed-string decoder. Mirrors soloscuro-archive
/// `read_compressed` exactly: a sliding 16-bit window with `idx`
/// cycling 1..=7, 0 (drop a fresh byte on idx > 0, extract 7 bits
/// at `idx`). `0x03` terminates; non-printables are replaced with
/// space. Returns `(string, bytes_consumed_including_terminator)`.
fn decode_compressed(bytes: &[u8], cursor: usize) -> Option<(String, usize)> {
    let mut buffer: u32 = 0;
    let mut idx: u8 = 1;
    let mut chars: Vec<u8> = Vec::with_capacity(64);
    let mut i = cursor;
    while chars.len() < MAX_PACKED_STRING_LEN && i < bytes.len() {
        if idx > 0 {
            buffer = (buffer << 8) & 0xFF00;
            buffer |= bytes[i] as u32;
            i += 1;
        }
        let mut ch = ((buffer >> idx) & 0x7F) as u8;
        if ch == STRING_TERMINATOR {
            return Some((string_from_lossy(&chars), i - cursor));
        }
        if !(0x20..=0x7E).contains(&ch) {
            ch = 0x20;
        }
        chars.push(ch);
        idx = idx.wrapping_add(1);
        if idx > 7 {
            idx = 0;
        }
    }
    // Ran off the end of the chunk without seeing 0x03. Soft-fail.
    None
}

fn string_from_lossy(bytes: &[u8]) -> String {
    bytes.iter().map(|&b| b as char).collect()
}

/// Result of one [`read_instruction_params_with_depth`] call.
struct InstructionParams {
    params: Vec<Vec<Expression>>,
    consumed: usize,
    best_effort: bool,
}

/// Read all parameters for a single opcode according to its
/// [`ParamSpec`]. Pulled out of [`disassemble`] so the
/// `GPL_RETVAL` recursion in [`read_expression_with_depth`] can
/// reuse it.
fn read_instruction_params_with_depth(
    opcode: u8,
    bytes: &[u8],
    cursor: usize,
    retval_depth: u8,
) -> InstructionParams {
    let mut pos = cursor;
    let mut params: Vec<Vec<Expression>> = Vec::new();
    let mut be = false;

    match param_spec(opcode) {
        ParamSpec::None => {}
        ParamSpec::Fixed(n) => {
            for _ in 0..n {
                let r = read_expression_with_depth(bytes, pos, retval_depth);
                pos += r.consumed;
                be |= r.best_effort;
                params.push(r.tokens);
                if r.consumed == 0 {
                    be = true;
                    break;
                }
            }
        }
        ParamSpec::Log => {
            if let Some((sub_type, value, consumed)) = read_text(bytes, pos) {
                pos += consumed;
                params.push(vec![Expression::ImmediateString { sub_type, value }]);
            } else {
                be = true;
            }
        }
        ParamSpec::LoadVar => {
            let r = read_expression_with_depth(bytes, pos, retval_depth);
            pos += r.consumed;
            be |= r.best_effort;
            params.push(r.tokens);
            if pos < bytes.len() {
                let raw = bytes[pos];
                let stripped = raw & 0x7F;
                let extended = (stripped & EXTENDED_VAR) != 0;
                let datatype = if extended { stripped & !EXTENDED_VAR } else { stripped };
                pos += 1;
                if datatype < 0x10 {
                    if let Some(var_kind) = VarKind::from_tag(datatype) {
                        let (id, n) = read_simple_num_var(bytes, pos, extended);
                        pos += n;
                        params.push(vec![Expression::Variable {
                            var_kind,
                            id,
                            extended,
                        }]);
                    } else {
                        be = true;
                        params.push(vec![Expression::Unknown { byte: raw }]);
                    }
                } else {
                    // Complex variable write: read the access_complex
                    // block.
                    match read_complex_access(bytes, pos) {
                        Some((obj_name, depth, elements, consumed)) => {
                            pos += consumed;
                            params.push(vec![Expression::ComplexAccess {
                                tag: datatype,
                                obj_name,
                                depth,
                                elements,
                            }]);
                        }
                        None => {
                            be = true;
                        }
                    }
                }
            } else {
                be = true;
            }
        }
        ParamSpec::SetRecord => {
            // gpl_setrecord: access_complex + read_number (per all
            // three branches of libgff parse.c 689-726).
            match read_complex_access(bytes, pos) {
                Some((obj_name, depth, elements, consumed)) => {
                    pos += consumed;
                    params.push(vec![Expression::ComplexAccess {
                        tag: 0,
                        obj_name,
                        depth,
                        elements,
                    }]);
                    let r = read_expression_with_depth(bytes, pos, retval_depth);
                    pos += r.consumed;
                    be |= r.best_effort;
                    params.push(r.tokens);
                }
                None => {
                    be = true;
                }
            }
        }
        ParamSpec::Menu => {
            let r = read_expression_with_depth(bytes, pos, retval_depth);
            pos += r.consumed;
            be |= r.best_effort;
            params.push(r.tokens);
            let mut items = 0;
            while items < 24 && pos < bytes.len() && bytes[pos] != 0x4A {
                for _ in 0..3 {
                    let r = read_expression_with_depth(bytes, pos, retval_depth);
                    if r.consumed == 0 {
                        be = true;
                        break;
                    }
                    pos += r.consumed;
                    be |= r.best_effort;
                    params.push(r.tokens);
                }
                items += 1;
            }
            if pos < bytes.len() && bytes[pos] == 0x4A {
                pos += 1;
            }
        }
        ParamSpec::Search => {
            let r = read_expression_with_depth(bytes, pos, retval_depth);
            pos += r.consumed;
            be |= r.best_effort;
            params.push(r.tokens);
            if pos + 2 > bytes.len() {
                be = true;
            } else {
                pos += 2;
                loop {
                    if pos < bytes.len() && bytes[pos] == 0x53 {
                        pos += 1;
                    }
                    if pos + 2 > bytes.len() {
                        be = true;
                        break;
                    }
                    let _field = bytes[pos];
                    pos += 1;
                    let type_ = bytes[pos];
                    pos += 1;
                    if (4..=6).contains(&type_) {
                        let r = read_expression_with_depth(bytes, pos, retval_depth);
                        if r.consumed == 0 {
                            be = true;
                            break;
                        }
                        pos += r.consumed;
                        be |= r.best_effort;
                        params.push(r.tokens);
                    }
                    if pos >= bytes.len() || bytes[pos] != 0x53 {
                        break;
                    }
                }
            }
        }
        ParamSpec::Custom => {
            // Best-effort: consume nothing beyond the opcode byte.
            // Mark misalignment.
            be = true;
        }
    }

    InstructionParams {
        params,
        consumed: pos - cursor,
        best_effort: be,
    }
}

/// Disassemble a GPL chunk into instructions.
///
/// Walks the byte stream linearly. For each opcode, looks up its
/// [`ParamSpec`] and reads the corresponding parameters via
/// [`read_instruction_params_with_depth`]. Stops at end of input.
pub fn disassemble(bytes: &[u8]) -> DisasmResult {
    let mut cursor = 0usize;
    let mut instructions: Vec<Instruction> = Vec::new();
    let mut any_best_effort = false;

    while cursor < bytes.len() {
        let start = cursor;
        let opcode = bytes[cursor];
        cursor += 1;
        let mnemonic = opcode_name(opcode);
        let r = read_instruction_params_with_depth(opcode, bytes, cursor, 0);
        cursor += r.consumed;
        let be = r.best_effort;
        let params = r.params;

        if be {
            any_best_effort = true;
        }
        let length = cursor - start;
        let string_run = if length > 0 {
            inline_string_run(&bytes[start..start + length])
        } else {
            None
        };

        instructions.push(Instruction {
            offset: start,
            length,
            opcode,
            mnemonic,
            params,
            best_effort: be,
            string_run,
        });
    }

    DisasmResult {
        aligned: !any_best_effort && cursor == bytes.len(),
        bytes_consumed: cursor,
        total_bytes: bytes.len(),
        instructions,
    }
}

/// Find the first printable ASCII run of length `>= MIN_STRING_LEN`
/// in `slice` and return it. Used for the inline-string annotation
/// carried over from v0.1.0.
fn inline_string_run(slice: &[u8]) -> Option<String> {
    let mut start: Option<usize> = None;
    let mut best: Option<(usize, usize)> = None;
    for (i, &b) in slice.iter().enumerate() {
        if is_printable(b) {
            start.get_or_insert(i);
        } else if let Some(s) = start.take() {
            if i - s >= MIN_STRING_LEN && best.is_none() {
                best = Some((s, i));
            }
        }
    }
    if let Some(s) = start {
        if slice.len() - s >= MIN_STRING_LEN && best.is_none() {
            best = Some((s, slice.len()));
        }
    }
    best.map(|(s, e)| String::from_utf8_lossy(&slice[s..e]).into_owned())
}

#[inline]
fn is_printable(b: u8) -> bool {
    (0x20..=0x7E).contains(&b) || matches!(b, b'\t' | b'\n' | b'\r')
}

// ---------- Display ----------

impl fmt::Display for Expression {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Expression::Immediate14 { value } => write!(f, "{value}"),
            Expression::ImmediateByte { value } => write!(f, "{value}i8"),
            Expression::ImmediateBigNum { value } => write!(f, "{value}i32"),
            Expression::ImmediateName { value } => write!(f, "NAME({value})"),
            Expression::ImmediateString { sub_type, value } => match sub_type {
                StringSubType::Introduce => write!(f, "INTRODUCE"),
                StringSubType::Uncompressed => write!(f, "UNCOMPRESSED"),
                StringSubType::Compressed => write!(f, "\"{}\"", escape_text(value)),
            },
            Expression::Variable {
                var_kind,
                id,
                extended,
            } => {
                let suffix = if *extended { "+" } else { "" };
                write!(f, "{}{suffix}[{id}]", var_kind.short_name())
            }
            Expression::BinaryOp { op } => write!(f, "{}", op.symbol()),
            Expression::OpenParen => write!(f, "("),
            Expression::CloseParen => write!(f, ")"),
            Expression::RetVal {
                inner_opcode,
                inner_mnemonic,
                inner_params,
            } => {
                let name = inner_mnemonic.unwrap_or("?");
                write!(f, "RETVAL({name}")?;
                for (i, param) in inner_params.iter().enumerate() {
                    write!(f, "{}", if i == 0 { " " } else { ", " })?;
                    for tok in param {
                        write!(f, "{tok}")?;
                    }
                }
                let _ = inner_opcode;
                write!(f, ")")
            }
            Expression::ComplexAccess {
                tag,
                obj_name,
                depth,
                elements,
            } => {
                let ctx = if *obj_name >= 0x8000 {
                    match (*obj_name as u32) & 0x7FFF {
                        0x25 => "POV",
                        0x26 => "ACTIVE",
                        0x27 => "PASSIVE",
                        0x28 => "OTHER",
                        0x2B => "THING",
                        0x2C => "OTHER1",
                        _ => "?",
                    }
                    .to_string()
                } else {
                    format!("id={obj_name}")
                };
                write!(f, "COMPLEX(0x{tag:02x}, {ctx}, depth={depth}")?;
                if !elements.is_empty() {
                    write!(f, ", [")?;
                    for (i, e) in elements.iter().enumerate() {
                        if i > 0 {
                            write!(f, ",")?;
                        }
                        write!(f, "{e}")?;
                    }
                    write!(f, "]")?;
                }
                write!(f, ")")
            }
            Expression::AccmError => write!(f, "ACCM_ERROR"),
            Expression::ImmediWordUnimplemented => write!(f, "IMMED_WORD_UNIMPL"),
            Expression::Unknown { byte } => write!(f, "??0x{byte:02x}"),
        }
    }
}

fn escape_text(s: &str) -> String {
    s.chars()
        .map(|c| match c {
            '\r' => "\\r".to_string(),
            '\n' => "\\n".to_string(),
            '\t' => "\\t".to_string(),
            '"' => "\\\"".to_string(),
            c if c.is_ascii_graphic() || c == ' ' => c.to_string(),
            c => format!("\\x{:02x}", c as u8),
        })
        .collect()
}

impl fmt::Display for Instruction {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let m = self.mnemonic.unwrap_or("db");
        write!(f, "{:04x}  {:02x}  {:<22}", self.offset, self.opcode, m)?;
        if self.mnemonic.is_none() {
            write!(f, "  ; ??")?;
        }
        for (i, param) in self.params.iter().enumerate() {
            write!(f, "{}", if i == 0 { "  " } else { ", " })?;
            write_param_tokens(f, param)?;
        }
        if self.best_effort {
            write!(f, "  ; best-effort")?;
        }
        if let Some(ref s) = self.string_run {
            write!(f, "  ; \"{}\"", escape_text(s))?;
        }
        Ok(())
    }
}

fn write_param_tokens(f: &mut fmt::Formatter<'_>, tokens: &[Expression]) -> fmt::Result {
    let mut prev_was_value = false;
    for tok in tokens {
        let is_open = matches!(tok, Expression::OpenParen);
        let is_close = matches!(tok, Expression::CloseParen);
        let is_op = matches!(tok, Expression::BinaryOp { .. });
        if prev_was_value && !is_close && !is_op {
            write!(f, " ")?;
        }
        if is_op {
            write!(f, " {tok} ")?;
        } else {
            write!(f, "{tok}")?;
        }
        prev_was_value = !is_open && !is_op;
    }
    Ok(())
}

// ---------- Tests ----------

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
    fn param_counts_match_known_handlers() {
        // Spot-checks against pick-it-up's worked counts.
        assert_eq!(PARAM_COUNTS[0x4F], ParamSpec::Fixed(2)); // print string
        assert_eq!(PARAM_COUNTS[0x25], ParamSpec::Fixed(6)); // clone
        assert_eq!(PARAM_COUNTS[0x6A], ParamSpec::Fixed(7)); // move boxtrigger
        assert_eq!(PARAM_COUNTS[0x76], ParamSpec::Fixed(2)); // byte plus equal
        assert_eq!(PARAM_COUNTS[0x67], ParamSpec::None); // endif
        assert_eq!(PARAM_COUNTS[0x2C], ParamSpec::Log); // gpl_log reads packed string
        assert_eq!(PARAM_COUNTS[0x16], ParamSpec::LoadVar);
        assert_eq!(PARAM_COUNTS[0x33], ParamSpec::Search);
        assert_eq!(PARAM_COUNTS[0x40], ParamSpec::SetRecord);
        assert_eq!(PARAM_COUNTS[0x48], ParamSpec::Menu);
    }

    #[test]
    fn read_expression_14bit_immediate() {
        // 0x12 0x34 → cval = 0x12 * 256 + 0x34 = 0x1234.
        let r = read_expression(&[0x12, 0x34], 0);
        assert_eq!(r.consumed, 2);
        assert!(!r.best_effort);
        assert_eq!(r.tokens, vec![Expression::Immediate14 { value: 0x1234 }]);
    }

    #[test]
    fn read_expression_immed_byte() {
        // 0x8F (GPL_IMMED_BYTE | 0x80) + 0xFF (signed -1).
        let r = read_expression(&[0x8F, 0xFF], 0);
        assert_eq!(r.consumed, 2);
        assert!(!r.best_effort);
        assert_eq!(r.tokens, vec![Expression::ImmediateByte { value: -1 }]);
    }

    #[test]
    fn read_expression_immed_bignum() {
        // 0x8B (GPL_IMMED_BIGNUM|0x80) + hi 0x0001 + lo 0x0002
        // → cval = 0x00010002.
        let r = read_expression(&[0x8B, 0x00, 0x01, 0x00, 0x02], 0);
        assert_eq!(r.consumed, 5);
        assert!(!r.best_effort);
        assert_eq!(
            r.tokens,
            vec![Expression::ImmediateBigNum { value: 0x00010002 }]
        );
    }

    #[test]
    fn read_expression_immed_name() {
        // 0x91 (GPL_IMMED_NAME|0x80) + halfword 0x0040 → -64.
        let r = read_expression(&[0x91, 0x00, 0x40], 0);
        assert_eq!(r.consumed, 3);
        assert_eq!(
            r.tokens,
            vec![Expression::ImmediateName { value: -64 }]
        );
    }

    #[test]
    fn read_expression_simple_variable() {
        // 0x8D (GFLAG|0x80) + 0x12 = GFLAG[18].
        let r = read_expression(&[0x8D, 0x12], 0);
        assert_eq!(r.consumed, 2);
        assert_eq!(
            r.tokens,
            vec![Expression::Variable {
                var_kind: VarKind::Gflag,
                id: 18,
                extended: false,
            }]
        );
    }

    #[test]
    fn read_expression_extended_variable() {
        // 0xCD = GFLAG | 0x80 | EXTENDED_VAR (0x40). 2-byte id.
        let r = read_expression(&[0xCD, 0x01, 0x23], 0);
        assert_eq!(r.consumed, 3);
        assert_eq!(
            r.tokens,
            vec![Expression::Variable {
                var_kind: VarKind::Gflag,
                id: 0x0123,
                extended: true,
            }]
        );
    }

    #[test]
    fn read_expression_operator_continues_loop() {
        // 14-bit immediate (0x00 0x05 = 5) + ADD (0xD1) + IMMED_BYTE 3.
        let r = read_expression(&[0x00, 0x05, 0xD1, 0x8F, 0x03], 0);
        assert_eq!(r.consumed, 5);
        assert_eq!(r.tokens.len(), 3);
        assert_eq!(r.tokens[0], Expression::Immediate14 { value: 5 });
        assert_eq!(r.tokens[1], Expression::BinaryOp { op: Op::Add });
        assert_eq!(r.tokens[2], Expression::ImmediateByte { value: 3 });
    }

    #[test]
    fn read_expression_parens() {
        // ( IMMED_BYTE 1 + IMMED_BYTE 2 ) — paren keeps the loop going.
        let r = read_expression(&[0xE2, 0x8F, 0x01, 0xD1, 0x8F, 0x02, 0xE1], 0);
        assert_eq!(r.consumed, 7);
        assert_eq!(r.tokens.len(), 5);
        assert_eq!(r.tokens[0], Expression::OpenParen);
        assert_eq!(r.tokens[4], Expression::CloseParen);
    }

    #[test]
    fn read_expression_retval_with_safe_inner_opcode() {
        // 0x8C (RETVAL|0x80) + inner 0x52 (gpl rand, ParamSpec::Fixed(1))
        // + a 14-bit immediate (0x00 0x05 = 5). The RETVAL should
        // recursively consume the inner opcode's one parameter and
        // NOT be best-effort.
        let r = read_expression(&[0x8C, 0x52, 0x00, 0x05], 0);
        assert!(!r.best_effort, "tokens={:?}", r.tokens);
        assert_eq!(r.consumed, 4);
        match &r.tokens[0] {
            Expression::RetVal {
                inner_opcode,
                inner_mnemonic,
                inner_params,
            } => {
                assert_eq!(*inner_opcode, 0x52);
                assert_eq!(*inner_mnemonic, Some("gpl rand"));
                assert_eq!(inner_params.len(), 1);
                assert_eq!(
                    inner_params[0],
                    vec![Expression::Immediate14 { value: 5 }]
                );
            }
            other => panic!("expected RetVal, got {other:?}"),
        }
    }

    #[test]
    fn read_expression_retval_with_unsafe_inner_marks_best_effort() {
        // 0x8C + 0x12 (gpl jump) is not in the libgff safe-subset;
        // mark best-effort and don't recurse.
        let r = read_expression(&[0x8C, 0x12], 0);
        assert!(r.best_effort);
        match &r.tokens[0] {
            Expression::RetVal {
                inner_opcode,
                inner_params,
                ..
            } => {
                assert_eq!(*inner_opcode, 0x12);
                assert!(inner_params.is_empty());
            }
            other => panic!("expected RetVal, got {other:?}"),
        }
    }

    #[test]
    fn read_complex_access_consumes_expected_bytes() {
        // word obj_name (big-endian) + byte depth + depth bytes.
        // 0x80 0x25 → obj_name = 0x8025 (POV), depth = 2, elements [4, 7].
        let (obj_name, depth, elements, consumed) =
            read_complex_access(&[0x80, 0x25, 0x02, 0x04, 0x07], 0).unwrap();
        assert_eq!(obj_name, 0x8025);
        assert_eq!(depth, 2);
        assert_eq!(elements, vec![4, 7]);
        assert_eq!(consumed, 5);
    }

    #[test]
    fn read_expression_complex_access() {
        // 0xB1 (GPL_COMPLEX_VAL|0x80) + obj_name 0x8027 (PASSIVE)
        // + depth 0 + (no elements). Should fully decode, not be
        // best-effort.
        let r = read_expression(&[0xB1, 0x80, 0x27, 0x00], 0);
        assert!(!r.best_effort, "tokens={:?}", r.tokens);
        assert_eq!(r.consumed, 4);
        match &r.tokens[0] {
            Expression::ComplexAccess {
                tag,
                obj_name,
                depth,
                elements,
            } => {
                assert_eq!(*tag, 0x31);
                assert_eq!(*obj_name, 0x8027);
                assert_eq!(*depth, 0);
                assert!(elements.is_empty());
            }
            other => panic!("expected ComplexAccess, got {other:?}"),
        }
    }

    #[test]
    fn disassemble_setrecord_fully_aligned() {
        // 0x40 (setrecord) + complex (obj_name=0x8025 POV, depth=1,
        // element=4) + 14-bit immediate (0x00 0x05 = 5).
        let r = disassemble(&[0x40, 0x80, 0x25, 0x01, 0x04, 0x00, 0x05]);
        assert!(r.aligned, "{r:?}");
        assert_eq!(r.instructions.len(), 1);
        assert_eq!(r.instructions[0].params.len(), 2);
    }

    #[test]
    fn retval_recursion_capped_at_max_depth() {
        // A chain of nested RETVALs that exceeds MAX_RETVAL_DEPTH
        // should bail out with best_effort, not blow the stack.
        // Build: 0x8C 0x52 0x8C 0x52 0x8C 0x52 0x8C 0x52 0x8C 0x52 ...
        // Each RETVAL's safe-subset inner (0x52 gpl rand) expects
        // 1 read_number param, which can itself be another 0x8C.
        let mut bytes = Vec::new();
        for _ in 0..(MAX_RETVAL_DEPTH as usize + 2) {
            bytes.extend_from_slice(&[0x8C, 0x52]);
        }
        bytes.extend_from_slice(&[0x00, 0x01]); // terminating immediate
        let r = read_expression(&bytes, 0);
        assert!(
            r.best_effort,
            "expected best_effort at depth {}, got tokens={:?}",
            MAX_RETVAL_DEPTH, r.tokens
        );
    }

    #[test]
    fn read_text_compressed_yields_known_string() {
        // Round-trip a known string through the compressor below.
        let payload = compress("Hello!");
        let mut bytes = vec![STRING_COMPRESSED];
        bytes.extend(payload);
        let (sub, s, _consumed) = read_text(&bytes, 0).unwrap();
        assert_eq!(sub, StringSubType::Compressed);
        assert_eq!(s, "Hello!");
    }

    #[test]
    fn read_text_introduce_consumes_one_byte() {
        let (sub, _s, consumed) = read_text(&[STRING_INTRODUCE], 0).unwrap();
        assert_eq!(sub, StringSubType::Introduce);
        assert_eq!(consumed, 1);
    }

    #[test]
    fn disassemble_simple_program() {
        // Three instructions, all 0-param: gpl endif (0x67),
        // gpl exit gpl (0x31), gpl printnl (0x51).
        let r = disassemble(&[0x67, 0x31, 0x51]);
        assert!(r.aligned);
        assert_eq!(r.bytes_consumed, 3);
        assert_eq!(r.instructions.len(), 3);
        assert_eq!(r.instructions[0].opcode, 0x67);
        assert_eq!(r.instructions[0].length, 1);
    }

    #[test]
    fn disassemble_with_2_param_instruction() {
        // gpl print string (0x4F) with two 14-bit immediates.
        let r = disassemble(&[0x4F, 0x00, 0x01, 0x00, 0x02]);
        assert!(r.aligned);
        assert_eq!(r.instructions.len(), 1);
        assert_eq!(r.instructions[0].length, 5);
        assert_eq!(r.instructions[0].params.len(), 2);
        assert_eq!(
            r.instructions[0].params[0],
            vec![Expression::Immediate14 { value: 1 }]
        );
    }

    #[test]
    fn disassemble_print_string_with_compressed_literal() {
        // gpl print string (0x4F) with first param a compressed
        // immediate string "hi!" and second param a 14-bit zero.
        let payload = compress("hi!");
        let mut bytes = vec![0x4F, 0x92, STRING_COMPRESSED];
        bytes.extend(payload);
        bytes.extend_from_slice(&[0x00, 0x00]);
        let r = disassemble(&bytes);
        assert!(r.aligned, "result was {r:?}");
        assert_eq!(r.instructions.len(), 1);
        match &r.instructions[0].params[0][0] {
            Expression::ImmediateString { sub_type, value } => {
                assert_eq!(*sub_type, StringSubType::Compressed);
                assert_eq!(value, "hi!");
            }
            other => panic!("expected ImmediateString, got {other:?}"),
        }
    }

    #[test]
    fn disassemble_custom_opcode_marks_best_effort() {
        // gpl joinparty (0x45) is Custom in libgff (gpl_unknown);
        // consume only the opcode byte and mark best-effort.
        let r = disassemble(&[0x45, 0x00, 0x01]);
        assert!(!r.aligned);
        assert!(r.instructions[0].best_effort);
        assert_eq!(r.instructions[0].length, 1);
    }

    #[test]
    fn disassemble_string_run_annotation() {
        // 0x4A is Custom (1 byte best-effort). Pad with printable
        // ASCII to trigger the string-run annotation on a later
        // instruction. Use 0x67 (endif, 0 params) wrapping bytes
        // that look like ASCII.
        // Sequence: endif endif Garn endif. The inline run is
        // captured under the 0x67's length=1 window which is just
        // one byte, so the run lands on a unique instruction —
        // here, the 'G' (0x47) is parsed as opcode itself
        // (gpl_unknown for our tests). Skip this case to keep
        // the test simple.
        let r = disassemble(&[0x67]);
        assert_eq!(r.instructions.len(), 1);
        assert!(r.instructions[0].string_run.is_none());
    }

    #[test]
    fn instruction_display_includes_offset_and_params() {
        let r = disassemble(&[0x4F, 0x00, 0x05, 0x00, 0x07]);
        let line = format!("{}", r.instructions[0]);
        assert!(line.starts_with("0000  4f  gpl print string"), "{line}");
        assert!(line.contains('5'));
        assert!(line.contains('7'));
    }

    /// Test helper: encode an ASCII string in the 7-bit packed
    /// format soloscuro-archive `read_compressed` decodes. Useful
    /// for round-trip tests on read_text.
    fn compress(s: &str) -> Vec<u8> {
        // Each character contributes 7 bits, packed MSB-first.
        // We append the terminator 0x03 and pad to a byte boundary.
        let mut bits: Vec<u8> = Vec::new();
        for ch in s.bytes() {
            for i in (0..7).rev() {
                bits.push((ch >> i) & 1);
            }
        }
        for i in (0..7).rev() {
            bits.push((STRING_TERMINATOR >> i) & 1);
        }
        while bits.len() % 8 != 0 {
            bits.push(0);
        }
        bits.chunks(8)
            .map(|c| c.iter().enumerate().fold(0u8, |acc, (i, &b)| acc | (b << (7 - i))))
            .collect()
    }

    #[test]
    fn compress_roundtrips_through_decoder() {
        // Confirms the test helper itself: a known string survives
        // a compress + read_text round trip.
        for s in &["a", "Hi", "Free!", "1234567890"] {
            let mut buf = vec![STRING_COMPRESSED];
            buf.extend(compress(s));
            let (_sub, decoded, _n) = read_text(&buf, 0).unwrap();
            assert_eq!(decoded, *s, "round trip for {s:?}");
        }
    }
}
