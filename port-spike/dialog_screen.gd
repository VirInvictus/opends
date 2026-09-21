# DialogScreen: WIND 3007, the engine's dialog strip (drawn at board
# (1,0), 318x58): stone plate with the portrait frame (PORT 119 face
# for the arena Announcer) and EBOX 4002, all baked into
# dialog_plate_3007.png (regenerated from the oracle capture with the
# text in-painted). Pages advance on Enter/Space/click (the invisible
# 12300 hot zone); finished fires when the last page closes. Lines are
# the real GPL-2 strings (docs/dialogs.md machinery).
extends WindScreen
class_name DialogScreen

signal finished

const LINE_WIDTH := 228.0
const LINE_PITCH := 9.0
const MAX_LINES := 4
const ANNOUNCER_PORT := 119

var pages: Array = []  # [{port: int, text: String}] (port reserved for
# per-speaker faces; the announcer face is baked into the plate)
var auto_seconds := 0.0  # >0: auto-advance for scripted QC runs

var _page := -1
var _auto := 0.0

func _init(p_pages: Array, p_auto := 0.0) -> void:
	window_id = 3007
	pages = p_pages
	auto_seconds = p_auto
	# the engine opens the strip at board (1,0), not the chunk's (10,0)
	_ensure_winds()
	_winds["3007"]["x"] = 1
	_winds["3007"]["y"] = 0

func _ready() -> void:
	super._ready()
	var plate := Sprite2D.new()
	plate.texture = load("res://generated/ui/dialog_plate_3007.png")
	plate.centered = false
	_board.add_child(plate)
	_board.move_child(plate, 0)
	_next_page()

func _process(delta: float) -> void:
	if auto_seconds > 0.0:
		_auto -= delta
		if _auto <= 0.0:
			_next_page()

func _next_page() -> void:
	_page += 1
	_auto = auto_seconds
	if _page >= pages.size():
		finished.emit()
		queue_free()
		return
	_show_page(str(pages[_page]["text"]))

func _show_page(text: String) -> void:
	for c in _board.get_children():
		if String(c.name).begins_with("Page"):
			c.queue_free()
	var layer := Node2D.new()
	layer.name = "Page%d" % _page
	_board.add_child(layer)
	var y := 6.0
	for line in text.split("\n"):
		var t := TextBlitter.new()
		t.ink = Color8(230, 200, 60)
		t.relief = Color8(24, 24, 40)
		t.position = _origin + Vector2(60, y)
		t.text = line
		layer.add_child(t)
		y += LINE_PITCH

## Greedy word wrap at the EBOX 4002 width (236px), max 4 lines.
func _wrap(text: String) -> Array:
	var words := text.split(" ")
	var lines: Array = []
	var cur := ""
	for w in words:
		var probe := w
		if not cur.is_empty():
			probe = cur + " " + w
		if TextBlitter.width_of(probe) > LINE_WIDTH and not cur.is_empty():
			lines.append(cur)
			cur = w
		else:
			cur = probe
		if lines.size() == MAX_LINES:
			break
	if not cur.is_empty() and lines.size() < MAX_LINES:
		lines.append(cur)
	return lines

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode in [KEY_ENTER, KEY_SPACE, KEY_KP_ENTER]:
			_next_page()
			get_viewport().set_input_as_handled()
	elif event is InputEventMouseButton and event.pressed \
			and event.button_index == MOUSE_BUTTON_LEFT:
		var pos: Vector2 = _board.get_global_transform().affine_inverse() * event.position
		if Rect2(_origin, Vector2(318, 58)).has_point(pos):
			_next_page()
			get_viewport().set_input_as_handled()
