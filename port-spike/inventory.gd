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

var _rows: Array[TextBlitter] = []

func _init() -> void:
	window_id = 13500

func _ready() -> void:
	super._ready()
	_build_rows()
	_refresh()

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
