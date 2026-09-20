# SheetScreen: WIND 11500 in its three modes (screen-flow.md 8.7):
# VIEW CHARACTER (name/stats/origin/class/EXP block), USE (the casting
# picker: spell grid 21000+id, class + LEVEL bars on the strip), and
# EFFECTS (name only, empty panel). Party strip rows mirror the
# inventory's four slots.
extends WindScreen
class_name SheetScreen

enum Mode { VIEW, USE, EFFECTS }

const ROW_INK := Color8(214, 214, 222)
const ROW_RELIEF := Color8(24, 24, 40)
const ROW_GOLD := Color8(230, 200, 60)
const ROW_PSI := Color8(120, 150, 235)
const TITLE_TEX := {
	Mode.VIEW: "bmp20079.png",
	Mode.USE: "bmp20080.png",
	Mode.EFFECTS: "bmp20075.png",
}
const SPELL_GRID_ORIGIN := Vector2(168, 52)
const SPELL_GRID_PITCH := Vector2(19, 21)
# the sheet's right-hand cell APFMs are the spell grid; the engine
# draws cell frames only under filled slots (oracle USE capture), and
# view/effects show plain stone
const SKIP_CELLS := [11213, 11214, 11215, 11216, 11217, 11218, 11219, 11220,
	11221, 11222, 11223, 11224, 11225, 11226, 11227, 11228, 11229, 11230,
	11234, 11235, 11236, 11237, 11238, 11239, 11240, 11241, 11242, 11243,
	11244, 11245]

var selected := 1
var mode := Mode.VIEW
var cast_class := ""  # caster class whose spells the USE grid shows
var _rows: Array[TextBlitter] = []
var _spell_cells: Array[Node2D] = []
var _bar_texts: Array[TextBlitter] = []

func _init(p_mode := Mode.VIEW) -> void:
	window_id = 11500
	mode = p_mode
	# the 35 right-panel cell APFMs never paint in these modes: the
	# oracle shows plain stone, and USE draws icons without cell frames
	skip_apfm.assign(SKIP_CELLS)

func _ready() -> void:
	super._ready()
	_build_rows()
	attach_party_figures(PartyData.MEMBERS, InventoryScreen._db()["party"])
	if mode == Mode.USE:
		_build_spell_grid()
		_build_bar_texts()
	_refresh()

func _selected_member() -> Dictionary:
	return PartyData.MEMBERS[selected]

## The member's caster classes in engine order with known spells.
func _caster_classes() -> Array:
	var m := _selected_member()
	var out: Array = []
	for cls in m.get("classes", []):
		if (m.get("spells", {}) as Dictionary).has(cls):
			out.append(cls)
	return out

func _build_spell_grid() -> void:
	var casters := _caster_classes()
	if casters.is_empty():
		return
	if cast_class == "" or not casters.has(cast_class):
		cast_class = casters[0]
	for i in 10:
		var cell := Node2D.new()
		cell.position = SPELL_GRID_ORIGIN + Vector2(float(i % 5), float(i / 5)) * SPELL_GRID_PITCH
		var icon := Sprite2D.new()
		icon.name = "Icon"
		icon.centered = false
		icon.visible = false
		cell.add_child(icon)
		_board.add_child(cell)
		_spell_cells.append(cell)

func _build_bar_texts() -> void:
	for iid in [11319, 11320]:
		var b := item_by_id(iid)
		var t := TextBlitter.new()
		t.ink = Color8(24, 24, 24)
		t.relief = Color8(214, 214, 222)
		t.position = Vector2(float(b.get("x", 0)) + 4, float(b.get("y", 0)) + 2)
		_board.add_child(t)
		_bar_texts.append(t)

func _set_spell_grid() -> void:
	var m := _selected_member()
	var ids: Array = (m.get("spells", {}) as Dictionary).get(cast_class, [])
	for i in _spell_cells.size():
		var icon: Sprite2D = _spell_cells[i].get_child(0)
		if i < ids.size():
			var iid := int(ids[i])
			icon.texture = load("res://generated/ui/icon%d_f0.png" % (21000 + iid))
			icon.position = Vector2(1, 1)
			icon.visible = true
		else:
			icon.visible = false

func _set_bar_texts() -> void:
	if _bar_texts.is_empty():
		return
	_bar_texts[0].text = cast_class.to_upper()
	_bar_texts[1].text = "LEVEL %d" % (1 + int(_selected_member().get("levels", [1])[0]) / 2)

func _build_rows() -> void:
	# each mode's title plate centres on the same midline
	var title := Sprite2D.new()
	var tex: Texture2D = load("res://generated/ui/" + TITLE_TEX[mode])
	title.texture = tex
	title.centered = false
	title.position = Vector2((320.0 - tex.get_width()) / 2.0, 3)
	_board.add_child(title)
	var layer := Node2D.new()
	layer.name = "TextLayer"
	_board.add_child(layer)
	# party strip: HP line, PSP line for casters, status under each of
	# the four slots (sheet strip is a 2x2 grid: slots 0,1 top; 2,3
	# bottom); rows shift at refresh time
	var strip_pos := [Vector2(53, 66), Vector2(104, 66), Vector2(53, 126), Vector2(104, 126)]
	for i in 4:
		_rows.append(_make_row(layer, strip_pos[i]))
		_rows.append(_make_row(layer, strip_pos[i] + Vector2(0, 8)))
		_rows.append(_make_row(layer, strip_pos[i] + Vector2(0, 16)))
	# name plate
	_rows.append(_make_row(layer, Vector2(155, 37)))
	# stats
	for i in 6:
		_rows.append(_make_row(layer, Vector2(150, 52 + 7 * i)))
	# gender+race, alignment
	_rows.append(_make_row(layer, Vector2(150, 95)))
	_rows.append(_make_row(layer, Vector2(150, 102)))
	# class list, levels, EXP, HP, PSI, AC+DAM
	_rows.append(_make_row(layer, Vector2(150, 110)))
	_rows.append(_make_row(layer, Vector2(150, 117)))
	_rows.append(_make_row(layer, Vector2(150, 124)))
	_rows.append(_make_row(layer, Vector2(150, 131)))
	_rows.append(_make_row(layer, Vector2(150, 138)))
	_rows.append(_make_row(layer, Vector2(150, 145)))
	# ink colours off the oracle: white for name/stats/origin/levels,
	# gold for the EXP/HP/PSP/AC block, blue for PSP values
	for i in range(12, 23):
		if i != 21:
			_rows[i].ink = ROW_INK

func _make_row(parent: Node2D, pos: Vector2) -> TextBlitter:
	var row := TextBlitter.new()
	row.position = pos
	row.ink = ROW_GOLD
	row.relief = ROW_RELIEF
	parent.add_child(row)
	return row

func _set_row(i: int, s: String) -> void:
	_rows[i].text = s

func _refresh() -> void:
	for si in 4:
		var m: Dictionary = PartyData.MEMBERS[si]
		var base := 66 if si < 2 else 126
		var x := 53 if si % 2 == 0 else 104
		var has_psi: bool = int(m["psi"][1]) > 0
		_rows[si * 3].text = "%d/%d" % [m["hp"], m["max"]]
		_rows[si * 3].position = Vector2(x, base)
		if has_psi:
			_rows[si * 3 + 1].text = "%d/%d" % [m["psi"][0], m["psi"][1]]
			_rows[si * 3 + 1].position = Vector2(x, base + 8)
			_rows[si * 3 + 1].ink = ROW_PSI
			_rows[si * 3 + 1].visible = true
			_rows[si * 3 + 2].text = str(m["status"])
			_rows[si * 3 + 2].position = Vector2(x, base + 16)
			_rows[si * 3 + 2].visible = true
		else:
			_rows[si * 3 + 1].visible = false
			_rows[si * 3 + 2].text = str(m["status"])
			_rows[si * 3 + 2].position = Vector2(x, base + 8)
			_rows[si * 3 + 2].visible = true
	# selected member's party box takes the yellow frame (ICON 11100 f3)
	for b in _buttons:
		var iid: int = int(b["id"])
		if iid >= 11300 and iid <= 11303:
			_set_frame(b, 3 if iid - 11300 == selected else 0)
	var m: Dictionary = PartyData.MEMBERS[selected]
	_set_row(12, str(m["name"]))
	var labels := ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
	var st: Array = m["stats"]
	for i in 6:
		_set_row(13 + i, "%s: %d" % [labels[i], st[i]])
	_set_row(19, "%s %s" % [m["gender"], m["race"]])
	_set_row(20, str(m["align"]))
	var classes: Array = m["classes"]
	var cls_line: String = ""
	for i in classes.size():
		cls_line += classes[i] + ("/" if i < classes.size() - 1 else "")
	_set_row(21, cls_line)
	var lv_line: String = ""
	for i in m["levels"].size():
		lv_line += str(m["levels"][i]) + ("/" if i < m["levels"].size() - 1 else "")
	_set_row(22, lv_line)
	_set_row(23, "EXP:%d (%d)" % [m["exp"], m["exp_next"]])
	_set_row(24, "HP:  %d/%d" % [m["hp"], m["max"]])
	_set_row(25, "PSI: %d/%d" % [m["psi"][0], m["psi"][1]])
	_set_row(26, "AC: %d  DAM: %s" % [m["ac"], m["dmg"]])
	if mode != Mode.VIEW:
		# USE/EFFECTS: the info block gives way to the spell grid or an
		# empty panel; only the name plate stays
		for i in range(13, 27):
			_rows[i].visible = false
		if mode == Mode.USE:
			var casters := _caster_classes()
			if cast_class == "" and not casters.is_empty():
				cast_class = casters[0]
			_set_spell_grid()
			_set_bar_texts()

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		var code: int = event.keycode
		if code >= KEY_1 and code <= KEY_4:
			selected = code - KEY_1
			_refresh()
	elif event is InputEventMouseButton and event.pressed \
			and event.button_index == MOUSE_BUTTON_LEFT:
		var pos: Vector2 = _board.get_global_transform().affine_inverse() * event.position
		for b in _buttons:
			var iid: int = int(b["id"])
			if iid >= 11300 and iid <= 11303 and (b["rect"] as Rect2).has_point(pos):
				selected = iid - 11300
				_refresh()
				return
