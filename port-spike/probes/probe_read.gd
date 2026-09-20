extends SceneTree
func _init():
	var f := FileAccess.open("/tmp/spike-oracle/SAVE01.SAV", FileAccess.READ)
	var data := f.get_buffer(f.get_length())
	var dl := data.decode_u32(8)
	var tl := data.decode_u32(12)
	var tlen := data.decode_u32(16)
	print("dl=", dl, " tl=", tl, " tlen=", tlen)
	var types_offset := data.decode_u32(tl)
	print("types_offset=", types_offset)
	var num_types := data.decode_u16(tl + types_offset)
	print("num_types=", num_types)
	var cursor := tl + types_offset + 2
	for t in num_types:
		var kind := data.slice(cursor, cursor + 4).get_string_from_ascii()
		var count := data.decode_u32(cursor + 4) & 0xFFFF
		print("type ", kind, " count ", count)
		cursor += 8
		for c in count:
			var rid := data.decode_s32(cursor)
			var loc := data.decode_u32(cursor + 4)
			var length := data.decode_u32(cursor + 8)
			print("  chunk ", rid, " loc ", loc, " len ", length)
			cursor += 12
	quit()
