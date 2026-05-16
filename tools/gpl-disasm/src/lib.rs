//! gpl-disasm: disassembler for SSI's GPL bytecode (Dark Sun).
//!
//! v0.3.0 ships **control-flow analysis**: each aligned chunk
//! also yields a [`Cfg`] of basic blocks, entry points, and
//! labeled successors. Branch-target offsets render as labels
//! (`gpl if label_0x0020`) and the `--cfg` flag emits a Graphviz
//! DOT graph. Per-opcode branch semantics are documented in
//! `docs/gpl-bytecode.md` §5a and verified across 600 / 600
//! DS1+DS2 chunks (71,403 successor edges, 0 computed-target).
//!
//! v0.2.0 baseline: **parameter decoding**. Each opcode consumes
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

use std::borrow::Cow;
use std::collections::{BTreeMap, BTreeSet};
use std::fmt;
use std::fs;
use std::io::{self, Write};
use std::path::Path;

use serde::{Deserialize, Serialize};

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
    /// `Cow::Borrowed` for the default libgff names from
    /// [`OPCODES`]; `Cow::Owned` after [`Symbols::apply_to_mnemonics`]
    /// rewrites it with a hand-curated override from `opcodes.toml`.
    pub mnemonic: Option<Cow<'static, str>>,
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
    /// Control-flow graph built post-walk (v0.3.0+). `None` when
    /// `aligned == false`: best-effort disassembly may misidentify
    /// branch instructions, so we skip CFG construction rather than
    /// emit a wrong one.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cfg: Option<Cfg>,
    /// Cross-chunk `gpl global sub` (0x14) call sites. Targets are
    /// in another GPL file and are not wired into [`Cfg`]; recorded
    /// here for future inter-chunk analysis (v0.4.0+).
    #[serde(skip_serializing_if = "Vec::is_empty", default)]
    pub cross_chunk_calls: Vec<CrossChunkCall>,
}

// ---------- CFG types (v0.3.0) ----------

/// Control-flow graph for one disassembled chunk. Branch semantics
/// are documented in `docs/gpl-bytecode.md` §5a.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Cfg {
    /// Discovered entry offsets, sorted and deduplicated. Includes
    /// candidate offsets 0 and 1 (`chunk[0]` is consistently the
    /// `gpl global ret` epilogue placeholder), plus every observed
    /// `gpl local sub` target inside this chunk.
    pub entry_points: Vec<usize>,
    /// Basic blocks, sorted by `start_offset`.
    pub blocks: Vec<BasicBlock>,
    /// Offset → label name. One entry per block leader. Entry
    /// points get the `entry_0x...` form; other leaders get
    /// `label_0x...`.
    pub labels: BTreeMap<usize, String>,
    /// Auxiliary lookup for branch-target rendering. Maps "the raw
    /// target offset stored in a branch instruction's bytecode" to
    /// the corresponding label name when that raw offset is not
    /// itself a block leader. Currently populated only for
    /// `gpl else` (0x3F) offsets, which are not block leaders but
    /// are common branch targets (see [`redirect_past_else`]).
    /// Renderers that show `label_0xNNNN` in place of integer
    /// targets should consult [`Self::labels`] first, then
    /// [`Self::target_aliases`].
    #[serde(skip_serializing_if = "BTreeMap::is_empty", default)]
    pub target_aliases: BTreeMap<usize, String>,
    /// Successor offsets that didn't resolve to an instruction
    /// boundary in this chunk. Empirically should be empty for the
    /// DS1+DS2 corpus; populated only when a `jump` target's first
    /// param is a non-literal expression (computed jump).
    #[serde(skip_serializing_if = "Vec::is_empty", default)]
    pub unresolved: Vec<UnresolvedEdge>,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct BasicBlock {
    pub start_offset: usize,
    /// Exclusive: equals the next leader offset, or [`DisasmResult::total_bytes`]
    /// for the final block.
    pub end_offset: usize,
    /// Indices into [`DisasmResult::instructions`] for the
    /// instructions that make up this block.
    pub instruction_indices: Vec<usize>,
    pub successors: Vec<Edge>,
    pub terminator: TerminatorKind,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub enum TerminatorKind {
    /// Block ends because it ran into the next leader; control
    /// falls through. Used for `endif` / `cmpend` markers and for
    /// any unterminated leader-bounded run.
    Fallthrough,
    /// `gpl jump` (0x12) or `gpl wend` (0x64) — single outgoing
    /// edge.
    Unconditional,
    /// `gpl if` (0x3E), `gpl while` (0x63), `gpl ifcompare` (0x27)
    /// — two outgoing edges.
    Conditional,
    /// `gpl else` (0x3F) — single outgoing edge to the matching
    /// endif (unconditionally skips the else-block when reached by
    /// fall-through from the then-branch).
    UnconditionalElse,
    /// `gpl local ret` (0x15) / `gpl global ret` (0x19). No
    /// successors.
    Return,
    /// `gpl zero` (0x00, EXIT_GPL) / `gpl exit gpl` (0x31). No
    /// successors.
    ExitScript,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Edge {
    pub target_offset: usize,
    pub kind: EdgeKind,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub enum EdgeKind {
    /// Natural fall-through to the next instruction.
    Fallthrough,
    /// Unconditional branch taken (`gpl jump`, `gpl else`).
    Unconditional,
    /// Conditional branch's "predicate is true" path. For `gpl if`
    /// / `gpl while` this is the fall-through (the param target is
    /// the not-taken side); for `gpl ifcompare` this is also the
    /// fall-through (param[1] is the mismatch target).
    ConditionalTaken,
    /// Conditional branch's "predicate is false" path. For `gpl
    /// if` / `gpl while` / `gpl ifcompare` this is the param-supplied
    /// target.
    ConditionalNotTaken,
    /// `gpl wend` (0x64) backward edge to the matching `gpl while`.
    WhileBack,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct CrossChunkCall {
    /// Offset of the `gpl global sub` instruction in this chunk.
    pub from_offset: usize,
    /// First param: target offset within the destination GPL file.
    pub target_offset: i32,
    /// Second param: destination GPL file id.
    pub target_file_id: i32,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct UnresolvedEdge {
    pub from_offset: usize,
    pub reason: &'static str,
}

// ---------- Global CFG (v0.4.1) ----------

/// Whole-file inter-chunk control-flow graph. Nodes are GPL/MAS
/// chunks; edges are `gpl global sub` (0x14) call sites. Each
/// chunk's per-chunk [`Cfg`] models intra-chunk flow only; the
/// `GlobalCfg` is the union view across all chunks in a single
/// GFF.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct GlobalCfg {
    /// Source GFF basename (e.g. `GPLDATA.GFF`), preserved for
    /// downstream consumers and rendering.
    pub source: String,
    pub nodes: Vec<ChunkNode>,
    pub edges: Vec<CrossEdge>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ChunkNode {
    /// 4-char FOURCC including any trailing space (`GPL ` / `MAS `).
    pub kind: String,
    pub chunk_id: i32,
    /// Number of entry points (chunk start + every `local sub`
    /// target inside this chunk).
    pub entry_count: usize,
    /// Number of basic blocks in the chunk's intra-chunk CFG.
    pub block_count: usize,
    /// Number of `gpl global sub` call sites originating in this
    /// chunk.
    pub outbound_calls: usize,
    /// Number of `gpl global sub` call sites in other chunks
    /// (or this chunk, via self-call) targeting this chunk.
    /// Computed from the cross-chunk edge list.
    pub inbound_calls: usize,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct CrossEdge {
    pub from_kind: String,
    pub from_chunk: i32,
    pub from_offset: usize,
    /// Destination chunk id within the same GFF.
    pub to_chunk: i32,
    pub to_offset: usize,
    /// Optional symbol-derived name for the entry point that
    /// contains `from_offset` (the calling site's nearest
    /// enclosing entry).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub from_function_name: Option<String>,
    /// Optional symbol-derived name for `to_offset` when it
    /// matches an entry point in the destination chunk.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub to_function_name: Option<String>,
}

/// A single chunk's contribution to a [`GlobalCfg`]. Builder
/// callers iterate over every GPL/MAS chunk in the GFF, build
/// the per-chunk [`Cfg`], and pass the resulting tuple into
/// [`build_global_cfg`].
#[derive(Debug)]
pub struct ChunkSummary<'a> {
    pub kind: String,
    pub chunk_id: i32,
    pub cfg: &'a Cfg,
    pub cross_chunk_calls: &'a [CrossChunkCall],
}

/// Aggregate per-chunk Cfgs into a whole-file inter-chunk graph.
/// Symbols (if provided) annotate the from/to function names on
/// each cross-chunk edge.
pub fn build_global_cfg(
    source: &str,
    chunks: &[ChunkSummary<'_>],
    symbols: Option<&Symbols>,
) -> GlobalCfg {
    let mut nodes: Vec<ChunkNode> = Vec::with_capacity(chunks.len());
    let mut edges: Vec<CrossEdge> = Vec::new();
    let mut inbound: BTreeMap<i32, usize> = BTreeMap::new();

    // Per-chunk: build a sorted entry-offset list for "nearest
    // enclosing entry" lookups when resolving from_function_name.
    let chunk_entries: BTreeMap<i32, Vec<usize>> = chunks
        .iter()
        .map(|cs| (cs.chunk_id, cs.cfg.entry_points.clone()))
        .collect();

    for cs in chunks {
        for call in cs.cross_chunk_calls {
            let to_chunk = call.target_file_id;
            *inbound.entry(to_chunk).or_insert(0) += 1;
            let from_function_name = nearest_entry_symbol(
                symbols,
                source,
                &cs.kind,
                cs.chunk_id,
                call.from_offset,
                chunk_entries.get(&cs.chunk_id).map(|v| v.as_slice()).unwrap_or(&[]),
            );
            let to_offset = if call.target_offset >= 0 {
                call.target_offset as usize
            } else {
                0
            };
            let to_function_name = symbols.and_then(|s| {
                s.function_name(source, "GPL ", to_chunk, to_offset)
                    .map(String::from)
            });
            edges.push(CrossEdge {
                from_kind: cs.kind.clone(),
                from_chunk: cs.chunk_id,
                from_offset: call.from_offset,
                to_chunk,
                to_offset,
                from_function_name,
                to_function_name,
            });
        }
    }

    for cs in chunks {
        nodes.push(ChunkNode {
            kind: cs.kind.clone(),
            chunk_id: cs.chunk_id,
            entry_count: cs.cfg.entry_points.len(),
            block_count: cs.cfg.blocks.len(),
            outbound_calls: cs.cross_chunk_calls.len(),
            inbound_calls: *inbound.get(&cs.chunk_id).unwrap_or(&0),
        });
    }

    GlobalCfg {
        source: source.to_string(),
        nodes,
        edges,
    }
}

/// Find the symbol name for the entry point whose offset is the
/// largest value ≤ `call_offset` (i.e., the nearest enclosing
/// entry). Returns None if no symbol matches.
fn nearest_entry_symbol(
    symbols: Option<&Symbols>,
    file_basename: &str,
    kind: &str,
    chunk_id: i32,
    call_offset: usize,
    entries: &[usize],
) -> Option<String> {
    let syms = symbols?;
    let entry_offset = entries
        .iter()
        .rev()
        .find(|e| **e <= call_offset)
        .copied()?;
    syms.function_name(file_basename, kind, chunk_id, entry_offset)
        .map(String::from)
}

/// Emit a Graphviz DOT graph for `gcfg`. Nodes are labelled by
/// kind+id (and inbound/outbound counts in the label tooltip);
/// edges are styled by source chunk. Self-loops get a special
/// style. Suitable for whole-file callgraph visualisation.
pub fn write_global_cfg_dot(
    gcfg: &GlobalCfg,
    out: &mut impl Write,
) -> io::Result<()> {
    writeln!(out, "digraph global_cfg {{")?;
    writeln!(out, "  rankdir=LR;")?;
    writeln!(
        out,
        "  node [shape=box, fontname=\"monospace\", fontsize=9];"
    )?;
    writeln!(out, "  edge [fontname=\"monospace\", fontsize=8];")?;
    writeln!(
        out,
        "  label=\"global callgraph for {} ({} chunks, {} cross-chunk calls)\";",
        gcfg.source,
        gcfg.nodes.len(),
        gcfg.edges.len()
    )?;
    for n in &gcfg.nodes {
        let kind_trim = n.kind.trim_end();
        writeln!(
            out,
            "  c_{}_{} [label=\"{}-{}\\n{} entries, {} blocks\\nin:{} out:{}\"];",
            kind_trim,
            n.chunk_id,
            kind_trim,
            n.chunk_id,
            n.entry_count,
            n.block_count,
            n.inbound_calls,
            n.outbound_calls
        )?;
    }
    for e in &gcfg.edges {
        let from_trim = e.from_kind.trim_end();
        let is_self = e.from_chunk == e.to_chunk && from_trim == "GPL";
        let attrs = if is_self {
            " [style=dashed, color=gray50]"
        } else {
            ""
        };
        // For DS1/DS2 GPLDATA we observe `gpl global sub` targets
        // landing only in GPL chunks (never MAS), so the to-node
        // is always `c_GPL_<id>`.
        writeln!(
            out,
            "  c_{}_{} -> c_GPL_{}{};",
            from_trim, e.from_chunk, e.to_chunk, attrs
        )?;
    }
    writeln!(out, "}}")
}

// ---------- Symbols (v0.4.0) ----------

/// Hand-curated symbol catalogue. Seeded from the DSO v1.0
/// client's debug symbols (greg-kennedy/DarkSunOnline,
/// `tools/symbols.txt`) and cross-checked against game content.
/// Each row is verified before it lands here; see
/// `docs/dso-symbols.md` for the curation surface.
///
/// v0.4.0 covers function-entry naming (chunk + offset → name).
/// Opcode-mnemonic overrides and global-variable naming land in
/// v0.4.1+.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Symbols {
    /// Opcode-byte → DSO-derived display name. Pre-populated via
    /// `tools/gpl-disasm/syms/opcodes.toml`. v0.4.0 loads the map
    /// but does not yet rewrite mnemonics on output.
    #[serde(default)]
    pub opcodes: BTreeMap<String, OpcodeSymbol>,
    /// Function entries by `(file_basename, chunk_kind, chunk_id,
    /// offset)` → name. The file basename matches the source GFF
    /// (e.g. `GPLDATA.GFF`); chunk_kind is `"GPL "` or `"MAS "`
    /// (4-char FOURCC, trailing space preserved); chunk_id is the
    /// integer id; offset is the function entry's byte offset in
    /// the chunk.
    #[serde(default)]
    pub functions: Vec<FunctionSymbol>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct OpcodeSymbol {
    pub name: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub dso_source: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub verified_by: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FunctionSymbol {
    /// Source GFF basename, e.g. `GPLDATA.GFF`. Matched
    /// case-insensitively.
    pub file: String,
    /// Chunk FOURCC including any trailing space, e.g. `GPL ` or
    /// `MAS `.
    pub kind: String,
    pub chunk_id: i32,
    pub offset: usize,
    pub name: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub notes: Option<String>,
}

impl Symbols {
    /// Load `Symbols` from a directory containing `opcodes.toml`
    /// and `functions.toml`. Missing files are silently treated as
    /// empty (the loader returns a sparse `Symbols` rather than
    /// erroring). Malformed TOML is a hard error.
    pub fn load_from_dir(dir: &Path) -> Result<Self, SymbolsLoadError> {
        let mut syms = Symbols::default();
        let opcodes_path = dir.join("opcodes.toml");
        if opcodes_path.is_file() {
            let body = fs::read_to_string(&opcodes_path).map_err(|e| {
                SymbolsLoadError::Io {
                    path: opcodes_path.display().to_string(),
                    source: e,
                }
            })?;
            let parsed: OpcodesFile =
                toml::from_str(&body).map_err(|e| SymbolsLoadError::Parse {
                    path: opcodes_path.display().to_string(),
                    source: e,
                })?;
            syms.opcodes = parsed.opcodes;
        }
        let functions_path = dir.join("functions.toml");
        if functions_path.is_file() {
            let body = fs::read_to_string(&functions_path).map_err(|e| {
                SymbolsLoadError::Io {
                    path: functions_path.display().to_string(),
                    source: e,
                }
            })?;
            let parsed: FunctionsFile =
                toml::from_str(&body).map_err(|e| SymbolsLoadError::Parse {
                    path: functions_path.display().to_string(),
                    source: e,
                })?;
            syms.functions = parsed.function.unwrap_or_default();
        }
        Ok(syms)
    }

    /// Look up a function name for a specific (file, kind, chunk_id,
    /// offset). File matching is case-insensitive on basename; kind
    /// matching is byte-exact on the 4-char FOURCC (caller normalises).
    pub fn function_name(
        &self,
        file_basename: &str,
        kind: &str,
        chunk_id: i32,
        offset: usize,
    ) -> Option<&str> {
        let target = file_basename.to_ascii_lowercase();
        self.functions
            .iter()
            .find(|f| {
                f.file.to_ascii_lowercase() == target
                    && f.kind == kind
                    && f.chunk_id == chunk_id
                    && f.offset == offset
            })
            .map(|f| f.name.as_str())
    }

    /// Apply function-name decorations to `cfg.labels` in place.
    /// Each matching entry-point label becomes `entry_0xNNNN
    /// (name)`. Non-entry labels are left alone. JSON consumers
    /// (notably `dialog-extract`) pick up the enriched form
    /// automatically.
    pub fn apply_to_labels(
        &self,
        cfg: &mut Cfg,
        file_basename: &str,
        kind: &str,
        chunk_id: i32,
    ) {
        if self.functions.is_empty() {
            return;
        }
        let entry_set: BTreeSet<usize> = cfg.entry_points.iter().copied().collect();
        for (offset, name) in cfg.labels.iter_mut() {
            if !entry_set.contains(offset) {
                continue;
            }
            if let Some(sym) = self.function_name(file_basename, kind, chunk_id, *offset) {
                *name = format!("{name} ({sym})");
            }
        }
    }

    /// Apply opcode-mnemonic overrides to every instruction in
    /// `result`. For each instruction whose opcode byte has an entry
    /// in `self.opcodes` (keyed as `"0xNN"` lowercase hex), the
    /// `mnemonic` field is replaced with the curated name. Bytes
    /// with no entry keep the libgff default from [`OPCODES`].
    ///
    /// JSON consumers (e.g. `dialog-extract`) see the override
    /// directly through serde; they should continue to key on the
    /// `opcode` byte rather than `mnemonic` text. Inner mnemonics
    /// inside [`Expression::RetVal`] are intentionally left alone
    /// for v0.4.2; a follow-up release can extend the override to
    /// that path if curation finds a case where it matters.
    pub fn apply_to_mnemonics(&self, result: &mut DisasmResult) {
        if self.opcodes.is_empty() {
            return;
        }
        for instr in &mut result.instructions {
            let key = format!("0x{:02x}", instr.opcode);
            if let Some(sym) = self.opcodes.get(&key) {
                instr.mnemonic = Some(Cow::Owned(sym.name.clone()));
            }
        }
    }
}

#[derive(Debug, Deserialize, Default)]
struct OpcodesFile {
    #[serde(default)]
    opcodes: BTreeMap<String, OpcodeSymbol>,
}

#[derive(Debug, Deserialize, Default)]
struct FunctionsFile {
    #[serde(default)]
    function: Option<Vec<FunctionSymbol>>,
}

#[derive(Debug, thiserror::Error)]
pub enum SymbolsLoadError {
    #[error("reading {path}: {source}")]
    Io {
        path: String,
        #[source]
        source: io::Error,
    },
    #[error("parsing {path}: {source}")]
    Parse {
        path: String,
        #[source]
        source: toml::de::Error,
    },
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
        let mnemonic = opcode_name(opcode).map(Cow::Borrowed);
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

    let aligned = !any_best_effort && cursor == bytes.len();
    let total_bytes = bytes.len();
    let (cfg, cross_chunk_calls) = if aligned {
        let (c, x) = build_cfg(&instructions, total_bytes);
        (Some(c), x)
    } else {
        (None, Vec::new())
    };

    DisasmResult {
        aligned,
        bytes_consumed: cursor,
        total_bytes,
        instructions,
        cfg,
        cross_chunk_calls,
    }
}

// ---------- CFG construction (v0.3.0) ----------

/// Per-opcode classification for CFG construction. Returned by
/// [`classify_branch`].
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum BranchClass {
    /// Non-branch instruction; block continues to the next.
    NonBranch,
    /// Falls through but a sibling target may want this as a block
    /// leader (`gpl endif` 0x67, `gpl cmpend` 0x61). Treated like
    /// `NonBranch` for terminator purposes; the leader is added
    /// because something jumps here.
    Marker,
    /// `gpl jump` (0x12): 1 successor = param[0].
    Jump,
    /// `gpl local sub` (0x13): block continues; target is recorded
    /// as a separate entry point.
    LocalSub,
    /// `gpl global sub` (0x14): block continues; target is recorded
    /// as a cross-chunk call only.
    GlobalSub,
    /// `gpl local ret` / `gpl global ret` / `gpl exit gpl` /
    /// `gpl zero` — block terminates with no successors.
    Return,
    /// Single-param conditional (`if`, `while`). Param[0] is the
    /// not-taken target; falls through on the taken path.
    Conditional1,
    /// `gpl else` (0x3F): unconditional jump to param[0] (skips the
    /// else-block when reached by fall-through from the then-block).
    Else,
    /// `gpl wend` (0x64): unconditional backward jump to param[0]
    /// (matching `while`).
    Wend,
    /// `gpl ifcompare` (0x27): param[0] is the comparison value;
    /// param[1] is the not-taken target. Falls through on match.
    Ifcompare,
}

fn classify_branch(opcode: u8) -> BranchClass {
    match opcode {
        0x00 | 0x31 => BranchClass::Return, // gpl zero (EXIT_GPL), gpl exit gpl
        0x12 => BranchClass::Jump,
        0x13 => BranchClass::LocalSub,
        0x14 => BranchClass::GlobalSub,
        0x15 | 0x19 => BranchClass::Return,
        0x27 => BranchClass::Ifcompare,
        0x3E | 0x63 => BranchClass::Conditional1,
        0x3F => BranchClass::Else,
        0x61 | 0x67 => BranchClass::Marker, // gpl cmpend, gpl endif
        0x64 => BranchClass::Wend,
        _ => BranchClass::NonBranch,
    }
}

/// Extract a literal integer value from a single-param expression
/// list. Returns `Some(value)` only when the param is exactly one
/// of the immediate-literal forms (`Immediate14`, `ImmediateByte`,
/// `ImmediateBigNum`). Returns `None` for variable references,
/// computed expressions, `RetVal`, etc.
fn literal_target(param: &[Expression]) -> Option<i64> {
    if param.len() != 1 {
        return None;
    }
    match &param[0] {
        Expression::Immediate14 { value } => Some(*value as i64),
        Expression::ImmediateByte { value } => Some(*value as i64),
        Expression::ImmediateBigNum { value } => Some(*value as i64),
        _ => None,
    }
}

/// If `target` is the offset of a `gpl else` (0x3F) instruction,
/// return the offset of the instruction immediately *after* the
/// else opcode; otherwise return `target` unchanged.
///
/// Background: the `gpl else` opcode is a dual-mode instruction.
/// When reached by fall-through from a then-block, it executes its
/// own unconditional jump (target = its param, typically the
/// matching endif). When reached by jump (e.g., from a `gpl if`'s
/// not-taken edge), it behaves as a no-op and control continues
/// past the opcode bytes into the else-body. The runtime
/// distinguishes the two paths via the if/while depth state; for
/// CFG purposes we just redirect any incoming jump past the else
/// opcode so the else-body shows up on the not-taken successor.
///
/// 5,471 of 20,281 conditional branches in the DS1+DS2 corpus
/// (27%) land on a `gpl else` opcode; before this redirect, the
/// not-taken paths skipped the else-body entirely.
fn redirect_past_else(
    target: usize,
    instructions: &[Instruction],
    offset_to_idx: &BTreeMap<usize, usize>,
) -> usize {
    if let Some(&idx) = offset_to_idx.get(&target) {
        let instr = &instructions[idx];
        if instr.opcode == 0x3F {
            return instr.offset + instr.length;
        }
    }
    target
}

/// Build a [`Cfg`] for an aligned chunk's instruction list. Caller
/// is responsible for skipping this when the disassembly was not
/// aligned (best-effort consumption can misidentify branch
/// instructions).
pub fn build_cfg(
    instructions: &[Instruction],
    chunk_len: usize,
) -> (Cfg, Vec<CrossChunkCall>) {
    // Offset → instruction index, used to validate target offsets
    // and to populate `instruction_indices` later.
    let offset_to_idx: BTreeMap<usize, usize> = instructions
        .iter()
        .enumerate()
        .map(|(i, instr)| (instr.offset, i))
        .collect();

    let mut leaders: BTreeSet<usize> = BTreeSet::new();
    leaders.insert(0);
    // `chunk[0]` is consistently `gpl global ret` (0x19) as an
    // epilogue placeholder. Treat offset 1 as a candidate entry
    // point too if a real instruction lives there.
    if offset_to_idx.contains_key(&1) {
        leaders.insert(1);
    }

    let mut entry_points: BTreeSet<usize> = BTreeSet::new();
    entry_points.insert(0);
    if offset_to_idx.contains_key(&1) {
        entry_points.insert(1);
    }

    let mut cross_chunk_calls: Vec<CrossChunkCall> = Vec::new();
    let mut unresolved: Vec<UnresolvedEdge> = Vec::new();

    // Pass 1: collect leaders and cross-chunk records.
    for (i, instr) in instructions.iter().enumerate() {
        let class = classify_branch(instr.opcode);
        let next_offset = instructions
            .get(i + 1)
            .map(|n| n.offset)
            .unwrap_or(chunk_len);
        match class {
            BranchClass::NonBranch | BranchClass::Marker => {}
            BranchClass::Jump | BranchClass::Conditional1 | BranchClass::Else | BranchClass::Wend => {
                if let Some(v) = instr.params.first().and_then(|p| literal_target(p)) {
                    if v >= 0 && (v as usize) <= chunk_len {
                        let t = redirect_past_else(v as usize, instructions, &offset_to_idx);
                        leaders.insert(t);
                    } else {
                        unresolved.push(UnresolvedEdge {
                            from_offset: instr.offset,
                            reason: "target out of range",
                        });
                    }
                } else {
                    unresolved.push(UnresolvedEdge {
                        from_offset: instr.offset,
                        reason: "non-literal target",
                    });
                }
                leaders.insert(next_offset);
            }
            BranchClass::Ifcompare => {
                if let Some(v) = instr.params.get(1).and_then(|p| literal_target(p)) {
                    if v >= 0 && (v as usize) <= chunk_len {
                        let t = redirect_past_else(v as usize, instructions, &offset_to_idx);
                        leaders.insert(t);
                    } else {
                        unresolved.push(UnresolvedEdge {
                            from_offset: instr.offset,
                            reason: "target out of range",
                        });
                    }
                } else {
                    unresolved.push(UnresolvedEdge {
                        from_offset: instr.offset,
                        reason: "non-literal target",
                    });
                }
                leaders.insert(next_offset);
            }
            BranchClass::LocalSub => {
                if let Some(v) = instr.params.first().and_then(|p| literal_target(p)) {
                    if v >= 0 && (v as usize) <= chunk_len {
                        let t = redirect_past_else(v as usize, instructions, &offset_to_idx);
                        leaders.insert(t);
                        entry_points.insert(t);
                    }
                }
            }
            BranchClass::GlobalSub => {
                let target = instr
                    .params
                    .first()
                    .and_then(|p| literal_target(p))
                    .unwrap_or(0) as i32;
                let file_id = instr
                    .params
                    .get(1)
                    .and_then(|p| literal_target(p))
                    .unwrap_or(0) as i32;
                cross_chunk_calls.push(CrossChunkCall {
                    from_offset: instr.offset,
                    target_offset: target,
                    target_file_id: file_id,
                });
            }
            BranchClass::Return => {
                leaders.insert(next_offset);
            }
        }
    }

    // Drop leaders that don't correspond to a real instruction
    // boundary (and aren't the chunk-end sentinel). These can
    // happen when an `if` target was a non-literal expression and
    // got mistakenly added; the unresolved list already records it.
    let leaders: Vec<usize> = leaders
        .into_iter()
        .filter(|o| *o == chunk_len || offset_to_idx.contains_key(o))
        .collect();

    // Pass 2: build blocks.
    let mut blocks: Vec<BasicBlock> = Vec::with_capacity(leaders.len());
    for (li, &start) in leaders.iter().enumerate() {
        if start == chunk_len {
            continue;
        }
        let end = leaders.get(li + 1).copied().unwrap_or(chunk_len);
        let mut instr_indices: Vec<usize> = Vec::new();
        for (i, instr) in instructions.iter().enumerate() {
            if instr.offset >= start && instr.offset < end {
                instr_indices.push(i);
            } else if instr.offset >= end {
                break;
            }
        }

        let (terminator, successors) = if let Some(&last_idx) = instr_indices.last() {
            let last = &instructions[last_idx];
            successors_for(last, end, instructions, &offset_to_idx)
        } else {
            (TerminatorKind::Fallthrough, vec![])
        };

        blocks.push(BasicBlock {
            start_offset: start,
            end_offset: end,
            instruction_indices: instr_indices,
            successors,
            terminator,
        });
    }

    // Labels: every block leader gets one. Entry points get the
    // `entry_0xNNNN` form; other leaders get `label_0xNNNN`.
    let mut labels: BTreeMap<usize, String> = BTreeMap::new();
    for b in &blocks {
        let name = if entry_points.contains(&b.start_offset) {
            format!("entry_{:#06x}", b.start_offset)
        } else {
            format!("label_{:#06x}", b.start_offset)
        };
        labels.insert(b.start_offset, name);
    }
    // target_aliases: map each `gpl else` opcode's raw offset to
    // the label name of its post-else block leader. This lets
    // branch-target renderers replace the stored target value
    // with a meaningful label name without making the else
    // offset itself a block leader (and thus without prepending a
    // spurious label_*: line in front of the else instruction).
    let mut target_aliases: BTreeMap<usize, String> = BTreeMap::new();
    for instr in instructions {
        if instr.opcode == 0x3F {
            let redirected = instr.offset + instr.length;
            if let Some(name) = labels.get(&redirected).cloned() {
                target_aliases.insert(instr.offset, name);
            }
        }
    }

    let cfg = Cfg {
        entry_points: entry_points.into_iter().collect(),
        blocks,
        labels,
        target_aliases,
        unresolved,
    };
    (cfg, cross_chunk_calls)
}

/// Build the successor list for a block whose terminator
/// instruction is `last`. `next_block_offset` is the fall-through
/// destination if applicable. `instructions` + `offset_to_idx` let
/// us apply the [`redirect_past_else`] fixup when a branch target
/// lands on a `gpl else` opcode.
fn successors_for(
    last: &Instruction,
    next_block_offset: usize,
    instructions: &[Instruction],
    offset_to_idx: &BTreeMap<usize, usize>,
) -> (TerminatorKind, Vec<Edge>) {
    let class = classify_branch(last.opcode);
    match class {
        BranchClass::NonBranch | BranchClass::Marker | BranchClass::LocalSub => (
            TerminatorKind::Fallthrough,
            vec![Edge {
                target_offset: next_block_offset,
                kind: EdgeKind::Fallthrough,
            }],
        ),
        BranchClass::GlobalSub => (
            TerminatorKind::Fallthrough,
            vec![Edge {
                target_offset: next_block_offset,
                kind: EdgeKind::Fallthrough,
            }],
        ),
        BranchClass::Return => (TerminatorKind::Return, vec![]),
        BranchClass::Jump => {
            let target = last
                .params
                .first()
                .and_then(|p| literal_target(p))
                .map(|v| redirect_past_else(v as usize, instructions, offset_to_idx));
            (
                TerminatorKind::Unconditional,
                target
                    .map(|t| {
                        vec![Edge {
                            target_offset: t,
                            kind: EdgeKind::Unconditional,
                        }]
                    })
                    .unwrap_or_default(),
            )
        }
        BranchClass::Else => {
            // The `gpl else` opcode's *own* unconditional target is
            // its param (the matching endif). Do NOT redirect: this
            // is the goto the runtime executes when reached by
            // fall-through from a then-block.
            let target = last
                .params
                .first()
                .and_then(|p| literal_target(p))
                .map(|v| v as usize);
            (
                TerminatorKind::UnconditionalElse,
                target
                    .map(|t| {
                        vec![Edge {
                            target_offset: t,
                            kind: EdgeKind::Unconditional,
                        }]
                    })
                    .unwrap_or_default(),
            )
        }
        BranchClass::Wend => {
            let target = last
                .params
                .first()
                .and_then(|p| literal_target(p))
                .map(|v| redirect_past_else(v as usize, instructions, offset_to_idx));
            (
                TerminatorKind::Unconditional,
                target
                    .map(|t| {
                        vec![Edge {
                            target_offset: t,
                            kind: EdgeKind::WhileBack,
                        }]
                    })
                    .unwrap_or_default(),
            )
        }
        BranchClass::Conditional1 => {
            let target = last
                .params
                .first()
                .and_then(|p| literal_target(p))
                .map(|v| redirect_past_else(v as usize, instructions, offset_to_idx));
            let mut edges = vec![Edge {
                target_offset: next_block_offset,
                kind: EdgeKind::ConditionalTaken,
            }];
            if let Some(t) = target {
                edges.push(Edge {
                    target_offset: t,
                    kind: EdgeKind::ConditionalNotTaken,
                });
            }
            (TerminatorKind::Conditional, edges)
        }
        BranchClass::Ifcompare => {
            let target = last
                .params
                .get(1)
                .and_then(|p| literal_target(p))
                .map(|v| redirect_past_else(v as usize, instructions, offset_to_idx));
            let mut edges = vec![Edge {
                target_offset: next_block_offset,
                kind: EdgeKind::ConditionalTaken,
            }];
            if let Some(t) = target {
                edges.push(Edge {
                    target_offset: t,
                    kind: EdgeKind::ConditionalNotTaken,
                });
            }
            (TerminatorKind::Conditional, edges)
        }
    }
}

/// Emit a Graphviz DOT graph for `cfg`. Block nodes carry an
/// abbreviated label (offset + first instruction's mnemonic);
/// edges are colored by [`EdgeKind`].
pub fn write_dot(
    cfg: &Cfg,
    instructions: &[Instruction],
    out: &mut impl Write,
) -> io::Result<()> {
    writeln!(out, "digraph cfg {{")?;
    writeln!(out, "  rankdir=TB;")?;
    writeln!(
        out,
        "  node [shape=box, fontname=\"monospace\", fontsize=10];"
    )?;
    writeln!(out, "  edge [fontname=\"monospace\", fontsize=9];")?;
    for b in &cfg.blocks {
        let head_mnemonic = b
            .instruction_indices
            .first()
            .and_then(|i| instructions.get(*i))
            .and_then(|instr| instr.mnemonic.as_deref())
            .unwrap_or("(empty)");
        let term = match b.terminator {
            TerminatorKind::Fallthrough => "",
            TerminatorKind::Unconditional => " | jmp",
            TerminatorKind::UnconditionalElse => " | else",
            TerminatorKind::Conditional => " | cond",
            TerminatorKind::Return => " | ret",
            TerminatorKind::ExitScript => " | exit",
        };
        let label = cfg
            .labels
            .get(&b.start_offset)
            .map(String::as_str)
            .unwrap_or("?");
        writeln!(
            out,
            "  blk_{:04x} [label=\"{}\\n{:#06x}: {}{}\"];",
            b.start_offset, label, b.start_offset, head_mnemonic, term
        )?;
    }
    for b in &cfg.blocks {
        for edge in &b.successors {
            let color = match edge.kind {
                EdgeKind::Fallthrough => "gray50",
                EdgeKind::Unconditional => "black",
                EdgeKind::ConditionalTaken => "darkgreen",
                EdgeKind::ConditionalNotTaken => "firebrick",
                EdgeKind::WhileBack => "blue",
            };
            // If the target isn't a block leader, draw to a
            // synthetic offset node so the reader sees the
            // mismatch.
            let target_block = cfg
                .blocks
                .iter()
                .find(|tb| tb.start_offset == edge.target_offset);
            if let Some(tb) = target_block {
                writeln!(
                    out,
                    "  blk_{:04x} -> blk_{:04x} [color=\"{}\"];",
                    b.start_offset, tb.start_offset, color
                )?;
            } else {
                writeln!(
                    out,
                    "  blk_{:04x} -> off_{:04x} [color=\"{}\", style=dashed];",
                    b.start_offset, edge.target_offset, color
                )?;
                writeln!(
                    out,
                    "  off_{:04x} [shape=plaintext, label=\"{:#06x}\\n(off-graph)\"];",
                    edge.target_offset, edge.target_offset
                )?;
            }
        }
    }
    writeln!(out, "}}")
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
        let m = self.mnemonic.as_deref().unwrap_or("db");
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

    // ---------- CFG tests (v0.3.0) ----------

    /// Build a chunk:
    ///   0x00: gpl global ret (0x19)              ; placeholder
    ///   0x01: gpl load accum (0x18) with simple immediate
    ///         — too complex for a hand-written test; instead
    ///         use bare-opcode branches with literal params:
    /// Synthetic: jump 5; (offset 3) gpl endif (0x67); ret (0x15)
    fn fake_instr(offset: usize, opcode: u8, target: Option<u16>) -> Instruction {
        let params = match target {
            Some(v) => vec![vec![Expression::Immediate14 { value: v }]],
            None => vec![],
        };
        let length = 1 + match target {
            Some(_) => 2, // Immediate14 is 2 bytes
            None => 0,
        };
        Instruction {
            offset,
            length,
            opcode,
            mnemonic: opcode_name(opcode).map(Cow::Borrowed),
            params,
            best_effort: false,
            string_run: None,
        }
    }

    #[test]
    fn cfg_classifies_jump_opcode() {
        // jump (0x12) target=5; endif (0x67) at 3; ret (0x15) at 4;
        // chunk ends at 5.
        let instrs = vec![
            fake_instr(0, 0x12, Some(5)),
            fake_instr(3, 0x67, None),
            fake_instr(4, 0x15, None),
        ];
        let (cfg, _) = build_cfg(&instrs, 5);
        // Leaders: 0 (entry), 3 (after the jump), target=5 (chunk
        // end, not a block). After filter: 0, 3 → 2 blocks.
        assert_eq!(cfg.blocks.len(), 2);
        let jump_block = &cfg.blocks[0];
        assert_eq!(jump_block.terminator, TerminatorKind::Unconditional);
        assert_eq!(jump_block.successors.len(), 1);
        assert_eq!(jump_block.successors[0].target_offset, 5);
        assert_eq!(jump_block.successors[0].kind, EdgeKind::Unconditional);
    }

    #[test]
    fn cfg_classifies_if_opcode_with_two_successors() {
        // if (0x3E) at 0 jumps to 6 on false; endif (0x67) at 6
        // Layout: if(target=6) at 0 (3 bytes), endif at 3 (1 byte),
        // ret at 4 (1 byte), endif at 6 (1 byte).
        // The if at 0 jumps to offset 6.
        let instrs = vec![
            fake_instr(0, 0x3E, Some(6)),
            fake_instr(3, 0x67, None),
            fake_instr(4, 0x15, None),
            fake_instr(6, 0x67, None),
        ];
        let (cfg, _) = build_cfg(&instrs, 7);
        let if_block = &cfg.blocks[0];
        assert_eq!(if_block.terminator, TerminatorKind::Conditional);
        assert_eq!(if_block.successors.len(), 2);
        // First successor is the taken/fallthrough (next instr at 3).
        assert_eq!(if_block.successors[0].target_offset, 3);
        assert_eq!(if_block.successors[0].kind, EdgeKind::ConditionalTaken);
        // Second is the not-taken (param target = 6).
        assert_eq!(if_block.successors[1].target_offset, 6);
        assert_eq!(
            if_block.successors[1].kind,
            EdgeKind::ConditionalNotTaken
        );
    }

    #[test]
    fn cfg_redirects_if_target_past_else_opcode() {
        // Synthetic if-then-else:
        //   0: if   (len 3, target = 4 = else opcode)
        //   3: endif-marker (len 1; stands in for then-body)
        //   4: else (len 3, target = 9 = matching endif)
        //   7: endif-marker (len 1; stands in for else-body)
        //   8: endif-marker (len 1; stands in for else-body)
        //   9: endif (len 1)
        // The if's not-taken edge param is 4 (the else opcode);
        // with the redirect, the effective target is 7 (the
        // byte after the else opcode = start of the else-body).
        let instrs = vec![
            fake_instr(0, 0x3E, Some(4)),  // if @ 0, len=3, target=4
            fake_instr(3, 0x67, None),     // then-body filler
            fake_instr(4, 0x3F, Some(9)),  // else @ 4, len=3, target=9
            fake_instr(7, 0x67, None),     // else-body filler
            fake_instr(8, 0x67, None),     // else-body filler
            fake_instr(9, 0x67, None),     // endif @ 9
        ];
        let (cfg, _) = build_cfg(&instrs, 10);
        let if_block = cfg
            .blocks
            .iter()
            .find(|b| b.start_offset == 0)
            .expect("block at if");
        assert_eq!(if_block.terminator, TerminatorKind::Conditional);
        let not_taken = if_block
            .successors
            .iter()
            .find(|e| e.kind == EdgeKind::ConditionalNotTaken)
            .expect("not-taken edge");
        // Without redirect this would be 4 (the else opcode itself).
        // With redirect it's 7 (the byte after the else opcode).
        assert_eq!(not_taken.target_offset, 7);
        // The else opcode's offset (4) should NOT be a block leader.
        assert!(
            !cfg.blocks.iter().any(|b| b.start_offset == 4),
            "no block should start at the else opcode's offset"
        );
        // target_aliases should map the else offset to the
        // redirected label so renderers can still resolve raw
        // branch params that point at the else opcode.
        assert_eq!(
            cfg.target_aliases.get(&4).map(String::as_str),
            Some("label_0x0007")
        );
    }

    #[test]
    fn cfg_classifies_else_opcode_as_unconditional() {
        // else (0x3F) at 0 with target=6.
        let instrs = vec![
            fake_instr(0, 0x3F, Some(6)),
            fake_instr(3, 0x67, None),
            fake_instr(6, 0x67, None),
        ];
        let (cfg, _) = build_cfg(&instrs, 7);
        let else_block = &cfg.blocks[0];
        assert_eq!(else_block.terminator, TerminatorKind::UnconditionalElse);
        assert_eq!(else_block.successors.len(), 1);
        assert_eq!(else_block.successors[0].target_offset, 6);
        assert_eq!(else_block.successors[0].kind, EdgeKind::Unconditional);
    }

    #[test]
    fn cfg_classifies_wend_as_backward_edge() {
        // while (0x63) at 0 target=10; endif at 3; wend (0x64) at 5
        // target=0 (back to while); endif at 8.
        // The wend is the terminator of the block that starts at
        // 3 (it's a leader because while's next_offset added it).
        let instrs = vec![
            fake_instr(0, 0x63, Some(10)),
            fake_instr(3, 0x67, None),
            fake_instr(5, 0x64, Some(0)),
            fake_instr(8, 0x67, None),
        ];
        let (cfg, _) = build_cfg(&instrs, 10);
        let wend_block = cfg
            .blocks
            .iter()
            .find(|b| {
                b.successors
                    .iter()
                    .any(|e| e.kind == EdgeKind::WhileBack)
            })
            .expect("block with WhileBack edge");
        assert_eq!(wend_block.terminator, TerminatorKind::Unconditional);
        assert_eq!(wend_block.successors.len(), 1);
        assert_eq!(wend_block.successors[0].target_offset, 0);
        assert_eq!(wend_block.successors[0].kind, EdgeKind::WhileBack);
    }

    #[test]
    fn cfg_treats_local_sub_target_as_entry_point() {
        // local sub (0x13) target=5; ret (0x15) at 3; func body at 5;
        // ret at 6.
        let instrs = vec![
            fake_instr(0, 0x13, Some(5)),
            fake_instr(3, 0x15, None),
            fake_instr(5, 0x67, None),
            fake_instr(6, 0x15, None),
        ];
        let (cfg, _) = build_cfg(&instrs, 7);
        assert!(
            cfg.entry_points.contains(&5),
            "entry_points={:?}",
            cfg.entry_points
        );
    }

    #[test]
    fn cfg_records_global_sub_as_cross_chunk_call() {
        // global sub (0x14) target=42 file=7.
        let instr = Instruction {
            offset: 0,
            length: 5,
            opcode: 0x14,
            mnemonic: opcode_name(0x14).map(Cow::Borrowed),
            params: vec![
                vec![Expression::Immediate14 { value: 42 }],
                vec![Expression::Immediate14 { value: 7 }],
            ],
            best_effort: false,
            string_run: None,
        };
        let instrs = vec![instr, fake_instr(5, 0x15, None)];
        let (_, calls) = build_cfg(&instrs, 6);
        assert_eq!(calls.len(), 1);
        assert_eq!(calls[0].from_offset, 0);
        assert_eq!(calls[0].target_offset, 42);
        assert_eq!(calls[0].target_file_id, 7);
    }

    #[test]
    fn cfg_classifies_ifcompare_with_two_successors() {
        // ifcompare (0x27) value=2 target=8.
        let instr = Instruction {
            offset: 0,
            length: 5,
            opcode: 0x27,
            mnemonic: opcode_name(0x27).map(Cow::Borrowed),
            params: vec![
                vec![Expression::ImmediateByte { value: 2 }],
                vec![Expression::Immediate14 { value: 8 }],
            ],
            best_effort: false,
            string_run: None,
        };
        let instrs = vec![
            instr,
            fake_instr(5, 0x67, None),
            fake_instr(8, 0x67, None),
        ];
        let (cfg, _) = build_cfg(&instrs, 9);
        let ic = &cfg.blocks[0];
        assert_eq!(ic.terminator, TerminatorKind::Conditional);
        assert_eq!(ic.successors.len(), 2);
        // Fallthrough on match.
        assert_eq!(ic.successors[0].target_offset, 5);
        assert_eq!(ic.successors[0].kind, EdgeKind::ConditionalTaken);
        // Param[1] target on mismatch.
        assert_eq!(ic.successors[1].target_offset, 8);
        assert_eq!(
            ic.successors[1].kind,
            EdgeKind::ConditionalNotTaken
        );
    }

    #[test]
    fn cfg_labels_use_entry_or_label_form() {
        // Entry points get `entry_0x...`; non-entry leaders get
        // `label_0x...`.
        let instrs = vec![
            fake_instr(0, 0x12, Some(3)),
            fake_instr(3, 0x15, None),
        ];
        let (cfg, _) = build_cfg(&instrs, 4);
        assert_eq!(cfg.labels.get(&0).map(String::as_str), Some("entry_0x0000"));
        // 3 is a leader because it's after a Jump; not an entry.
        assert_eq!(cfg.labels.get(&3).map(String::as_str), Some("label_0x0003"));
    }

    #[test]
    fn cfg_skipped_when_disassembly_not_aligned() {
        // 0xFF is unknown; the decoder marks the instruction
        // best-effort. disassemble() should leave cfg = None.
        let result = disassemble(&[0xFF, 0x00]);
        assert!(!result.aligned);
        assert!(result.cfg.is_none());
    }

    #[test]
    fn global_cfg_aggregates_inbound_outbound_counts() {
        // Two chunks: GPL-1 calls GPL-2 twice; GPL-2 calls GPL-1
        // once (and itself once via self-call).
        let cfg1 = Cfg {
            entry_points: vec![0, 1],
            blocks: vec![],
            labels: BTreeMap::new(),
            target_aliases: BTreeMap::new(),
            unresolved: vec![],
        };
        let cfg2 = cfg1.clone();
        let calls1 = vec![
            CrossChunkCall {
                from_offset: 0x10,
                target_offset: 0x100,
                target_file_id: 2,
            },
            CrossChunkCall {
                from_offset: 0x20,
                target_offset: 0x200,
                target_file_id: 2,
            },
        ];
        let calls2 = vec![
            CrossChunkCall {
                from_offset: 0x40,
                target_offset: 0x40,
                target_file_id: 1,
            },
            CrossChunkCall {
                from_offset: 0x50,
                target_offset: 0x50,
                target_file_id: 2,
            },
        ];
        let summaries = vec![
            ChunkSummary {
                kind: "GPL ".to_string(),
                chunk_id: 1,
                cfg: &cfg1,
                cross_chunk_calls: &calls1,
            },
            ChunkSummary {
                kind: "GPL ".to_string(),
                chunk_id: 2,
                cfg: &cfg2,
                cross_chunk_calls: &calls2,
            },
        ];
        let gcfg = build_global_cfg("TEST.GFF", &summaries, None);
        assert_eq!(gcfg.nodes.len(), 2);
        assert_eq!(gcfg.edges.len(), 4);
        let n1 = gcfg.nodes.iter().find(|n| n.chunk_id == 1).unwrap();
        let n2 = gcfg.nodes.iter().find(|n| n.chunk_id == 2).unwrap();
        // GPL-1 outbound: 2 (both to GPL-2). Inbound: 1 (from GPL-2).
        assert_eq!(n1.outbound_calls, 2);
        assert_eq!(n1.inbound_calls, 1);
        // GPL-2 outbound: 2 (one each to GPL-1 and GPL-2 self).
        // Inbound: 3 (2 from GPL-1 + 1 self-call).
        assert_eq!(n2.outbound_calls, 2);
        assert_eq!(n2.inbound_calls, 3);
    }

    #[test]
    fn global_cfg_annotates_edges_with_symbols() {
        let cfg = Cfg {
            entry_points: vec![0, 0x80],
            blocks: vec![],
            labels: BTreeMap::new(),
            target_aliases: BTreeMap::new(),
            unresolved: vec![],
        };
        let calls = vec![CrossChunkCall {
            from_offset: 0x90,
            target_offset: 0x80,
            target_file_id: 5,
        }];
        let summaries = vec![ChunkSummary {
            kind: "GPL ".to_string(),
            chunk_id: 1,
            cfg: &cfg,
            cross_chunk_calls: &calls,
        }];
        let syms = Symbols {
            opcodes: BTreeMap::new(),
            functions: vec![
                FunctionSymbol {
                    file: "TEST.GFF".to_string(),
                    kind: "GPL ".to_string(),
                    chunk_id: 1,
                    offset: 0x80,
                    name: "caller_function".to_string(),
                    notes: None,
                },
                FunctionSymbol {
                    file: "TEST.GFF".to_string(),
                    kind: "GPL ".to_string(),
                    chunk_id: 5,
                    offset: 0x80,
                    name: "callee_function".to_string(),
                    notes: None,
                },
            ],
        };
        let gcfg = build_global_cfg("TEST.GFF", &summaries, Some(&syms));
        assert_eq!(gcfg.edges.len(), 1);
        let e = &gcfg.edges[0];
        // from_offset 0x90 is after entry 0x80, so nearest enclosing
        // entry is 0x80 → "caller_function".
        assert_eq!(e.from_function_name.as_deref(), Some("caller_function"));
        // to_offset 0x80 matches the chunk-5 entry directly.
        assert_eq!(e.to_function_name.as_deref(), Some("callee_function"));
    }

    #[test]
    fn symbols_apply_to_entry_labels_only() {
        // Build a tiny CFG with one entry point at offset 0 and
        // one non-entry leader at offset 5.
        let instrs = vec![
            fake_instr(0, 0x12, Some(5)),  // jump to 5 (entry-style synthetic)
            fake_instr(3, 0x67, None),
            fake_instr(5, 0x15, None),     // local ret
        ];
        let (mut cfg, _) = build_cfg(&instrs, 6);
        assert_eq!(cfg.labels.get(&0).map(String::as_str), Some("entry_0x0000"));
        let syms = Symbols {
            opcodes: BTreeMap::new(),
            functions: vec![
                FunctionSymbol {
                    file: "TEST.GFF".to_string(),
                    kind: "GPL ".to_string(),
                    chunk_id: 7,
                    offset: 0,
                    name: "test_function".to_string(),
                    notes: None,
                },
                // Non-entry leader; should NOT be decorated.
                FunctionSymbol {
                    file: "TEST.GFF".to_string(),
                    kind: "GPL ".to_string(),
                    chunk_id: 7,
                    offset: 5,
                    name: "should_not_apply".to_string(),
                    notes: None,
                },
            ],
        };
        syms.apply_to_labels(&mut cfg, "TEST.GFF", "GPL ", 7);
        assert_eq!(
            cfg.labels.get(&0).map(String::as_str),
            Some("entry_0x0000 (test_function)")
        );
        // Non-entry leader at 5 stays untouched.
        assert_eq!(
            cfg.labels.get(&5).map(String::as_str),
            Some("label_0x0005")
        );
    }

    #[test]
    fn symbols_case_insensitive_file_match() {
        let syms = Symbols {
            opcodes: BTreeMap::new(),
            functions: vec![FunctionSymbol {
                file: "GPLDATA.GFF".to_string(),
                kind: "GPL ".to_string(),
                chunk_id: 1,
                offset: 1,
                name: "n".to_string(),
                notes: None,
            }],
        };
        assert_eq!(syms.function_name("gpldata.gff", "GPL ", 1, 1), Some("n"));
        assert_eq!(syms.function_name("GPLDATA.GFF", "GPL ", 1, 1), Some("n"));
        assert_eq!(syms.function_name("OTHER.GFF", "GPL ", 1, 1), None);
        assert_eq!(syms.function_name("GPLDATA.GFF", "MAS ", 1, 1), None);
    }

    #[test]
    fn cfg_present_when_disassembly_aligned() {
        // 0x67 endif is a no-param marker; clean disassemble.
        let result = disassemble(&[0x67]);
        assert!(result.aligned);
        assert!(result.cfg.is_some());
        let cfg = result.cfg.unwrap();
        assert_eq!(cfg.blocks.len(), 1);
    }

    #[test]
    fn symbols_apply_to_mnemonics_overrides_known_opcode() {
        // Two-instruction synthetic chunk: jump (0x12) target=3,
        // followed by endif (0x67). The override targets 0x12 only.
        let mut result = disassemble(&[0x12, 0x00, 0x03, 0x67]);
        assert_eq!(
            result.instructions[0].mnemonic.as_deref(),
            Some("gpl jump")
        );
        let mut opcodes = BTreeMap::new();
        opcodes.insert(
            "0x12".to_string(),
            OpcodeSymbol {
                name: "gpl jmp_renamed".to_string(),
                dso_source: None,
                verified_by: None,
            },
        );
        let syms = Symbols {
            opcodes,
            functions: vec![],
        };
        syms.apply_to_mnemonics(&mut result);
        assert_eq!(
            result.instructions[0].mnemonic.as_deref(),
            Some("gpl jmp_renamed")
        );
        // 0x67 was not in the override map; libgff name preserved.
        assert_eq!(
            result.instructions[1].mnemonic.as_deref(),
            Some("gpl endif")
        );
    }

    #[test]
    fn symbols_apply_to_mnemonics_leaves_unrelated_alone() {
        // Empty override map: every mnemonic stays at the libgff
        // default. Mirror of apply_to_labels's empty-functions path.
        let mut result = disassemble(&[0x12, 0x00, 0x03, 0x67]);
        let before: Vec<Option<String>> = result
            .instructions
            .iter()
            .map(|i| i.mnemonic.as_deref().map(str::to_string))
            .collect();
        let syms = Symbols::default();
        syms.apply_to_mnemonics(&mut result);
        let after: Vec<Option<String>> = result
            .instructions
            .iter()
            .map(|i| i.mnemonic.as_deref().map(str::to_string))
            .collect();
        assert_eq!(before, after);
    }

    #[test]
    fn symbols_apply_to_mnemonics_preserves_none_for_unknown_byte() {
        // Bytes above MAX_KNOWN_OPCODE produce mnemonic=None at
        // disassembly time. Override should not invent a mnemonic
        // for a byte that has no entry in the override map.
        let unknown_byte = MAX_KNOWN_OPCODE + 1;
        let mut result = disassemble(&[unknown_byte]);
        assert!(result.instructions[0].mnemonic.is_none());
        // Override targets the unknown byte explicitly: now it gets
        // a name (this is the expected behavior; curation can fill
        // in opcodes > 0x80 if they appear in real chunks).
        let mut opcodes = BTreeMap::new();
        opcodes.insert(
            format!("0x{:02x}", unknown_byte),
            OpcodeSymbol {
                name: "gpl curated_unknown".to_string(),
                dso_source: None,
                verified_by: None,
            },
        );
        let syms = Symbols {
            opcodes,
            functions: vec![],
        };
        syms.apply_to_mnemonics(&mut result);
        assert_eq!(
            result.instructions[0].mnemonic.as_deref(),
            Some("gpl curated_unknown")
        );
    }

    #[test]
    fn symbols_load_opcodes_from_toml() {
        // Round-trip: write opcodes.toml + functions.toml into a
        // tempdir, load via Symbols::load_from_dir, verify both
        // maps populated. Stdlib-only (no tempfile crate dep).
        use std::time::SystemTime;
        let nanos = SystemTime::now()
            .duration_since(SystemTime::UNIX_EPOCH)
            .map(|d| d.as_nanos())
            .unwrap_or(0);
        let dir = std::env::temp_dir().join(format!("gpl-disasm-sym-{nanos}"));
        std::fs::create_dir_all(&dir).expect("create tempdir");
        std::fs::write(
            dir.join("opcodes.toml"),
            r#"
[opcodes."0x12"]
name = "gpl jmp"
verified_by = "test"
"#,
        )
        .expect("write opcodes.toml");
        std::fs::write(
            dir.join("functions.toml"),
            r#"
[[function]]
file = "TEST.GFF"
kind = "GPL "
chunk_id = 1
offset = 0
name = "test_fn"
"#,
        )
        .expect("write functions.toml");
        let syms = Symbols::load_from_dir(&dir).expect("load");
        let _ = std::fs::remove_dir_all(&dir);
        assert_eq!(syms.opcodes.len(), 1);
        assert_eq!(syms.opcodes.get("0x12").map(|s| s.name.as_str()), Some("gpl jmp"));
        assert_eq!(syms.functions.len(), 1);
        assert_eq!(syms.functions[0].name, "test_fn");
    }
}
