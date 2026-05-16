//! Text-listing parser. Consumes the per-line output of
//! `gpl-disasm` (the default labelled form OR `--no-labels`)
//! and produces a [`DisasmResult`] that the encoder can
//! re-emit.
//!
//! v0.2.1 adds two pieces over v0.2.0's --no-labels-only
//! support:
//!
//! - **Label declarations**: lines ending with `:` of the form
//!   `label_0xNNNN:` or `entry_0xNNNN[ (function_name)]:` are
//!   pre-scanned and collected as a name -> offset map. Branch
//!   params that name a label resolve through the map.
//! - **`; raw_tail=HEX` trailers**: the disassembler emits this
//!   on `gpl_search` instructions in v0.4.6+; the parser reads
//!   the hex and reconstructs `Instruction.raw_tail`, closing
//!   the text-format round-trip on Search-containing chunks.
//!
//! The parser is deliberately strict: it accepts the exact
//! format `gpl-disasm` produces, not arbitrary human-friendly
//! variations. Modder workflow is disasm -> edit values ->
//! reassemble.

use gpl_disasm::{
    DisasmResult, EXTENDED_VAR, Expression, GPL_GBIGNUM, GPL_GBYTE, GPL_GFLAG, GPL_GNAME,
    GPL_GNUM, GPL_GSTRING, GPL_LBIGNUM, GPL_LBYTE, GPL_LFLAG, GPL_LNAME, GPL_LNUM, GPL_LSTRING,
    Instruction, MAX_KNOWN_OPCODE, Op, OPCODES, PARAM_COUNTS, ParamSpec, StringSubType, VarKind,
    opcode_name,
};
use std::borrow::Cow;
use std::collections::HashMap;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum ParseError {
    #[error("line {line}: expected 4-hex offset at column 0")]
    MissingOffset { line: usize },
    #[error("line {line}: bad offset {got:?}")]
    BadOffset { line: usize, got: String },
    #[error("line {line}: expected 2-hex opcode at column 6")]
    MissingOpcode { line: usize },
    #[error("line {line}: bad opcode {got:?}")]
    BadOpcode { line: usize, got: String },
    #[error("line {line}: column 10 expected mnemonic, got nothing")]
    MissingMnemonic { line: usize },
    #[error("line {line}: opcode 0x{opcode:02x} expects {expected} params, found {found}")]
    ParamCount {
        line: usize,
        opcode: u8,
        expected: String,
        found: usize,
    },
    #[error("line {line}: failed to parse expression token at {position:?}: {detail}")]
    BadExpression {
        line: usize,
        position: String,
        detail: String,
    },
    #[error("line {line}: opcode 0x{opcode:02x} ({mnemonic}) is not supported by the v0.2.0 text parser ({reason})")]
    UnsupportedOpcode {
        line: usize,
        opcode: u8,
        mnemonic: String,
        reason: &'static str,
    },
}

pub type Result<T> = std::result::Result<T, ParseError>;

/// Parse a text-format disassembly listing into a
/// [`DisasmResult`]. The result has `cfg = None` and
/// `cross_chunk_calls = []` — the parser builds an instruction
/// list, not a CFG.
///
/// Two passes:
/// 1. Pre-scan for `label_0xNNNN:` / `entry_0xNNNN[ (...)]:`
///    declarations; build a `name -> offset` map.
/// 2. Parse each instruction line. Branch-param tokens that
///    name a label resolve to `Immediate14 { value: offset }`.
///    Lines with a `; raw_tail=HEX` trailer set the parsed
///    Instruction's `raw_tail` field.
pub fn parse(input: &str) -> Result<DisasmResult> {
    let labels = collect_labels(input);
    let mut instructions: Vec<Instruction> = Vec::new();
    let mut total_bytes = 0usize;
    for (i, raw_line) in input.lines().enumerate() {
        let line_no = i + 1;
        let line = raw_line.trim_end();
        if line.is_empty() {
            continue;
        }
        if line.starts_with(';') {
            // Standalone comment / footer line; not attached to
            // an instruction (we strip per-instruction trailers
            // separately).
            continue;
        }
        if line.ends_with(':') {
            // Label declaration line — collected by the pre-scan,
            // no semantic effect on the instruction stream.
            continue;
        }
        let instr = parse_instruction_line(line, line_no, &labels)?;
        total_bytes += instr.length;
        instructions.push(instr);
    }
    Ok(DisasmResult {
        instructions,
        bytes_consumed: total_bytes,
        total_bytes,
        aligned: true,
        cfg: None,
        cross_chunk_calls: Vec::new(),
    })
}

/// Pre-scan pass: find every line of the form `label_0xNNNN:`,
/// `entry_0xNNNN:`, or `entry_0xNNNN (function_name):`. Build a
/// `bare-name -> offset` map; the function-name decoration is
/// dropped because the branch-param renderer strips it too
/// (gpl-disasm v0.4.6+).
fn collect_labels(input: &str) -> HashMap<String, usize> {
    let mut out: HashMap<String, usize> = HashMap::new();
    for raw_line in input.lines() {
        let line = raw_line.trim();
        let Some(stripped) = line.strip_suffix(':') else {
            continue;
        };
        // Bare name: take everything up to the first `(` or
        // whitespace. `entry_0x0001 (iniya_first_meeting):` ->
        // `entry_0x0001`. `label_0x0011:` -> `label_0x0011`.
        let bare = stripped
            .split_once(' ')
            .map(|(l, _)| l)
            .unwrap_or(stripped);
        if !(bare.starts_with("label_0x") || bare.starts_with("entry_0x")) {
            continue;
        }
        let hex = &bare[bare.len() - 4..];
        if let Ok(offset) = usize::from_str_radix(hex, 16) {
            out.insert(bare.to_string(), offset);
        }
    }
    out
}

fn parse_instruction_line(
    line: &str,
    line_no: usize,
    labels: &HashMap<String, usize>,
) -> Result<Instruction> {
    // Layout: "OOOO  HH  MNEMONIC               <params>  ; trailer"
    //         0   4 6  8 10                     (variable)
    // The mnemonic field is left-padded to 22 chars (gpl-disasm's
    // Display impl): `{:04x}  {:02x}  {:<22}`. After that, params
    // start with the literal two-space separator `"  "`.
    if line.len() < 10 {
        return Err(ParseError::MissingOffset { line: line_no });
    }
    let offset_str = &line[0..4];
    let offset = usize::from_str_radix(offset_str, 16).map_err(|_| ParseError::BadOffset {
        line: line_no,
        got: offset_str.to_string(),
    })?;
    if &line[4..6] != "  " {
        return Err(ParseError::MissingOffset { line: line_no });
    }
    let opcode_str = &line[6..8];
    let opcode = u8::from_str_radix(opcode_str, 16).map_err(|_| ParseError::BadOpcode {
        line: line_no,
        got: opcode_str.to_string(),
    })?;
    if &line[8..10] != "  " {
        return Err(ParseError::MissingOpcode { line: line_no });
    }

    // The mnemonic + params area is the rest of the line.
    let rest = &line[10..];
    // Strip the comment trailer (best-effort / string-run /
    // raw_tail). GPL strings can contain `;` but our string
    // tokens are in escaped form (`\"` surrounds them), so we
    // split conservatively by looking for `  ; ` outside of
    // quoted regions.
    let (params_area, trailer) = split_trailer(rest);
    let raw_tail = trailer.and_then(parse_raw_tail_trailer);

    // Now parse the mnemonic + params area. The mnemonic is left-
    // padded to 22 chars. The rest may begin with two-space
    // separator before params.
    if params_area.len() < 22 {
        // Some short mnemonics may have trailing spaces; the line
        // could be shorter if there are no params. Just take the
        // whole rest as mnemonic, no params.
        let _mnemonic = params_area.trim_end();
        return Ok(Instruction {
            offset,
            length: instruction_length(opcode, &[], raw_tail.as_deref()),
            opcode,
            mnemonic: opcode_name(opcode).map(Cow::Borrowed),
            params: vec![],
            best_effort: false,
            string_run: None,
            raw_tail,
        });
    }
    // The format string `{:<22}` left-pads to 22 chars. Mnemonic
    // is `params_area[..22].trim_end()`. After char 22, params
    // start (if any).
    let _mnemonic = params_area[..22].trim_end();
    let params_str = if params_area.len() > 22 {
        &params_area[22..]
    } else {
        ""
    };

    // The first param is preceded by `"  "` (two spaces) per the
    // Display impl: `for (i, param) in params.iter().enumerate()
    // { write!(f, "{}", if i == 0 { "  " } else { ", " })?; }`.
    let params_str = params_str.trim_start();

    let params = if params_str.is_empty() {
        vec![]
    } else {
        parse_params(params_str, opcode, line_no, labels)?
    };

    Ok(Instruction {
        offset,
        length: instruction_length(opcode, &params, raw_tail.as_deref()),
        opcode,
        mnemonic: opcode_name(opcode).map(Cow::Borrowed),
        params,
        best_effort: false,
        string_run: None,
        raw_tail,
    })
}

/// Parse a `; raw_tail=HEX` trailer's hex payload into bytes.
/// Returns `None` for trailers that aren't a raw_tail
/// annotation (e.g. `best-effort`, `"string"`).
fn parse_raw_tail_trailer(trailer: &str) -> Option<Vec<u8>> {
    let body = trailer.trim_start();
    let hex = body.strip_prefix("raw_tail=")?;
    // Hex digits only, up to whitespace / end.
    let end = hex.find(|c: char| !c.is_ascii_hexdigit()).unwrap_or(hex.len());
    let hex = &hex[..end];
    if hex.is_empty() || hex.len() % 2 != 0 {
        return None;
    }
    let mut out = Vec::with_capacity(hex.len() / 2);
    for i in (0..hex.len()).step_by(2) {
        out.push(u8::from_str_radix(&hex[i..i + 2], 16).ok()?);
    }
    Some(out)
}

/// Split a line's "rest" portion into (params_area, trailer)
/// using the `"  ; "` marker. Quoted strings inside the params
/// area can contain `;`, but the escape rules mean `"` is
/// represented as `\"` inside the string content; a literal
/// closing `"` always marks the end of a token. So we can scan
/// linearly, tracking whether we're inside a string token.
fn split_trailer(rest: &str) -> (&str, Option<&str>) {
    let bytes = rest.as_bytes();
    let mut in_string = false;
    let mut i = 0;
    while i < bytes.len() {
        let b = bytes[i];
        if b == b'\\' && in_string && i + 1 < bytes.len() {
            i += 2;
            continue;
        }
        if b == b'"' {
            in_string = !in_string;
        } else if !in_string
            && b == b';'
            && i >= 2
            && bytes[i - 2] == b' '
            && bytes[i - 1] == b' '
        {
            return (&rest[..i - 2], Some(&rest[i + 1..]));
        }
        i += 1;
    }
    (rest, None)
}

/// Recompute an instruction's `length` from the encoded form.
/// We can't borrow `gpl_asm::encode_instruction` here without a
/// circular dependency, so we estimate: 1 byte for opcode + sum
/// of each Expression's byte width.
fn instruction_length(opcode: u8, params: &[Vec<Expression>], raw_tail: Option<&[u8]>) -> usize {
    let mut len = 1usize;
    let spec = if (opcode as usize) <= MAX_KNOWN_OPCODE as usize {
        PARAM_COUNTS[opcode as usize]
    } else {
        ParamSpec::None
    };
    for (i, p) in params.iter().enumerate() {
        for tok in p {
            len += expression_byte_len(tok);
        }
        match spec {
            ParamSpec::LoadVar if i == 1 => {
                // The datatype byte; encoder writes it but the
                // Variable/ComplexAccess token's bytes don't
                // include it directly. Subtract because we'd
                // double-count.
                // Actually, we add 1 byte for the dispatch byte;
                // for Variable that's the typed-byte (already
                // counted in expression_byte_len). For
                // ComplexAccess that's also the dispatch byte
                // (already counted). So no adjustment.
            }
            _ => {}
        }
    }
    if let ParamSpec::Menu = spec {
        len += 1; // 0x4A terminator
    }
    if let Some(tail) = raw_tail {
        len += tail.len();
    }
    len
}

/// Byte length of one Expression token's encoded form.
fn expression_byte_len(expr: &Expression) -> usize {
    match expr {
        Expression::Immediate14 { .. } => 2,
        Expression::ImmediateByte { .. } => 2,
        Expression::ImmediateBigNum { .. } => 5,
        Expression::ImmediateName { .. } => 3,
        Expression::ImmediateString { sub_type, value } => match sub_type {
            StringSubType::Introduce | StringSubType::Uncompressed => 2,
            StringSubType::Compressed => {
                // marker (1) + STRING_COMPRESSED (1) +
                // ceil(((chars + 1) * 7) / 8) bytes for the
                // bitstream.
                let bits = (value.chars().count() + 1) * 7;
                1 + 1 + bits.div_ceil(8)
            }
        },
        Expression::Variable { extended, .. } => 1 + if *extended { 2 } else { 1 },
        Expression::BinaryOp { .. } => 1,
        Expression::OpenParen | Expression::CloseParen => 1,
        Expression::RetVal { inner_params, .. } => {
            let mut n = 2; // 0x8C + inner_opcode
            for p in inner_params {
                for tok in p {
                    n += expression_byte_len(tok);
                }
            }
            n
        }
        Expression::ComplexAccess { elements, .. } => 1 + 2 + 1 + elements.len(),
        Expression::AccmError => 1,
        Expression::ImmediWordUnimplemented => 1,
        Expression::Unknown { .. } => 1,
    }
}

/// Parse the params region of an instruction line for an opcode
/// of known `opcode`. Splits on commas at the top level (not
/// inside parens, quotes, or brackets) then parses each part as
/// a single param (a sequence of Expression tokens).
fn parse_params(
    s: &str,
    opcode: u8,
    line_no: usize,
    labels: &HashMap<String, usize>,
) -> Result<Vec<Vec<Expression>>> {
    let parts = split_top_level_commas(s);
    let mut params: Vec<Vec<Expression>> = Vec::with_capacity(parts.len());
    for part in parts {
        let tokens = parse_param_tokens(part.trim(), line_no, labels)?;
        params.push(tokens);
    }

    let spec = if (opcode as usize) <= MAX_KNOWN_OPCODE as usize {
        PARAM_COUNTS[opcode as usize]
    } else {
        ParamSpec::None
    };
    match spec {
        ParamSpec::Fixed(n) if params.len() != n as usize => {
            return Err(ParseError::ParamCount {
                line: line_no,
                opcode,
                expected: n.to_string(),
                found: params.len(),
            });
        }
        ParamSpec::Search => {
            // Search needs the caller to also have parsed a
            // `; raw_tail=HEX` trailer (gpl-disasm v0.4.6+).
            // We can't verify that here without re-plumbing,
            // so we accept any number of params; the encoder
            // will surface a clear error if raw_tail is None.
        }
        ParamSpec::Custom => {
            return Err(ParseError::UnsupportedOpcode {
                line: line_no,
                opcode,
                mnemonic: opcode_name(opcode).unwrap_or("?").to_string(),
                reason: "Custom-shape opcodes not in v0.2.0",
            });
        }
        _ => {}
    }
    Ok(params)
}

/// Split `s` on `", "` at the top level (not inside parens,
/// brackets, or quoted strings).
fn split_top_level_commas(s: &str) -> Vec<&str> {
    let bytes = s.as_bytes();
    let mut parts: Vec<&str> = Vec::new();
    let mut depth_paren = 0i32;
    let mut depth_bracket = 0i32;
    let mut in_string = false;
    let mut start = 0usize;
    let mut i = 0usize;
    while i < bytes.len() {
        let b = bytes[i];
        if in_string {
            if b == b'\\' && i + 1 < bytes.len() {
                i += 2;
                continue;
            }
            if b == b'"' {
                in_string = false;
            }
            i += 1;
            continue;
        }
        match b {
            b'"' => in_string = true,
            b'(' => depth_paren += 1,
            b')' => depth_paren -= 1,
            b'[' => depth_bracket += 1,
            b']' => depth_bracket -= 1,
            b',' if depth_paren <= 0 && depth_bracket <= 0 => {
                parts.push(&s[start..i]);
                // Skip the space after the comma if present.
                let mut next = i + 1;
                while next < bytes.len() && bytes[next] == b' ' {
                    next += 1;
                }
                start = next;
                i = next;
                continue;
            }
            _ => {}
        }
        i += 1;
    }
    if start < bytes.len() {
        parts.push(&s[start..]);
    }
    parts
}

/// Parse a single parameter — a sequence of [`Expression`]
/// tokens — from its rendered form.
fn parse_param_tokens(
    s: &str,
    line_no: usize,
    labels: &HashMap<String, usize>,
) -> Result<Vec<Expression>> {
    let mut tokens = Vec::new();
    let mut rest = s;
    // `prev_was_value` mirrors the renderer's tracking of the
    // same name. When true, the next `-DIGIT` is an operator
    // followed by a positive value, NOT a signed literal. (Inside
    // the unspaced RetVal rendering, `GNAME[33]-2i8` is three
    // tokens; with a leading space it'd be `GNAME[33] - 2i8`.)
    let mut prev_was_value = false;
    while !rest.is_empty() {
        rest = rest.trim_start();
        if rest.is_empty() {
            break;
        }
        let (tok, consumed) = parse_one_expression(rest, line_no, labels, prev_was_value)?;
        let is_open = matches!(tok, Expression::OpenParen);
        let is_op = matches!(tok, Expression::BinaryOp { .. });
        prev_was_value = !is_open && !is_op;
        tokens.push(tok);
        rest = &rest[consumed..];
    }
    Ok(tokens)
}

/// Parse a single Expression token; return it plus the byte
/// count of `s` consumed.
fn parse_one_expression(
    s: &str,
    line_no: usize,
    labels: &HashMap<String, usize>,
    prev_was_value: bool,
) -> Result<(Expression, usize)> {
    let bytes = s.as_bytes();
    if bytes.is_empty() {
        return Err(ParseError::BadExpression {
            line: line_no,
            position: "<eof>".to_string(),
            detail: "empty".to_string(),
        });
    }

    // Single-byte tokens first.
    if bytes[0] == b'(' {
        return Ok((Expression::OpenParen, 1));
    }
    if bytes[0] == b')' {
        return Ok((Expression::CloseParen, 1));
    }

    // Binary operators (rendered between values with surrounding
    // spaces; trimmed input may start with the symbol).
    if let Some((op, n)) = try_parse_binary_op(s, prev_was_value) {
        return Ok((Expression::BinaryOp { op }, n));
    }

    // Label-form branch target: `label_0xNNNN` or
    // `entry_0xNNNN` resolves through the pre-scanned labels
    // map to an `Immediate14` with the target byte offset.
    if let Some((tok, n)) = try_parse_label_ref(s, labels) {
        return Ok((tok, n));
    }

    // String literals start with `"`.
    if bytes[0] == b'"' {
        return parse_compressed_string(s, line_no);
    }

    // INTRODUCE / UNCOMPRESSED markers.
    if let Some(rest) = s.strip_prefix("INTRODUCE") {
        return Ok((
            Expression::ImmediateString {
                sub_type: StringSubType::Introduce,
                value: "<active_character_name>".to_string(),
            },
            s.len() - rest.len(),
        ));
    }
    if let Some(rest) = s.strip_prefix("UNCOMPRESSED") {
        return Ok((
            Expression::ImmediateString {
                sub_type: StringSubType::Uncompressed,
                value: "<uncompressed; decoder not implemented>".to_string(),
            },
            s.len() - rest.len(),
        ));
    }
    if let Some(rest) = s.strip_prefix("ACCM_ERROR") {
        return Ok((Expression::AccmError, s.len() - rest.len()));
    }
    if let Some(rest) = s.strip_prefix("IMMED_WORD_UNIMPL") {
        return Ok((Expression::ImmediWordUnimplemented, s.len() - rest.len()));
    }

    // NAME(value)
    if let Some(rest) = s.strip_prefix("NAME(") {
        let end = rest.find(')').ok_or_else(|| ParseError::BadExpression {
            line: line_no,
            position: s.chars().take(20).collect(),
            detail: "unterminated NAME(...)".to_string(),
        })?;
        let value: i32 = rest[..end].parse().map_err(|e| ParseError::BadExpression {
            line: line_no,
            position: rest[..end].to_string(),
            detail: format!("NAME value: {e}"),
        })?;
        return Ok((
            Expression::ImmediateName { value },
            s.len() - rest.len() + end + 1,
        ));
    }

    // RETVAL(mnemonic params)
    if let Some(after_open) = s.strip_prefix("RETVAL(") {
        return parse_retval(s, after_open, line_no, labels);
    }

    // COMPLEX(0xNN, ctx, depth=D, [e0,e1,...])
    if let Some(after_open) = s.strip_prefix("COMPLEX(") {
        return parse_complex(s, after_open, line_no);
    }

    // Variable: SHORT[id] or SHORT+[id] (longest-match short name).
    if let Some((vk, extended, id, n)) = try_parse_variable(s) {
        return Ok((
            Expression::Variable {
                var_kind: vk,
                id,
                extended,
            },
            n,
        ));
    }

    // ??0xNN unknown.
    if let Some(rest) = s.strip_prefix("??0x") {
        let hex: String = rest.chars().take(2).collect();
        let byte = u8::from_str_radix(&hex, 16).map_err(|e| ParseError::BadExpression {
            line: line_no,
            position: hex.clone(),
            detail: format!("Unknown byte: {e}"),
        })?;
        return Ok((Expression::Unknown { byte }, s.len() - rest.len() + hex.len()));
    }

    // Integer immediates: try BigNum (i32), then Byte (i8), then 14-bit.
    parse_integer_immediate(s, line_no)
}

fn parse_compressed_string(s: &str, line_no: usize) -> Result<(Expression, usize)> {
    // Walk forward unescaping until we hit the closing `"`.
    let bytes = s.as_bytes();
    if bytes[0] != b'"' {
        return Err(ParseError::BadExpression {
            line: line_no,
            position: s.chars().take(8).collect(),
            detail: "string literal must start with \"".to_string(),
        });
    }
    let mut value = String::new();
    let mut i = 1usize;
    while i < bytes.len() {
        let b = bytes[i];
        if b == b'\\' && i + 1 < bytes.len() {
            let nx = bytes[i + 1];
            let ch = match nx {
                b'\\' => '\\',
                b'\"' => '"',
                b'n' => '\n',
                b'r' => '\r',
                b't' => '\t',
                b'x' if i + 3 < bytes.len() => {
                    let hex = &s[i + 2..i + 4];
                    let v =
                        u8::from_str_radix(hex, 16).map_err(|e| ParseError::BadExpression {
                            line: line_no,
                            position: hex.to_string(),
                            detail: format!("string \\x escape: {e}"),
                        })?;
                    value.push(v as char);
                    i += 4;
                    continue;
                }
                other => {
                    return Err(ParseError::BadExpression {
                        line: line_no,
                        position: format!("\\{}", other as char),
                        detail: "unknown escape".to_string(),
                    });
                }
            };
            value.push(ch);
            i += 2;
            continue;
        }
        if b == b'"' {
            // Closing quote.
            return Ok((
                Expression::ImmediateString {
                    sub_type: StringSubType::Compressed,
                    value,
                },
                i + 1,
            ));
        }
        // Multi-byte UTF-8: take whole codepoint.
        let ch_start = i;
        let ch = s[ch_start..]
            .chars()
            .next()
            .ok_or_else(|| ParseError::BadExpression {
                line: line_no,
                position: s.chars().take(8).collect(),
                detail: "unexpected end inside string".to_string(),
            })?;
        value.push(ch);
        i += ch.len_utf8();
    }
    Err(ParseError::BadExpression {
        line: line_no,
        position: s.chars().take(20).collect(),
        detail: "unterminated string literal".to_string(),
    })
}

fn parse_retval(
    s: &str,
    body: &str,
    line_no: usize,
    labels: &HashMap<String, usize>,
) -> Result<(Expression, usize)> {
    // body starts after `RETVAL(`. The first whitespace-delimited
    // token is the mnemonic (e.g. "gpl rand"), then optional
    // space-separated args. We need to find the matching `)`.
    // The mnemonic itself contains spaces, so we can't split on
    // whitespace naively.
    //
    // gpl-disasm's Display emits: RETVAL(MNEMONIC [param0_tokens
    // separated by spaces][, param1_tokens][, ...])
    //
    // We scan to find the matching `)` (tracking paren depth +
    // string state), then split the contents into mnemonic +
    // params.
    let bytes = body.as_bytes();
    let mut depth = 1i32;
    let mut in_string = false;
    let mut i = 0usize;
    while i < bytes.len() {
        let b = bytes[i];
        if in_string {
            if b == b'\\' && i + 1 < bytes.len() {
                i += 2;
                continue;
            }
            if b == b'"' {
                in_string = false;
            }
            i += 1;
            continue;
        }
        match b {
            b'"' => in_string = true,
            b'(' => depth += 1,
            b')' => {
                depth -= 1;
                if depth == 0 {
                    let inner = &body[..i];
                    let consumed = (s.len() - body.len()) + i + 1;
                    return parse_retval_inner(inner, consumed, line_no, labels);
                }
            }
            _ => {}
        }
        i += 1;
    }
    Err(ParseError::BadExpression {
        line: line_no,
        position: s.chars().take(20).collect(),
        detail: "unterminated RETVAL(...)".to_string(),
    })
}

fn parse_retval_inner(
    inner: &str,
    consumed: usize,
    line_no: usize,
    labels: &HashMap<String, usize>,
) -> Result<(Expression, usize)> {
    // Find the mnemonic: the longest prefix of `inner` that
    // matches an `OPCODES[i]` entry. We try every opcode name in
    // order from longest to shortest and pick the first match.
    let mut indexed_names: Vec<(usize, &&str)> = OPCODES.iter().enumerate().collect();
    indexed_names.sort_by_key(|&(_, name)| std::cmp::Reverse(name.len()));
    let mut found: Option<(u8, usize)> = None;
    for (idx, name) in &indexed_names {
        if inner.starts_with(*name) {
            let next = inner.len() > name.len();
            let next_is_sep = if next {
                let c = inner.as_bytes()[name.len()];
                c == b' ' || c == b','
            } else {
                true
            };
            if next_is_sep {
                found = Some((*idx as u8, name.len()));
                break;
            }
        }
    }
    let (inner_opcode, name_len) = found.ok_or_else(|| ParseError::BadExpression {
        line: line_no,
        position: inner.chars().take(30).collect(),
        detail: "RETVAL mnemonic doesn't match any OPCODES entry".to_string(),
    })?;

    // After the mnemonic, there may be a single space + the
    // params. The renderer writes " " before the first param-
    // token and ", " between params. For nested `gpl_search`,
    // a ` raw_tail=HEX` sentinel may appear after the params
    // (gpl-disasm v0.4.6+); split that off first.
    let after_mn = &inner[name_len..];
    let (params_part, inner_raw_tail) = split_retval_raw_tail(after_mn);
    let params_str = params_part.trim_start();
    let inner_params = if params_str.is_empty() {
        vec![]
    } else {
        let parts = split_top_level_commas(params_str);
        let mut out = Vec::with_capacity(parts.len());
        for p in parts {
            out.push(parse_param_tokens(p.trim(), line_no, labels)?);
        }
        out
    };
    Ok((
        Expression::RetVal {
            inner_opcode,
            inner_mnemonic: opcode_name(inner_opcode).map(Cow::Borrowed),
            inner_params,
            inner_raw_tail,
        },
        consumed,
    ))
}

/// Split a RETVAL's inner content (after the mnemonic) into
/// `(params_part, Option<inner_raw_tail>)`. The sentinel is
/// ` raw_tail=HEX`, appearing at the end after the params.
fn split_retval_raw_tail(after_mn: &str) -> (&str, Option<Vec<u8>>) {
    let Some(marker_idx) = after_mn.rfind(" raw_tail=") else {
        return (after_mn, None);
    };
    let hex = &after_mn[marker_idx + " raw_tail=".len()..];
    let end = hex.find(|c: char| !c.is_ascii_hexdigit()).unwrap_or(hex.len());
    let hex = &hex[..end];
    if hex.is_empty() || hex.len() % 2 != 0 {
        return (after_mn, None);
    }
    let mut bytes = Vec::with_capacity(hex.len() / 2);
    for i in (0..hex.len()).step_by(2) {
        match u8::from_str_radix(&hex[i..i + 2], 16) {
            Ok(b) => bytes.push(b),
            Err(_) => return (after_mn, None),
        }
    }
    (&after_mn[..marker_idx], Some(bytes))
}

fn parse_complex(s: &str, body: &str, line_no: usize) -> Result<(Expression, usize)> {
    // body starts after `COMPLEX(`. Format:
    //   0xTT, CTX, depth=D[, [E0,E1,...]]
    // Find matching `)`.
    let bytes = body.as_bytes();
    let mut depth = 1i32;
    let mut in_string = false;
    let mut i = 0usize;
    while i < bytes.len() {
        let b = bytes[i];
        if in_string {
            if b == b'\\' && i + 1 < bytes.len() {
                i += 2;
                continue;
            }
            if b == b'"' {
                in_string = false;
            }
            i += 1;
            continue;
        }
        match b {
            b'"' => in_string = true,
            b'(' => depth += 1,
            b')' => {
                depth -= 1;
                if depth == 0 {
                    let inner = &body[..i];
                    let consumed = (s.len() - body.len()) + i + 1;
                    return parse_complex_inner(inner, consumed, line_no);
                }
            }
            _ => {}
        }
        i += 1;
    }
    Err(ParseError::BadExpression {
        line: line_no,
        position: s.chars().take(20).collect(),
        detail: "unterminated COMPLEX(...)".to_string(),
    })
}

fn parse_complex_inner(inner: &str, consumed: usize, line_no: usize) -> Result<(Expression, usize)> {
    // Split on top-level commas.
    let parts: Vec<&str> = split_top_level_commas(inner)
        .into_iter()
        .map(str::trim)
        .collect();
    if parts.len() < 3 {
        return Err(ParseError::BadExpression {
            line: line_no,
            position: inner.to_string(),
            detail: "COMPLEX needs at least tag,ctx,depth".to_string(),
        });
    }
    // tag = "0xTT"
    let tag_str = parts[0]
        .strip_prefix("0x")
        .ok_or_else(|| ParseError::BadExpression {
            line: line_no,
            position: parts[0].to_string(),
            detail: "COMPLEX tag missing 0x prefix".to_string(),
        })?;
    let tag = u8::from_str_radix(tag_str, 16).map_err(|e| ParseError::BadExpression {
        line: line_no,
        position: tag_str.to_string(),
        detail: format!("COMPLEX tag: {e}"),
    })?;
    // ctx = "POV" | "ACTIVE" | "PASSIVE" | "OTHER" | "OTHER1" |
    // "THING" | "?" | "id={N}"
    let obj_name: i32 = match parts[1] {
        "POV" => 0x8025_u32 as i32,
        "ACTIVE" => 0x8026_u32 as i32,
        "PASSIVE" => 0x8027_u32 as i32,
        "OTHER" => 0x8028_u32 as i32,
        "THING" => 0x802B_u32 as i32,
        "OTHER1" => 0x802C_u32 as i32,
        "?" => 0x8000_u32 as i32, // best-effort; we don't know the original tag value
        other => {
            let body = other.strip_prefix("id=").ok_or_else(|| ParseError::BadExpression {
                line: line_no,
                position: other.to_string(),
                detail: "COMPLEX ctx unknown".to_string(),
            })?;
            body.parse::<i32>().map_err(|e| ParseError::BadExpression {
                line: line_no,
                position: body.to_string(),
                detail: format!("COMPLEX id: {e}"),
            })?
        }
    };
    // depth=N
    let depth_str = parts[2]
        .strip_prefix("depth=")
        .ok_or_else(|| ParseError::BadExpression {
            line: line_no,
            position: parts[2].to_string(),
            detail: "COMPLEX expects depth=N".to_string(),
        })?;
    let depth: u8 = depth_str.parse().map_err(|e| ParseError::BadExpression {
        line: line_no,
        position: depth_str.to_string(),
        detail: format!("COMPLEX depth: {e}"),
    })?;
    // elements (optional): "[E0,E1,...]"
    let elements: Vec<u8> = if parts.len() > 3 {
        let inside = parts[3]
            .strip_prefix('[')
            .and_then(|s| s.strip_suffix(']'))
            .ok_or_else(|| ParseError::BadExpression {
                line: line_no,
                position: parts[3].to_string(),
                detail: "COMPLEX elements need [..] wrapping".to_string(),
            })?;
        let mut out = Vec::new();
        for e in inside.split(',') {
            let e = e.trim();
            if e.is_empty() {
                continue;
            }
            out.push(e.parse::<u8>().map_err(|err| ParseError::BadExpression {
                line: line_no,
                position: e.to_string(),
                detail: format!("COMPLEX element: {err}"),
            })?);
        }
        out
    } else {
        Vec::new()
    };
    Ok((
        Expression::ComplexAccess {
            tag,
            obj_name,
            depth,
            elements,
        },
        consumed,
    ))
}

/// Match a `label_0xNNNN` or `entry_0xNNNN` identifier at the
/// start of `s` and resolve it through `labels`. The match must
/// be the start of an identifier token (followed by EOI, space,
/// comma, or close-paren / close-bracket).
fn try_parse_label_ref(s: &str, labels: &HashMap<String, usize>) -> Option<(Expression, usize)> {
    if !(s.starts_with("label_0x") || s.starts_with("entry_0x")) {
        return None;
    }
    // Identifier ends at first non-identifier character. The
    // rendered bare name is letters + digits + underscore.
    let bytes = s.as_bytes();
    let mut i = 0usize;
    while i < bytes.len() {
        let b = bytes[i];
        if b.is_ascii_alphanumeric() || b == b'_' {
            i += 1;
        } else {
            break;
        }
    }
    let name = &s[..i];
    let offset = labels.get(name).copied()?;
    let value: u16 = offset.try_into().ok()?;
    Some((Expression::Immediate14 { value }, i))
}

fn try_parse_binary_op(s: &str, prev_was_value: bool) -> Option<(Op, usize)> {
    // Multi-char operators first (longest match wins).
    let candidates: &[(&str, Op)] = &[
        // Longest first to avoid prefix collisions: `&~` (Bclr)
        // must beat `&` (Band).
        ("&~", Op::Bclr),
        (">=", Op::GreaterEqual),
        ("<=", Op::LessEqual),
        ("==", Op::Equal),
        ("!=", Op::NotEqual),
        ("and", Op::And),
        ("or", Op::Or),
        ("+", Op::Add),
        ("-", Op::Minus),
        ("*", Op::Times),
        ("/", Op::Divide),
        (">", Op::Greater),
        ("<", Op::Less),
        ("&", Op::Band),
        ("|", Op::Bor),
    ];
    for (sym, op) in candidates {
        if let Some(rest) = s.strip_prefix(sym) {
            // `+` and `-` can also be the sign on a signed integer
            // literal (`-10i32`). Disambiguate by requiring a
            // trailing space (the top-level renderer wraps every
            // op in ` {op} `; a sign on an integer has the digit
            // immediately after). The RetVal Display impl in
            // `gpl-disasm` doesn't wrap ops in spaces, so for the
            // unambiguous operators (`==`, `<`, `>`, `&`, `|`,
            // `&~`, `*`, `/`, `==`, `!=`, `>=`, `<=`) we don't
            // require a trailing space.
            // Only `-` is sign-ambiguous. It's a sign on an
            // integer literal when (a) it's followed by a digit
            // AND (b) the parser is at a position where the
            // previous token was not a value (start of param,
            // after open-paren, or after an operator). After a
            // value-producing token, `-DIGIT` is op + positive
            // value. The renderer's spaced top-level form
            // (` - 10i8`) is handled implicitly because trimming
            // doesn't change the prev_was_value state.
            let next_is_digit = !rest.is_empty() && rest.as_bytes()[0].is_ascii_digit();
            let sign_ambiguous =
                matches!(*op, Op::Minus) && next_is_digit && !prev_was_value;
            // `and` / `or` need a word boundary after.
            let word_op = matches!(*op, Op::And | Op::Or);
            let next_ok = if sign_ambiguous {
                rest.is_empty() || rest.as_bytes()[0] == b' '
            } else if word_op {
                rest.is_empty()
                    || !(rest.as_bytes()[0].is_ascii_alphanumeric()
                        || rest.as_bytes()[0] == b'_')
            } else {
                true
            };
            if next_ok {
                return Some((*op, sym.len()));
            }
        }
    }
    None
}

fn try_parse_variable(s: &str) -> Option<(VarKind, bool, u16, usize)> {
    // Strict longest-first ordering to avoid prefix collisions.
    // `GBYTE` must beat `GB`/`GBN`; `GNAME` must beat `GN`;
    // `GBN` must beat `GF`/`GB`; etc.
    let candidates: &[(&str, VarKind)] = &[
        ("GBYTE", VarKind::Gbyte),
        ("LBYTE", VarKind::Lbyte),
        ("GNAME", VarKind::Gname),
        ("LNAME", VarKind::Lname),
        ("GSTR", VarKind::Gstring),
        ("LSTR", VarKind::Lstring),
        ("GNUM", VarKind::Gnum),
        ("LNUM", VarKind::Lnum),
        ("GBN", VarKind::Gbignum),
        ("LBN", VarKind::Lbignum),
        ("GF", VarKind::Gflag),
        ("LF", VarKind::Lflag),
    ];
    // ACCUM doesn't correspond to a Variable kind; the renderer
    // emits it for `VarKind::Accm` which isn't in the public enum
    // (the decoder treats `GPL_ACCM | 0x80` as AccmError). We
    // handle "ACCUM" as a separate token in the caller if needed;
    // here we just return None for it.
    let _ = (
        EXTENDED_VAR,
        GPL_LSTRING,
        GPL_LNUM,
        GPL_LBYTE,
        GPL_LNAME,
        GPL_LBIGNUM,
        GPL_GSTRING,
        GPL_GNUM,
        GPL_GBYTE,
        GPL_GNAME,
        GPL_GBIGNUM,
        GPL_GFLAG,
        GPL_LFLAG,
    );
    for (prefix, vk) in candidates {
        if let Some(rest) = s.strip_prefix(prefix) {
            let extended = rest.starts_with('+');
            let after_plus = if extended { &rest[1..] } else { rest };
            if let Some(after_open) = after_plus.strip_prefix('[') {
                if let Some(close_idx) = after_open.find(']') {
                    let id_str = &after_open[..close_idx];
                    if let Ok(id) = id_str.parse::<u16>() {
                        // Bytes consumed: prefix + optional `+` +
                        // `[` + id_str + `]`.
                        let consumed = prefix.len()
                            + (if extended { 1 } else { 0 })
                            + 1
                            + id_str.len()
                            + 1;
                        return Some((*vk, extended, id, consumed));
                    }
                }
            }
        }
    }
    None
}

fn parse_integer_immediate(s: &str, line_no: usize) -> Result<(Expression, usize)> {
    // Number-token characters: optional `-`, digits.
    let bytes = s.as_bytes();
    let mut i = 0usize;
    if i < bytes.len() && bytes[i] == b'-' {
        i += 1;
    }
    while i < bytes.len() && bytes[i].is_ascii_digit() {
        i += 1;
    }
    if i == 0 || (bytes[0] == b'-' && i == 1) {
        return Err(ParseError::BadExpression {
            line: line_no,
            position: s.chars().take(8).collect(),
            detail: "expected integer or known token".to_string(),
        });
    }
    let digits = &s[..i];
    // Look for type suffix.
    if let Some(rest_after_suffix) = s[i..].strip_prefix("i32") {
        let value: i32 = digits.parse().map_err(|e| ParseError::BadExpression {
            line: line_no,
            position: digits.to_string(),
            detail: format!("i32: {e}"),
        })?;
        let consumed = i + (s.len() - i - rest_after_suffix.len());
        return Ok((Expression::ImmediateBigNum { value }, consumed));
    }
    if let Some(rest_after_suffix) = s[i..].strip_prefix("i8") {
        let value: i8 = digits.parse().map_err(|e| ParseError::BadExpression {
            line: line_no,
            position: digits.to_string(),
            detail: format!("i8: {e}"),
        })?;
        let consumed = i + (s.len() - i - rest_after_suffix.len());
        return Ok((Expression::ImmediateByte { value }, consumed));
    }
    // No suffix: Immediate14 (u16, but rendered as signed-friendly
    // decimal). Negatives don't happen here per the renderer.
    let value: u16 = digits.parse().map_err(|e| ParseError::BadExpression {
        line: line_no,
        position: digits.to_string(),
        detail: format!("Immediate14: {e}"),
    })?;
    Ok((Expression::Immediate14 { value }, i))
}
