# LoadScreen: WIND 3009 over the load plate (BMP 3009). Slots are DOS
# SAVE??.SAV files in user://saves with their STXT display labels
# (screen-flow.md 8.7). UP/DOWN move the selection, ENTER/LOAD
# confirms, ESC cancels.
extends WindScreen
class_name LoadScreen

signal load_requested(path: String)

const ROW_INK := Color8(214, 214, 222)
const ROW_RELIEF := Color8(24, 24, 40)

var _labels: Array[String] = []
var _paths: Array[String] = []
var _sel := 0
var _rows: Array[TextBlitter] = []

func _init() -> void:
	window_id = 3009

func _ready() -> void:
	super._ready()
	_bind_load_art()
	_scan()
	_build_rows()
	_refresh()

## The 3009 chunk ships with the SAVE faces; LOAD mode swaps title art
## 6030 onto the header plate and 6031 onto the confirm button
## (screen-flow.md 8.7).
func _bind_load_art() -> void:
	for b in _buttons:
		match int(b["id"]):
			2056:
				(b["sprite"] as Sprite2D).texture = load(
					"res://generated/ui/load6030_f0.png")
			2057:
				(b["sprite"] as Sprite2D).texture = load(
					"res://generated/ui/load6031_f0.png")

func _scan() -> void:
	DirAccess.make_dir_recursive_absolute("user://saves")
	var dir := DirAccess.open("user://saves")
	if dir == null:
		return
	var names: Array[String] = []
	for f in dir.get_files():
		if f.begins_with("SAVE") and f.ends_with(".SAV"):
			names.append(f)
	names.sort()
	for f in names:
		var label := _read_label("user://saves/" + f)
		if label != "":
			_paths.append("user://saves/" + f)
			_labels.append(label)

func _read_label(path: String) -> String:
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		return ""
	var data := f.get_buffer(f.get_length())
	# the label lives in the engine's STXT chunk; SAVE/60's JSON label
	# is the fallback for saves written before the STXT writer landed
	if data.size() < 28 or data.slice(0, 4).get_string_from_ascii() != "GFFI":
		return ""
	var toc_location := data.decode_u32(12)
	var types_offset := data.decode_u32(toc_location)
	var num_types := data.decode_u16(toc_location + types_offset)
	var cursor := toc_location + types_offset + 2
	var json_label := ""
	for t in num_types:
		var kind := data.slice(cursor, cursor + 4).get_string_from_ascii()
		var count := data.decode_u32(cursor + 4) & 0xFFFF
		cursor += 8
		for c in count:
			var rid := data.decode_s32(cursor)
			var loc := data.decode_u32(cursor + 4)
			var length := data.decode_u32(cursor + 8)
			cursor += 12
			if kind == "STXT":
				var end := data.slice(loc, loc + length).find(0)
				return data.slice(loc, loc + (end if end >= 0 else length)) \
					.get_string_from_ascii()
			if kind == "SAVE" and rid == 60:
				var parsed: Variant = JSON.parse_string(
					data.slice(loc, loc + length).get_string_from_utf8())
				if parsed is Dictionary:
					json_label = str(parsed.get("label", ""))
	return json_label

func _build_rows() -> void:
	var layer := Node2D.new()
	layer.name = "TextLayer"
	_board.add_child(layer)
	for i in 10:
		_rows.append(_make_row(layer, Vector2(50, 32 + 9 * i)))

func _make_row(parent: Node2D, pos: Vector2) -> TextBlitter:
	var row := TextBlitter.new()
	row.position = pos
	row.ink = ROW_INK
	row.relief = ROW_RELIEF
	parent.add_child(row)
	return row

func _refresh() -> void:
	for i in 10:
		var s := ""
		if i < _labels.size():
			s = _labels[i]
		_rows[i].text = s

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed:
		match event.keycode:
			KEY_ESCAPE:
				get_tree().current_scene.emit_signal("ui_close")
			KEY_ENTER:
				if _sel < _paths.size():
					load_requested.emit(_paths[_sel])
			KEY_UP:
				_sel = maxi(0, _sel - 1)
			KEY_DOWN:
				_sel = mini(_sel + 1, _paths.size() - 1)
		_refresh()
