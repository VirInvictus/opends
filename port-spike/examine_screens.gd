# ExamineScreen: WIND 15502 view-item (bg 15001). Shows the item's
# icon, name, and the IT1R fields the engine's INFO path prints
# (weapon dice or AC bonus, weight in tenths, value in ceramic).
# Right-click an occupied inventory cell opens it; ESC/click closes.
extends WindScreen
class_name ExamineScreen

signal closed

var obj_id := 0

func _init(p_obj := 0) -> void:
	window_id = 15502
	obj_id = p_obj

func _ready() -> void:
	super._ready()
	var info: Dictionary = InventoryScreen.obj_info(obj_id)
	var icon := Sprite2D.new()
	icon.centered = false
	icon.position = Vector2(16, 16)
	icon.texture = InventoryScreen.texture_for(str(info["png"]))
	_board.add_child(icon)
	var name_t := TextBlitter.new()
	name_t.ink = Color8(230, 200, 60)
	name_t.relief = Color8(24, 24, 40)
	name_t.position = Vector2(12, 8)
	name_t.text = str(info.get("name", "?")).to_upper()
	_board.add_child(name_t)
	var weight := int(info.get("weight", 0))
	var lines: Array
	if int(info.get("base_ac", 0)) > 0:
		lines = ["AC %+d" % int(info.get("base_ac", 0)),
			"WT %d.%d lb" % [weight / 10, weight % 10]]
	else:
		lines = ["%dd%d%+d" % [int(info.get("dice", 0)), int(info.get("sides", 0)), int(info.get("mod", 0))],
			"WT %d.%d lb" % [weight / 10, weight % 10]]
	var y := 40.0
	for line in lines:
		var t := TextBlitter.new()
		t.ink = Color8(230, 200, 60)
		t.relief = Color8(24, 24, 40)
		t.position = Vector2(16, y)
		t.text = line
		_board.add_child(t)
		y += 10.0

func _unhandled_input(event: InputEvent) -> void:
	var close: bool = (event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE) \
		or (event is InputEventMouseButton and event.pressed)
	if close:
		closed.emit()
		queue_free()
		get_viewport().set_input_as_handled()
