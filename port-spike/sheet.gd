# SheetScreen: WIND 11500 View Character. Yellow FONT/100 lines on the
# stone plate: name, six stats, gender+race, alignment, the class list
# with levels (level-up pending class in red), EXP, HP, PSI, AC+DAM.
# Party strip rows mirror the inventory's four slots.
extends WindScreen
class_name SheetScreen

const ROW_INK := Color8(214, 214, 222)
const ROW_RELIEF := Color8(24, 24, 40)
const ROW_GOLD := Color8(230, 200, 60)
const ROW_PSI := Color8(120, 150, 235)

var selected := 1
var _rows: Array[TextBlitter] = []

func _init() -> void:
	window_id = 11500

func _ready() -> void:
	super._ready()
	_build_rows()
	attach_party_figures(PartyData.MEMBERS, InventoryScreen._db()["party"])
	_refresh()

func _build_rows() -> void:
	var title := Sprite2D.new()
	title.texture = load("res://generated/ui/bmp20079.png")
	title.centered = false
	title.position = Vector2(55, 3)
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
