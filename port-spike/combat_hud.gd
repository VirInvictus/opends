# CombatHud: the engine-drawn combat overlay (no WIND exists). Binding
# per the mining report: stat gauge BMP 20106 trough + 20107 fill
# (cur/max * 82 of the 80px interior), status panel BMP 5016 at
# (215,4) 98x32 with four FONT/100 lines, arc indicator BMP 5012 at
# (10,10). Feed with set_actor(); text uses the mined 'Move : %d'
# format and the condition table.
extends Node2D
class_name CombatHud

var _lines: Array[TextBlitter] = []

func _ready() -> void:
	for pair in [[215, 4, "bmp5016.png"], [10, 10, "bmp5012.png"]]:
		var s := Sprite2D.new()
		s.texture = load("res://generated/ui/" + str(pair[2]))
		s.centered = false
		s.position = Vector2(pair[0], pair[1])
		add_child(s)
	for i in 4:
		var t := TextBlitter.new()
		t.ink = Color8(214, 214, 222)
		t.relief = Color8(24, 24, 40)
		add_child(t)
		_lines.append(t)
	_lines[0].text = ""
	queue_redraw()

func set_actor(name_: String, hp: int, hp_max: int, moves: int, condition: String) -> void:
	_lines[0].text = name_
	_lines[0].position = _centered(name_, 215, 98, 6)
	_lines[1].text = "%d/%d" % [hp, hp_max] if hp_max > 0 else "???/???"
	_lines[1].position = _centered(_lines[1].text, 215, 98, 12)
	_lines[2].text = condition
	_lines[2].position = _centered(condition, 215, 98, 18)
	_lines[3].text = "Move : %d" % (moves / 10)
	_lines[3].position = _centered(_lines[3].text, 215, 98, 24)

func _centered(s: String, panel_x: int, panel_w: int, y: int) -> Vector2:
	return Vector2(panel_x + (panel_w - TextBlitter.width_of(s)) / 2.0, y)
