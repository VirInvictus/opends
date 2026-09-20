# PrefsScreen: WIND 16500. Toggles and steppers per screen-flow.md 8.7:
# music/sound on-off, music/sound volume steppers, text speed, mouse
# toggle, the credits page button, back to game menu, X close.
extends WindScreen
class_name PrefsScreen

const ROW_INK := Color8(214, 214, 222)
const ROW_RELIEF := Color8(24, 24, 40)
const STONE := Color8(112, 112, 134)

var music_on := true
var sound_on := true
var music_vol := 90
var sound_vol := 90
var text_speed := 2
var mouse_on := true

var _rows: Array[TextBlitter] = []

func _init() -> void:
	window_id = 16500

func _build_rows() -> void:
	var layer := Node2D.new()
	layer.name = "TextLayer"
	_board.add_child(layer)
	# value readouts beside the steppers
	_rows.append(_make_row(layer, Vector2(120, 26)))
	_rows.append(_make_row(layer, Vector2(120, 45)))
	_rows.append(_make_row(layer, Vector2(120, 64)))

func _make_row(parent: Node2D, pos: Vector2) -> TextBlitter:
	var row := TextBlitter.new()
	row.position = pos
	row.ink = ROW_INK
	row.relief = ROW_RELIEF
	row.backing = STONE
	row.backing_size = Vector2(40, 11)
	parent.add_child(row)
	return row

func _set_row(i: int, s: String) -> void:
	_rows[i].text = s

func _refresh() -> void:
	_set_row(0, str(music_vol))
	_set_row(1, str(sound_vol))
	_set_row(2, ["EASY", "BALANCED", "FAST", "FASTEST"][text_speed])

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed:
		if event.keycode == KEY_ESCAPE:
			screen_requested.emit("close")
			return
	elif event is InputEventMouseButton and event.pressed \
			and event.button_index == MOUSE_BUTTON_LEFT:
		var pos: Vector2 = _board.get_global_transform().affine_inverse() * event.position
		for b in _buttons:
			if (b["rect"] as Rect2).has_point(pos):
				_activate(int(b["id"]))
				return

signal screen_requested(name: String)

func _activate(iid: int) -> void:
	match iid:
		11308:
			screen_requested.emit("gamemenu")
		10308:
			screen_requested.emit("close")
		_:
			pass  # toggle/stepper wiring lands with the audio backend
