# InventoryScreen: WIND 13500. Backdrop is the oracle-derived plate with
# dynamic text in-painted away; the party strip, name plate, stat panel
# and money draw live from the member records (screen-flow.md 8.3).
# Member switching: click the four party slots or keys 1-4.
extends WindScreen
class_name InventoryScreen

const STONE := Color8(112, 112, 134)
const ROW_INK := Color8(214, 214, 222)
const ROW_RELIEF := Color8(24, 24, 40)
const ROW_GOLD := Color8(230, 200, 60)

var members: Array = PartyData.MEMBERS
var selected := 1
var gold := 0
var held := ""  # name of the item carried on the cursor, "" = empty
var held_kind := ""  # placement code of the held item
var _held_tag: TextBlitter
var _cell_tags := {}  # member index -> {slot: TextBlitter}
var _rows: Array[TextBlitter] = []

# slot -> placement code for the 14 paperdoll slots (mined table at
# 0x40A70): arm, ammo, missile, hand, finger, waist, legs, head, neck,
# chest, hand2, finger2, cloak, foot
const PAPERDOLL_CODES := [3, 11, 12, 5, 9, 2, 10, 6, 7, 1, 5, 9, 8, 4]
const DEMO_ITEMS := {
	0: {"name": "Long Sword", "place": 5},
	2: {"name": "Long Bow", "place": 12},
}

func _cell_pos(slot: int) -> Vector2:
	# cell id = slot + 11216 for the paperdoll (0..13) and
	# slot + 11216 for the backpack (14..25): ids 11230..11241
	var id: int = 11216 + slot if slot < 14 else 11214 + slot
	for it in data["items"]:
		if it["type"] == "APFM" and int(it["id"]) == id:
			return Vector2(float(it["x"]), float(it["y"]))
	return Vector2.ZERO

func _init() -> void:
	window_id = 13500

func _ready() -> void:
	super._ready()
	_seed_items()
	_build_rows()
	_build_cell_tags()
	_build_held_tag()
	_refresh()

## Seed the demo inventories: two carried weapons on members 0 and 2.
## The 26-slot cell model (14 paperdoll + 12 backpack) is the mined
## structure; instances carry their placement code for legality.
func _seed_items() -> void:
	for m in members:
		if not m.has("cells"):
			m["cells"] = []
			for i in 26:
				m["cells"].append(null)
	var cermak: Dictionary = members[0]
	cermak["cells"][14] = {"name": "Long Sword", "place": 5}
	var saria: Dictionary = members[2]
	saria["cells"][14] = {"name": "Long Bow", "place": 12}

func _build_held_tag() -> void:
	_held_tag = TextBlitter.new()
	_held_tag.ink = ROW_GOLD
	_held_tag.relief = ROW_RELIEF
	_held_tag.visible = false
	_board.add_child(_held_tag)

func _process(_delta: float) -> void:
	if _held_tag != null and held != "":
		_held_tag.position = _held_pos()

func _held_pos() -> Vector2:
	return (_board.get_global_transform().affine_inverse() * get_global_mouse_position())

func _build_cell_tags() -> void:
	for mi in 4:
		_cell_tags[mi] = {}
		for slot in 26:
			var t := TextBlitter.new()
			t.ink = ROW_INK
			t.relief = ROW_RELIEF
			t.visible = false
			_board.add_child(t)
			_cell_tags[mi][slot] = t

func _build_rows() -> void:
	var layer := Node2D.new()
	layer.name = "TextLayer"
	_board.add_child(layer)
	# party strip: HP line + status line under each of the four slots
	for i in 4:
		_rows.append(_make_row(layer, Vector2(12, 40 + 48 * i)))
		_rows.append(_make_row(layer, Vector2(12, 48 + 48 * i)))
	# name plate (EBOX 4003 position)
	_rows.append(_make_row(layer, Vector2(59, 5)))
	# ability lines are engine-printed yellow, label and value together
	for i in 6:
		_rows.append(_make_row(layer, Vector2(236, 53 + 7 * i), ROW_GOLD))
	# PSI / AC / weapon readout lines
	_rows.append(_make_row(layer, Vector2(236, 99), ROW_GOLD))
	_rows.append(_make_row(layer, Vector2(236, 113), ROW_GOLD))
	for i in 4:
		_rows.append(_make_row(layer, Vector2(236, 121 + 8 * i), ROW_GOLD))
	# money
	_rows.append(_make_row(layer, Vector2(60, 184)))

func _make_row(parent: Node2D, pos: Vector2, ink: Color = ROW_INK) -> TextBlitter:
	var row := TextBlitter.new()
	row.position = pos
	row.ink = ink
	row.relief = ROW_RELIEF
	row.backing = STONE
	row.backing_size = Vector2(64, 11)
	parent.add_child(row)
	return row

func _set_row(i: int, s: String) -> void:
	_rows[i].text = s

func _refresh_cell_tags() -> void:
	var m: Dictionary = members[selected]
	var tags: Dictionary = _cell_tags[selected]
	for slot in tags:
		var t: TextBlitter = tags[slot]
		var item: Variant = m["cells"][slot]
		if item == null:
			t.visible = false
		else:
			t.text = str(item["name"]).substr(0, 2).to_upper()
			t.position = _cell_pos(slot) + Vector2(2, 2)
			t.visible = true

func _refresh() -> void:
	for mi in 4:
		var m: Dictionary = members[mi]
		_set_row(mi * 2, "%d/%d" % [m["hp"], m["max"]])
		_set_row(mi * 2 + 1, str(m["status"]))
	var m: Dictionary = members[selected]
	_set_row(8, str(m["name"]))
	var st: Array = m["stats"]
	var labels := ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
	for i in 6:
		_set_row(9 + i, "%s: %d" % [labels[i], st[i]])
	_set_row(15, "PSI: %d/%d" % [m["psi"][0], m["psi"][1]])
	_set_row(16, "AC: %d" % m["ac"])
	var wl: Array = m.get("weapon_lines", ["", "", "", ""])
	_set_row(17, wl[0])
	_set_row(18, wl[1])
	_set_row(19, wl[2])
	_set_row(20, wl[3])
	_refresh_cell_tags()
	if _held_tag != null:
		_held_tag.text = held
		_held_tag.visible = held != ""

## slot under a board position, or -1. Paperdoll = slots 0..13
## (ids 11216..11229), backpack = slots 14..25 (ids 11230..11241).
func _cell_at(pos: Vector2) -> int:
	for it in data["items"]:
		if it["type"] != "APFM":
			continue
		var iid: int = int(it["id"])
		var slot := -1
		if iid >= 11216 and iid <= 11229:
			slot = iid - 11216
		elif iid >= 11230 and iid <= 11241:
			slot = 14 + iid - 11230
		if slot < 0:
			continue
		var r := Rect2(Vector2(float(it["x"]), float(it["y"])), Vector2(18, 18))
		if r.has_point(pos):
			return slot
	return -1

func _legal(slot: int, item: Dictionary) -> bool:
	if slot >= 14:
		return true  # backpack takes anything
	return PAPERDOLL_CODES[slot] == int(item["place"])

func _click_cell(slot: int) -> void:
	var m: Dictionary = members[selected]
	var cells: Array = m["cells"]
	if held == "":
		if cells[slot] != null:
			held = str(cells[slot]["name"])
			held_kind = str(cells[slot]["place"])
			cells[slot] = null
	elif cells[slot] == null:
		if slot < 14 and PAPERDOLL_CODES[slot] != held_kind:
			pass  # wrong body slot: the engine just refuses the drop
		else:
			cells[slot] = {"name": held, "place": held_kind}
			held = ""
	else:
		# swap if the occupant is legal where the held item came from
		if slot < 14 and PAPERDOLL_CODES[slot] != held_kind:
			pass
		else:
			var tmp: Variant = cells[slot]
			cells[slot] = {"name": held, "place": held_kind}
			held = str(tmp["name"])
	_refresh()


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
