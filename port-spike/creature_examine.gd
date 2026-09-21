# CreatureExamineScreen: the 15500 examine plate showing a world
# entity's bestiary row. Opened by the interact strip's INFO button;
# the row is the entity's ETAB creature id through
# generated/ui/bestiary.json (the same records docs/bestiary-ds1.md
# was generated from). A missing row prints NO INFO, the engine's own
# SPIN-failure precedent (screen-flow.md 8.4).
extends WindScreen
class_name CreatureExamineScreen

signal closed

static var _rows: Dictionary

var creature_id := 0
var sprite_png := ""  # region sprite path, empty = no art

static func bestiary_row(oid: int) -> Dictionary:
	if _rows.is_empty():
		var f := FileAccess.open("res://generated/ui/bestiary.json", FileAccess.READ)
		if f == null:
			return {}
		_rows = JSON.parse_string(f.get_as_text())
	return _rows.get(str(oid), {})

func _init(p_creature_id: int, p_sprite := "") -> void:
	window_id = 15500
	creature_id = p_creature_id
	sprite_png = p_sprite

func _ready() -> void:
	# the 15200 bevel ships 145x87, larger than the 111x87 window
	skip_apfm = [15200]
	# the shipped faces are the item-strip arrows/INFO; the creature
	# panel prints its rows over that area, so they stay hot-zone only
	no_resting_art = [15301, 15302, 15303, 15304]
	super._ready()
	var clipped := WindScreen.BevelPanel.new()
	clipped.rect = Rect2(Vector2.ZERO, Vector2(111, 87))
	clipped.seed_key = 15200
	_board.add_child(clipped)
	_board.move_child(clipped, 1)
	if sprite_png != "":
		var icon := Sprite2D.new()
		icon.centered = false
		icon.position = Vector2(46, 6)
		icon.texture = load(sprite_png)
		_board.add_child(icon)
	var row := bestiary_row(creature_id)
	var name_t := TextBlitter.new()
	name_t.ink = Color8(230, 200, 60)
	name_t.relief = Color8(24, 24, 40)
	name_t.position = Vector2(8, 44)
	name_t.text = str(row.get("name", "NO INFO")).to_upper()
	_board.add_child(name_t)
	var lines: Array = []
	if not row.is_empty():
		# Godot's JSON parses numbers as floats; print them engine-style
		lines.append("HP %d  AC %d" % [int(row["hp"]), int(row["ac"])])
		var thac0 := "-" if row.get("thac0") == null else str(int(row["thac0"]))
		lines.append("THAC0 %s  MV %d" % [thac0, int(row["move"])])
		lines.append("%s  XP %d" % [str(row["dmg"]), int(row["xp"])])
	var y := 56.0
	for line in lines:
		var t := TextBlitter.new()
		t.ink = Color8(154, 154, 178)
		t.relief = Color8(24, 24, 40)
		t.position = Vector2(8, y)
		t.text = line
		_board.add_child(t)
		y += 9.0

func _unhandled_input(event: InputEvent) -> void:
	var close: bool = (event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE) \
		or (event is InputEventMouseButton and event.pressed)
	if close:
		closed.emit()
		queue_free()
		get_viewport().set_input_as_handled()
