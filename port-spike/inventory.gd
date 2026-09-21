# InventoryScreen: WIND 13500. Backdrop is the oracle-derived plate with
# dynamic text in-painted away; the party strip, name plate, stat panel
# and money draw live from the member records (screen-flow.md 8.3).
# Member switching: click the four party slots or keys 1-4.
# Items draw the engine way (export_items.py): icon = the base object's
# OJFF bmp_id sprite; empty paperdoll cells show the BMP 13007 slot
# glyphs (frames 9+slot); a held icon rides the cursor; f4 is the drop
# target selection and f6 the illegal-drop X.
extends WindScreen
class_name InventoryScreen

const ROW_INK := Color8(214, 214, 222)
const ROW_RELIEF := Color8(24, 24, 40)
const ROW_GOLD := Color8(230, 200, 60)

static var _idb: Dictionary

var members: Array = PartyData.MEMBERS
var selected := 1
var gold := 0
var held := 0  # object id carried on the cursor, 0 = empty hands
var _held_icon: Sprite2D
var _cells := {}  # member index -> {slot: {"base": Sprite2D, "icon": Sprite2D}}
var _rows: Array[TextBlitter] = []
var _hover_slot := -1

# slot -> placement code for the 14 paperdoll slots (mined table at
# 0x40A70): arm, ammo, missile, hand, finger, waist, legs, head, neck,
# chest, hand2, finger2, cloak, foot
const PAPERDOLL_CODES := [3, 11, 12, 5, 9, 2, 10, 6, 7, 1, 5, 9, 8, 4]


static func _db() -> Dictionary:
	if _idb.is_empty():
		var f := FileAccess.open("res://generated/ui/item_icons.json", FileAccess.READ)
		_idb = JSON.parse_string(f.get_as_text())
	return _idb


static func obj_info(oid: int) -> Dictionary:
	return _db()["items"].get(str(oid), {})


func _cell_pos(slot: int) -> Vector2:
	# cell id = slot + 11216 for the paperdoll (0..13) and
	# slot + 11214 for the backpack (14..25): ids 11230..11241
	var id: int = 11216 + slot if slot < 14 else 11214 + slot
	for it in data["items"]:
		if it["type"] == "APFM" and int(it["id"]) == id:
			return Vector2(float(it["x"]), float(it["y"]))
	return Vector2.ZERO


func _init() -> void:
	window_id = 13500
	# the whole stone/leather plate (cells, slot glyphs, parchment,
	# party portraits, figure) regenerates from the oracle capture
	# (bg_13500.png, drawn before layout); every APFM stays unpainted
	skip_apfm = []
	for i in range(11200, 11270):
		skip_apfm.append(i)
	skip_apfm.append(13200)


func _ready() -> void:
	super._ready()
	_seed_items()
	_build_rows()
	_build_cells()
	_build_held_icon()
	attach_party_figures(members, _db()["party"])
	_ensure_figure()
	_refresh()

## The centre card shows the selected member's standing figure
## (RESOURCE BMP 20000 + (race_i-1)*2 + (gender_i-1); the dig matched
## BMP 20013 = K'tarchek against the oracle 100.0%).
var _figure: Sprite2D

func _ensure_figure() -> void:
	if _figure != null:
		return
	_figure = Sprite2D.new()
	_figure.centered = false
	_figure.position = Vector2(81, 49)  # card (75,36) + (6,13)
	_board.add_child(_figure)

func _refresh_figure() -> void:
	_ensure_figure()
	var m: Dictionary = members[selected]
	var fid := 20000 + (int(m.get("race_i", 1)) - 1) * 2 + (int(m.get("gender_i", 1)) - 1)
	var tex_path := "res://generated/ui/figure_%d.png" % fid
	if ResourceLoader.exists(tex_path):
		_figure.texture = load(tex_path)


static func texture_for(png: String) -> Texture2D:
	return load("res://generated/ui/" + png)


## Seed the demo inventories from the exported kits (docs/
## creature-inventories-ds1.md picks). Each item goes to the first
## legal paperdoll slot for its placement code, else the backpack.
func _seed_items() -> void:
	for mi in members.size():
		var m: Dictionary = members[mi]
		if m.has("cells") and not (m["cells"] as Array).is_empty():
			continue
		var cells: Array = []
		for i in 26:
			cells.append(null)
		for oid in _db()["kits"].get(str(mi), []):
			var place := int(obj_info(int(oid)).get("place", 0))
			var slot := -1
			var s := PAPERDOLL_CODES.find(place)
			while s >= 0:
				if cells[s] == null:
					slot = s
					break
				s = PAPERDOLL_CODES.find(place, s + 1)
			if slot < 0:
				for b in range(14, 26):
					if cells[b] == null:
						slot = b
						break
			if slot >= 0:
				cells[slot] = {"obj": int(oid)}
		m["cells"] = cells


func _build_held_icon() -> void:
	_held_icon = Sprite2D.new()
	_held_icon.centered = false
	_held_icon.visible = false
	_board.add_child(_held_icon)


func _process(_delta: float) -> void:
	if _held_icon == null:
		return
	if held == 0:
		if _hover_slot != -1:
			_hover_slot = -1
			_refresh_cells()
		return
	_held_icon.position = _held_pos()
	var s := _cell_at(_held_pos())
	if s != _hover_slot:
		_hover_slot = s
		_refresh_cells()


func _held_pos() -> Vector2:
	return (_board.get_global_transform().affine_inverse() * get_global_mouse_position())


func _build_cells() -> void:
	var layer := Node2D.new()
	layer.name = "ItemLayer"
	_board.add_child(layer)
	for mi in 4:
		var per := {}
		for slot in 26:
			var base := Sprite2D.new()
			base.centered = false
			base.visible = false
			layer.add_child(base)
			var icon := Sprite2D.new()
			icon.centered = false
			icon.visible = false
			base.add_child(icon)
			per[slot] = {"base": base, "icon": icon}
		_cells[mi] = per


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
	parent.add_child(row)
	return row


func _set_row(i: int, s: String) -> void:
	_rows[i].text = s


func _refresh_cells() -> void:
	var m: Dictionary = members[selected]
	var per: Dictionary = _cells[selected]
	var cell: Dictionary = _db()["cell"]
	var frames: Array = cell["frames"]
	var glyph0 := int(cell["glyph_frame0"])
	for slot in per:
		var base: Sprite2D = per[slot]["base"]
		var icon: Sprite2D = per[slot]["icon"]
		base.position = _cell_pos(slot)
		var item: Variant = m["cells"][slot]
		# base tile: drop-target selection/X while holding, plain under
		# an item, the slot glyph when empty
		var f: int = (glyph0 + slot) if slot < 14 else int(cell["plain"])
		if item != null:
			f = int(cell["plain"])
		if slot == _hover_slot and held != 0:
			f = int(cell["select_yellow"]) if _legal(slot, {"obj": held}) \
				else int(cell["illegal"])
		base.texture = texture_for(str(frames[f]["png"]))
		base.visible = true
		if item != null:
			var info: Dictionary = obj_info(int(item["obj"]))
			icon.texture = texture_for(str(info["png"]))
			icon.position = (Vector2(18, 18) - Vector2(float(info["w"]), float(info["h"]))) / 2.0
			icon.visible = true
		else:
			icon.visible = false


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
	_set_row(21, "%d$" % gold)
	_refresh_figure()
	# selected member's party box takes the yellow frame (ICON 11100 f3)
	for b in _buttons:
		var iid: int = int(b["id"])
		if iid >= 11300 and iid <= 11303:
			_set_frame(b, 3 if iid - 11300 == selected else 0)
	_refresh_cells()
	if _held_icon != null:
		var vis := held != 0
		_held_icon.visible = vis
		if vis:
			var info: Dictionary = obj_info(held)
			_held_icon.texture = texture_for(str(info["png"]))


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
	var place := int(obj_info(int(item.get("obj", 0))).get("place", 0))
	return PAPERDOLL_CODES[slot] == place


func _click_cell(slot: int) -> void:
	var m: Dictionary = members[selected]
	var cells: Array = m["cells"]
	if held == 0:
		if cells[slot] != null:
			held = int(cells[slot]["obj"])
			cells[slot] = null
	elif cells[slot] == null:
		if _legal(slot, {"obj": held}):
			cells[slot] = {"obj": held}
			held = 0
	else:
		# swap if the occupant is legal where the held item came from
		if _legal(slot, {"obj": held}):
			var tmp: Variant = cells[slot]
			cells[slot] = {"obj": held}
			held = int(tmp["obj"])
	_hover_slot = -1
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
		var slot := _cell_at(pos)
		if slot >= 0:
			_click_cell(slot)
