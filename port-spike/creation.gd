# CreationScreen: WIND 3011 with the engine's behavior layer (docs/
# screen-flow.md 8.2). The race/class/stat model reuses the mined rules
# already proven in menu.gd; positions of the dynamic text rows come
# off the oracle capture (stat rows 135+7i, name row 125, right column
# mirrors with HP at 172).
extends WindScreen
class_name CreationScreen

const RACES := ["Human", "Dwarf", "Elf", "Half-Elf", "Half-Giant", "Mul", "Thri-kreen"]
const RACE_MODS := [
	[0, 0, 0, 0, 0, 0], [1, -1, 2, 0, 0, -2], [0, 2, -2, 1, -1, 0],
	[0, 1, -1, 0, 0, 0], [4, -5, 2, -5, -3, -3], [-2, 2, -1, 0, 2, -1],
	[2, 0, 1, -1, 0, -2], [0, 2, 0, -1, 1, -2],
]
const RACE_MASK := [0xFF, 0xB5, 0xBF, 0xFF, 0xB6, 0xF7, 0xF5]
const CLASSES := ["Cleric", "Druid", "Fighter", "Gladiator", "Preserver", "Psionicist", "Ranger", "Thief"]
const CLASS_MIN := [9, 12, 9, 13, 9, 12, 14, 9]
const CLASS_PRIME := [4, 4, 0, 0, 3, 4, 1]
const ALIGN_NAMES := [
	"Lawful Good", "Neutral Good", "Chaotic Good",
	"Lawful Neutral", "True Neutral", "Chaotic Neutral",
	"Lawful Evil", "Neutral Evil", "Chaotic Evil",
]
const XP_ROWS := [
	[0, 15, 30, 60, 130, 275, 550, 1100, 2250, 4500],
	[0, 20, 40, 75, 125, 200, 350, 600, 900, 1250],
	[0, 20, 40, 80, 160, 320, 640, 1250, 2500, 5000],
	[0, 20, 40, 80, 160, 320, 640, 1250, 2500, 5000],
	[0, 25, 50, 100, 200, 400, 600, 900, 1350, 2500],
	[0, 22, 44, 88, 165, 300, 550, 1000, 2000, 4000],
	[0, 22, 45, 90, 180, 360, 750, 1500, 3000, 6000],
	[0, 12, 25, 50, 100, 200, 400, 700, 1100, 1600],
]
const ROW_INK := Color8(214, 214, 222)
const ROW_RELIEF := Color8(24, 24, 40)
const AVAILABLE_INK := Color8(138, 138, 162)
const SELECTED_INK := Color8(65, 24, 8)
const LEATHER := Color8(74, 74, 98)
const DISC_NAMES := ["P-KINESIS", "P-METAB", "TELEPATHY"]
const DISC_BITS := [0x80, 0x40, 0x20]

var race_idx := 0
var gender := 0
var class_slot := 3  # creation class enum of the sole selected class
var align := 5
var stats := [0, 0, 0, 0, 0, 0]
var hp := 10
var hp_max := 10
var cname := "Nameless"
var psp := 0
var psp_max := 0
var disc_mask := 0x80
var sphere_mask := 0
var _rows: Array[TextBlitter] = []
var _name_box: TextBlitter
var _bullets: Node2D

func _init() -> void:
	window_id = 3011

func _ready() -> void:
	no_resting_art = [2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008,
		2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018,
		2027]
	super._ready()
	_roll_all()
	_build_rows()
	_build_bullets()
	_refresh()

func _build_rows() -> void:
	var layer := Node2D.new()
	layer.name = "TextLayer"
	_board.add_child(layer)
	for i in 6:
		_rows.append(_make_row(layer, Vector2(5, 135 + 7 * i), ROW_INK))
	_rows.append(_make_row(layer, Vector2(5, 125), ROW_INK))  # NAME:
	# right column: race/gender, alignment, class, level/EXP, AC/DAM,
	# HP, PSP
	for i in 7:
		_rows.append(_make_row(layer, Vector2(76, 135 + 7 * i), ROW_INK))
	# class list: eight rows, ink goes light for available, dark for the
	# selected row (the icon faces on 2002-2009 are flash variants, not
	# the resting art)
	for i in 8:
		_rows.append(_make_row(layer, Vector2(227, 8 + 8 * i), AVAILABLE_INK))
	# psionic discipline rows (the PSI DISCIPLINES header and VIEW
	# SPHERES stay baked in the backdrop - they never change)
	for i in 3:
		_rows.append(_make_row(layer, Vector2(226, 101 + 8 * i), AVAILABLE_INK))

func _build_bullets() -> void:
	var bl := BulletLayer.new()
	bl.cs = self
	_bullets = bl
	_bullets.name = "Bullets"
	_board.add_child(_bullets)

func _make_row(parent: Node2D, pos: Vector2, ink: Color) -> TextBlitter:
	var row := TextBlitter.new()
	row.position = pos
	row.ink = ink
	row.relief = ROW_RELIEF
	row.backing = LEATHER
	row.backing_size = Vector2(206, 11)
	parent.add_child(row)
	return row

func _set_row(i: int, s: String) -> void:
	_rows[i].text = s

func _set_row_ink(i: int, ink: Color) -> void:
	_rows[i].ink = ink

func _roll_stat(stat_i: int) -> void:
	var racial: int = RACE_MODS[race_idx][stat_i]
	var prime: int = CLASS_PRIME[class_slot - 1] if class_slot > 0 else -1
	var best := 0
	for attempt in 4:
		var v := _d4() + _d4() + _d4() + _d4() + racial + 4
		if v > best:
			best = v
	if stat_i == prime:
		best = maxi(best, 17)
	stats[stat_i] = clampi(best, 3, racial + 20)

func _roll_all() -> void:
	for i in 6:
		_roll_stat(i)
	hp_max = _class_die()
	hp = hp_max

func _d4() -> int:
	return randi_range(1, 4)

func _class_die() -> int:
	return [8, 8, 10, 10, 4, 6, 8, 6][class_slot - 1] if class_slot > 0 else 8

func _thac0() -> int:
	var rate: int = [8, 8, 12, 12, 4, 8, 12, 6][class_slot - 1] if class_slot > 0 else 8
	return 20 - (rate * 2) / 12

func _refresh() -> void:
	if _bullets != null:
		_bullets.queue_redraw()
	var prime: int = CLASS_PRIME[class_slot - 1] if class_slot > 0 else -1
	for i in 6:
		_set_row(i, "%s %s:%d" % ["*" if i == prime else "", ["STR", "DEX", "CON", "INT", "WIS", "CHR"][i], stats[i]])
	_set_row(6, "NAME: " + cname)
	var race_name: String = RACES[race_idx]
	var g := "MALE " if gender == 0 else "FEMALE "
	_set_row(7, g + race_name.to_upper())
	_set_row(8, ALIGN_NAMES[align - 1].to_upper())
	var cname_up: String = CLASSES[class_slot - 1] if class_slot > 0 else ""
	_set_row(9, cname_up.to_upper())
	var level := 3
	var xp: int = XP_ROWS[class_slot - 1][2] * 100 if class_slot > 0 else 0
	var nxt: int = XP_ROWS[class_slot - 1][3] * 100 if class_slot > 0 else 0
	_set_row(10, "%d  EXP:%d (%d)" % [level, xp, nxt])
	var dam := "1.5*1D1+1"
	_set_row(11, "AC: %d  DAM: %s" % [10 - 2 + (2 if race_idx == 4 else 0), dam])
	_set_row(12, "%d/%d" % [hp, hp_max])
	_set_row(13, "%d/%d" % [psp, psp_max])
	_bullets.queue_redraw()
	# class list rows 2002..2009
	for ci in 8:
		var selected: bool = class_slot == ci + 1
		_set_row(14 + ci, CLASSES[ci].to_upper())
		_set_row_ink(14 + ci, SELECTED_INK if selected else AVAILABLE_INK)
	# psionic discipline rows + view spheres
	for di in 3:
		var on: bool = (disc_mask & DISC_BITS[di]) != 0
		_set_row(22 + di, DISC_NAMES[di])
		_set_row_ink(22 + di, SELECTED_INK if on else AVAILABLE_INK)

func _cycle_race(dir: int) -> void:
	var packed := race_idx * 2 + gender
	packed = wrapi(packed + dir, 0, 14)
	race_idx = packed >> 1
	gender = packed & 1
	_clamp_stats()
	_refresh()

func _clamp_stats() -> void:
	for i in 6:
		var racial: int = RACE_MODS[race_idx][i]
		stats[i] = clampi(stats[i], 3, racial + 20)

func _toggle_class(creation_class: int) -> void:
	if class_slot == creation_class:
		return  # the engine would deselect; keep at least one class
	class_slot = creation_class
	_roll_all()
	_refresh()

func _adjust_stat(stat_i: int, dir: int) -> void:
	var racial: int = RACE_MODS[race_idx][stat_i]
	var floor_v: int = CLASS_MIN[class_slot - 1] if class_slot > 0 else 3
	if stat_i == (CLASS_PRIME[class_slot - 1] if class_slot > 0 else -1):
		floor_v = maxi(floor_v, 17)
	stats[stat_i] = clampi(stats[stat_i] + dir, floor_v, racial + 20)
	_refresh()

func _accept() -> void:
	var rec := {
		"use_presets": false, "name": cname, "race": race_idx, "gender": gender,
		"class": CLASSES[class_slot - 1], "level": 3,
		"xp": XP_ROWS[class_slot - 1][2] * 100, "bmp": [2095, 2095, 2059, 2095, 2095, 2095, 2097][race_idx],
		"hp": hp, "max_hp": hp_max, "ac": 10, "thac0": _thac0(),
		"move": [12, 6, 12, 12, 14, 12, 15][race_idx],
		"blows": 2, "dice": 1, "sides": 8, "bonus": 1, "stats": stats,
	}
	var f := FileAccess.open("res://generated/created.json", FileAccess.WRITE)
	f.store_string(JSON.stringify(rec))
	Engine.set_meta("skip_intro", true)
	get_tree().change_scene_to_file("res://main.tscn")

func _on_item(iid: int, right_click: bool) -> void:
	var dir := -1 if right_click else 1
	match iid:
		2001, 2027: _cycle_race(dir)
		2010:
			_roll_all()
			_refresh()
		2011: align = wrapi(align + dir, 1, 10); _refresh()
		2012: _adjust_stat(0, dir)
		2013: _adjust_stat(1, dir)
		2014: _adjust_stat(2, dir)
		2015: _adjust_stat(3, dir)
		2016: _adjust_stat(4, dir)
		2017: _adjust_stat(5, dir)
		2018: hp = wrapi(hp + dir, 1, hp_max + 1); _refresh()
		2002: _toggle_class(1)
		2003: _toggle_class(2)
		2004: _toggle_class(3)
		2005: _toggle_class(4)
		2006: _toggle_class(5)
		2007: _toggle_class(6)
		2008: _toggle_class(7)
		2009: _toggle_class(8)
		2000: _accept()
		2058: get_tree().change_scene_to_file("res://menu.tscn")

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.button_index in [MOUSE_BUTTON_LEFT, MOUSE_BUTTON_RIGHT] and event.pressed:
		var pos: Vector2 = _board.get_global_transform().affine_inverse() * event.position
		for b in _buttons:
			if (b["rect"] as Rect2).has_point(pos):
				_on_item(int(b["id"]), event.button_index == MOUSE_BUTTON_RIGHT)
				return
	elif event is InputEventKey and event.pressed:
		var k: InputEventKey = event
		if k.keycode == KEY_ESCAPE:
			_on_item(2058, false)
		elif k.keycode == KEY_BACKSPACE and cname.length() > 0:
			cname = cname.substr(0, cname.length() - 1)
			_refresh()
		elif k.unicode >= 32 and k.unicode < 127 and cname.length() < 15:
			cname += char(k.unicode)
			_refresh()


## Marker glyphs: a square ahead of each stat row, a diamond ahead of
## the selected class and the selected discipline.
class BulletLayer:
	extends Node2D

	var dark := Color8(65, 24, 8)
	var cs: CreationScreen

	func _draw() -> void:
		for i in 6:
			draw_rect(Rect2(Vector2(5, 137 + 7 * i), Vector2(4, 4)), dark)
		if cs.class_slot > 0:
			var ci: int = cs.class_slot - 1
			draw_rect(Rect2(Vector2(219, 10 + 8 * ci), Vector2(5, 5)), dark)
		if (cs.disc_mask & 0x80) != 0:
			draw_rect(Rect2(Vector2(216, 103), Vector2(5, 5)), dark)
