# ChoiceScreen: WIND 3008, the dialog choice strip that pairs with
# 3007 (five 300x10 bar buttons 2076-2080, ICON 12102-12106 faces,
# scroll arrows 2095/2096; screen-flow.md 8.1). The engine feeds the
# 0x48 MENU option lines into the bars; up to five show at once with
# arrow paging. Click a bar or press its first letter; chosen(index)
# reports the GLOBAL option index.
extends WindScreen
class_name ChoiceScreen

signal chosen(index: int)

const BAR_FIRST := 2076
const VISIBLE := 5

var options: Array = []  # reply lines, in engine order
var auto_seconds := 0.0  # >0: scripted QC picks auto_index
var auto_index := 0

var _page := 0
var _bars: Array[Dictionary] = []  # {rect: Rect2, text: TextBlitter}
var _auto := 0.0

func _init(p_options: Array, p_auto := 0.0, p_auto_index := 0) -> void:
	window_id = 3008
	options = p_options
	auto_seconds = p_auto
	auto_index = p_auto_index

func _ready() -> void:
	super._ready()
	_page = 0
	_show_page()

func _show_page() -> void:
	for c in _board.get_children():
		if String(c.name).begins_with("Opts"):
			c.queue_free()
	var layer := Node2D.new()
	layer.name = "Opts%d" % _page
	_board.add_child(layer)
	_bars.clear()
	for i in VISIBLE:
		var oi := _page * VISIBLE + i
		if oi >= options.size():
			break
		var b := item_by_id(BAR_FIRST + i)
		var pos := _origin + Vector2(float(b.get("x", 3)), float(b.get("y", 13 + 8 * i)))
		var t := TextBlitter.new()
		t.ink = Color8(24, 24, 24)
		t.relief = Color8(214, 214, 222)
		t.position = pos + Vector2(5, 1)
		t.text = str(options[oi]).strip_edges()
		layer.add_child(t)
		_bars.append({"rect": Rect2(pos, Vector2(float(b.get("w", 300)), float(b.get("h", 10)))),
			"letter": String(options[oi]).strip_edges().left(1).to_lower().unicode_at(0),
			"index": oi})

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		var ch := char(event.keycode).to_lower().unicode_at(0)
		for b in _bars:
			if int(b["letter"]) == ch:
				chosen.emit(int(b["index"]))
				get_viewport().set_input_as_handled()
				return
	elif event is InputEventMouseButton and event.pressed \
			and event.button_index == MOUSE_BUTTON_LEFT:
		var pos: Vector2 = _board.get_global_transform().affine_inverse() * event.position
		for b in _bars:
			if (b["rect"] as Rect2).has_point(pos):
				chosen.emit(int(b["index"]))
				return

func _process(delta: float) -> void:
	if auto_seconds <= 0.0:
		return
	_auto -= delta
	if _auto <= 0.0:
		chosen.emit(auto_index)
