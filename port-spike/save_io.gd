# SaveIO: GFFI save files in the DARKRUN/SAVE0N.SAV family layout.
# Chunks written: SAVE/5 party combat rows (58 B each, ds1_combat_t),
# SAVE/6 party character rows (71 B each, ds1_character_t), STXT/0 the
# display label, SAVE/60 the port's own state blob (JSON: region, tile,
# fight counter, gold). Layout per docs/file-formats.md 3.2-3.4; the
# container mirrors save-inspect's parse_gff (indexed chunks only).
class_name SaveIO

const HEADER_SIZE := 28
const VERSION := 196608  # 3 << 16
const MAGIC := "GFFI"

static func _i16(v: int) -> PackedByteArray:
	var b := PackedByteArray()
	b.resize(2)
	b.encode_s16(0, clampi(v, -32768, 32767))
	return b

static func _u16(v: int) -> PackedByteArray:
	var b := PackedByteArray()
	b.resize(2)
	b.encode_u16(0, clampi(v, 0, 65535))
	return b

static func _u32(v: int) -> PackedByteArray:
	var b := PackedByteArray()
	b.resize(4)
	b.encode_u32(0, v)
	return b

static func _str_field(s: String, size: int) -> PackedByteArray:
	var b := s.to_ascii_buffer()
	b.resize(size)
	return b

## Packs one party member into a 58-byte combat row (SAVE/5).
static func combat_row(m: Dictionary) -> PackedByteArray:
	var b := PackedByteArray()
	b.append_array(_i16(int(m["hp"])))
	b.append_array(_i16(int(m.get("psi", [0, 0])[0])))
	b.append_array(_i16(0))  # char_index
	b.append_array(_i16(0))  # id
	b.append_array(_i16(0))  # ready_item_index
	b.append_array(_i16(0))  # weapon_index
	b.append_array(_i16(0))  # pack_index
	for i in 8:
		b.append(0)  # data_block
	b.append(0)  # special_attack
	b.append(0)  # special_defense
	b.append_array(_u16(int(m.get("bmp", 0))))
	b.append(int(m["ac"]))
	b.append(int(m["moves"]) / 10)
	b.append(0 if str(m["status"]) == "Okay" else 1)  # status
	b.append(0)  # allegiance
	b.append(0)  # data
	b.append(int(m["thac0"]))
	b.append(0)  # priority
	b.append(0)  # flags
	for v in m["stats"]:
		b.append(int(v))
	var name_field := _str_field(str(m["name"]), 18)
	b.append_array(name_field)
	return b

## Packs one party member into a 71-byte character row (SAVE/6).
static func char_row(m: Dictionary) -> PackedByteArray:
	var b := PackedByteArray()
	b.append_array(_u32(int(m.get("exp", 0))))
	b.append_array(_u32(int(m.get("exp_next", 0))))
	b.append_array(_u16(int(m["max"])))
	b.append_array(_u16(int(m["max"])))
	b.append_array(_u16(int(m.get("psi", [0, 0])[1])))
	b.append_array(_u16(0))  # id
	b.append(0)
	b.append(0)
	b.append_array(_u16(0))  # legal_class
	for i in 4:
		b.append(0)
	b.append(int(m.get("race_i", 1)))
	b.append(int(m.get("gender_i", 1)))
	b.append(int(m.get("align_i", 5)))
	for v in m["stats"]:
		b.append(int(v))
	var ids: Array = m.get("class_ids", [9])
	var levels: Array = m.get("levels", [1])
	for i in 3:
		b.append(int(ids[i]) if i < ids.size() else 0)
	for i in 3:
		b.append(int(levels[i]) if i < levels.size() else 0)
	b.append(int(m["ac"]))
	b.append(int(m["moves"]) / 10)
	b.append(0)  # magic_resistance
	b.append(int(m.get("blows", 1)))
	for i in 3:
		b.append(int(m.get("blows", 1)))
	for i in 3:
		b.append(int(m.get("dice", 1)))
	for i in 3:
		b.append(int(m.get("sides", 8)))
	for i in 3:
		b.append(int(m.get("bonus", 1)))
	for i in 5:
		b.append(0)  # saving throws (engine writes 99 at init)
	b.append(0)  # allegiance
	b.append(0)  # size
	b.append(0)  # spell_group
	for i in 3:
		b.append(int(levels[i]) if i < levels.size() else 0)
	b.append_array(_u16(0))  # sound_fx
	b.append_array(_u16(0))  # attack_sound
	b.append(0)  # psi_group
	return b

## Writes the save file. state = {"label", "members" (PartyData.MEMBERS
## shape), "port": {"region", "tile", "fight_count", "gold"}}.
static func write_save(path: String, state: Dictionary) -> int:
	var chunks: Array[Dictionary] = []
	var s5 := PackedByteArray()
	var s6 := PackedByteArray()
	for m in state["members"]:
		s5.append_array(combat_row(m))
		s6.append_array(char_row(m))
	chunks.append({"kind": "SAVE", "id": 5, "bytes": s5})
	chunks.append({"kind": "SAVE", "id": 6, "bytes": s6})
	var port: Dictionary = state["port"]
	port["label"] = str(state["label"])
	chunks.append({"kind": "SAVE", "id": 60,
		"bytes": str(JSON.stringify(port)).to_utf8_buffer()})
	return _write_gffi(path, chunks)

static func read_save(path: String) -> Dictionary:
	var out := {"label": "", "members": [], "port": {}}
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		return out
	var data := f.get_buffer(f.get_length())
	if data.size() < HEADER_SIZE or data.slice(0, 4).get_string_from_ascii() != MAGIC:
		return out
	var data_location := data.decode_u32(8)
	var toc_location := data.decode_u32(12)
	var toc_length := data.decode_u32(16)
	var types_offset := data.decode_u32(toc_location)
	var num_types := data.decode_u16(toc_location + types_offset)
	var cursor := toc_location + types_offset + 2
	for t in num_types:
		var kind := data.slice(cursor, cursor + 4).get_string_from_ascii()
		var count := data.decode_u32(cursor + 4) & 0xFFFF
		cursor += 8
		for c in count:
			var rid := data.decode_s32(cursor)
			var loc := data.decode_u32(cursor + 4)
			var length := data.decode_u32(cursor + 8)
			cursor += 12
			var payload := data.slice(loc, loc + length)
			if kind == "SAVE" and rid == 5:
				for mi in payload.size() / 58:
					var row := payload.slice(mi * 58, mi * 58 + 58)
					var m: Dictionary = (PartyData.MEMBERS[mi] if mi < PartyData.MEMBERS.size() else {}).duplicate()
					m["hp"] = row.decode_s16(0)
					m["ac"] = row[26]
					m["thac0"] = row[31]
					m["name"] = row.slice(40, 58).get_string_from_ascii().rstrip(String.chr(0))
					out["members"].append(m)
			elif kind == "SAVE" and rid == 6:
				for mi in payload.size() / 71:
					var row := payload.slice(mi * 71, mi * 71 + 71)
					if mi < out["members"].size():
						out["members"][mi]["max"] = row.decode_u16(8)
			elif kind == "SAVE" and rid == 60:
				var parsed: Variant = JSON.parse_string(
					payload.get_string_from_utf8())
				if parsed is Dictionary:
					out["port"] = parsed
			elif kind == "STXT":
				out["label"] = payload.get_string_from_ascii().rstrip(String.chr(0))
	return out

static func _write_gffi(path: String, chunks: Array[Dictionary]) -> int:
	# group chunks by kind preserving order
	var kinds: Array[String] = []
	var by_kind := {}
	var data := PackedByteArray()
	var off := data_location()
	for c in chunks:
		var bytes: PackedByteArray = c["bytes"]
		var k: String = c["kind"]
		if not by_kind.has(k):
			kinds.append(k)
			by_kind[k] = []
		by_kind[k].append({"id": int(c["id"]), "off": off, "len": bytes.size()})
		data.append_array(bytes)
		off += bytes.size()
	# TOC: types_offset u32, free list u32, type count u16, then per kind
	# [kind 4s][count u32] followed by that kind's 12-byte chunk entries.
	var toc := PackedByteArray()
	toc.append_array(_u32(8))  # num_types sits 8 bytes into the toc
	toc.append_array(_u32(0))
	toc.append_array(_u16(kinds.size()))
	for k in kinds:
		toc.append_array(k.to_ascii_buffer())
		toc.append_array(_u32(by_kind[k].size()))
		for c in by_kind[k]:
			toc.append_array(_u32(int(c["id"])))
			toc.append_array(_u32(int(c["off"])))
			toc.append_array(_u32(int(c["len"])))
	# layout: [28-byte header][chunk data][toc]
	var out := PackedByteArray()
	out.append_array(MAGIC.to_ascii_buffer())
	out.append_array(_u32(VERSION))
	out.append_array(_u32(data_location()))
	out.append_array(_u32(data_location() + data.size()))
	out.append_array(_u32(toc.size()))
	out.append_array(_u32(0))
	out.append_array(_u32(1))
	out.append_array(data)
	out.append_array(toc)
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		return ERR_CANT_OPEN
	f.store_buffer(out)
	f.close()
	return OK


static func data_location() -> int:
	return HEADER_SIZE
