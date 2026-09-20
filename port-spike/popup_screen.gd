# PopupScreen: WIND 14000, the engine's generic modal (shared proc
# 0x55258; screen-flow.md 8.7). The caller supplies the title and the
# 1-3 line texts; the engine prints them into the header strip and the
# 93x9 line buttons, clicks map to 1..3 with the X to 0, and the
# keyboard path is CASE-INSENSITIVE FIRST-LETTER per line (ESC cancels
# only when the caller allows it). Chosen(0) = cancelled/closed.
extends WindScreen
class_name PopupScreen

signal chosen(index: int)

var title := ""
var lines: Array = []
var allow_esc := true

var _line_rects: Array[Rect2] = []
var _line_letters: Array = []

func _init(p_title := "", p_lines: Array = [], p_allow_esc := true) -> void:
	window_id = 14000
	title = p_title
	lines = p_lines
	allow_esc = p_allow_esc
	# the engine centres the 146x66 popup on the 320x200 screen; the
	# chunk ships with origin (0,0)
	_ensure_winds()
	_winds["14000"]["x"] = 87
	_winds["14000"]["y"] = 67

func _ready() -> void:
	super._ready()
	var header := TextBlitter.new()
	header.ink = Color8(214, 214, 222)
	header.relief = Color8(24, 24, 40)
	header.position = _origin + Vector2(14, 4)
	header.text = title
	_board.add_child(header)
	for i in 3:
		var b := item_by_id(14001 + i)
		var pos := _origin + Vector2(float(b.get("x", 8)), float(b.get("y", 17 + 12 * i)))
		var t := TextBlitter.new()
		t.ink = Color8(24, 24, 24)
		t.relief = Color8(214, 214, 222)
		t.position = pos + Vector2(6, 1)
		t.text = str(lines[i]) if i < lines.size() else ""
		_board.add_child(t)
		_line_rects.append(Rect2(pos, Vector2(float(b.get("w", 93)), float(b.get("h", 9)))))
		_line_letters.append(String(lines[i]).left(1).to_lower().unicode_at(0) \
			if i < lines.size() and str(lines[i]) != "" else 0)

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		var code: int = event.keycode
		if code == KEY_ESCAPE:
			if allow_esc:
				chosen.emit(0)
				get_viewport().set_input_as_handled()
			return
		var ch := char(code).to_lower().unicode_at(0)
		for i in _line_letters.size():
			if _line_letters[i] != 0 and ch == _line_letters[i]:
				chosen.emit(i + 1)
				get_viewport().set_input_as_handled()
				return
	elif event is InputEventMouseButton and event.pressed \
			and event.button_index == MOUSE_BUTTON_LEFT:
		var pos: Vector2 = _board.get_global_transform().affine_inverse() * event.position
		for i in _line_rects.size():
			if _line_rects[i].has_point(pos):
				chosen.emit(i + 1)
				return
