# SpellInfoScreen: WIND 15503 (border plate 15002, EBOX 15400). The
# engine fills the EBOX with the spell's SPIN chunk verbatim
# (screen-flow.md 8.4: load_resource('SPIN', spell_id), text at +5).
# Opened by right-clicking a spell in the USE grid; ESC/click closes.
extends WindScreen
class_name SpellInfoScreen

signal closed

var spell_id := 0

func _init(p_id: int) -> void:
	window_id = 15503
	spell_id = p_id

func _ready() -> void:
	super._ready()
	var db := InventoryScreen._db()
	var spin: Dictionary = (db["spins"] as Dictionary).get(str(spell_id), {})
	# greedy wrap at the EBOX 15400 width (133px), 9px pitch
	var words: Array = String(spin.get("text", "UNKNOWN")).split(" ")
	var wrapped: Array = []
	var cur := ""
	for wd in words:
		var probe: String = wd
		if not cur.is_empty():
			probe = cur + " " + wd
		if TextBlitter.width_of(probe) > 130.0 and not cur.is_empty():
			wrapped.append(cur)
			cur = wd
		else:
			cur = probe
	if not cur.is_empty():
		wrapped.append(cur)
	var layer := Node2D.new()
	layer.name = "TextLayer"
	_board.add_child(layer)
	var y := 17.0
	for line in wrapped:
		var t := TextBlitter.new()
		t.ink = Color8(230, 200, 60)
		t.relief = Color8(24, 24, 40)
		t.position = Vector2(11, y)
		t.text = line
		layer.add_child(t)
		y += 9.0

func _unhandled_input(event: InputEvent) -> void:
	var close: bool = (event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE) \
		or (event is InputEventMouseButton and event.pressed)
	if close:
		closed.emit()
		queue_free()
		get_viewport().set_input_as_handled()
