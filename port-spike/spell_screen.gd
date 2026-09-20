# SpellScreen: WIND 17500, the level-up learn window (screen-flow.md
# 8.4). Border plate 17000, the LEVEL placeholder cycles the displayed
# spell level, cells show the member's known spells for that level
# (ICON 21000+id; psionic powers use 3000+id), EXIT closes. Sample
# known lists ride on PartyData until Wave 3 wires live records.
extends WindScreen
class_name SpellScreen

const ROW_INK := Color8(214, 214, 222)
const ROW_RELIEF := Color8(24, 24, 40)
const STONE := Color8(112, 112, 134)

var member_index := 1
var level := 1
var _level_row: TextBlitter
var _cell_icons: Array[Sprite2D] = []
## Sample known lists: powers of the P-KINESIS discipline and the
## first-level preserver spells, per the mined table at 0x4512C.
var known_powers := [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
var known_spells := [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

func _init() -> void:
	window_id = 17500

func _ready() -> void:
	super._ready()
	level = 1
	_build_level_row()
	_fill_cells()

func _build_level_row() -> void:
	_level_row = TextBlitter.new()
	_level_row.position = Vector2(23, 102)
	_level_row.ink = ROW_INK
	_level_row.relief = ROW_RELIEF
	_level_row.backing = STONE
	_level_row.backing_size = Vector2(46, 11)
	_level_row.text = "LEVEL %d" % level
	_board.add_child(_level_row)

func _fill_cells() -> void:
	var powers := known_powers.size() > 0
	var ids: Array = known_powers if powers else known_spells
	var cells := 0
	for it in data["items"]:
		var iid: int = int(it["id"])
		if iid < 11213 or iid > 11233:
			continue
		if cells >= ids.size():
			break
		var pos := Vector2(float(it["x"]), float(it["y"]))
		var icon_base: int = 3000 if powers else 21000
		var spr := Sprite2D.new()
		spr.texture = load("res://generated/ui/icon%d_f0.png" % (icon_base + int(ids[cells])))
		spr.centered = false
		spr.position = pos
		_board.add_child(spr)
		_cell_icons.append(spr)
		cells += 1

func _cycle_level(dir: int) -> void:
	level = wrapi(level + dir, 1, 10)
	_level_row.text = "LEVEL %d" % level
	# the cell list refills here once live known-spell lists land

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed:
		if event.keycode == KEY_ESCAPE:
			get_tree().change_scene_to_file("res://menu.tscn")
