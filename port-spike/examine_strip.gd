# ExamineStrip: WIND 15500, the item examine strip (111x87, bg 15000).
# Engine truth (port-digs-2026-09-21.md): the three buttons are the
# interact strip's talk/steal/give glyphs (15301/15303/15302, shared
# handlers) and INFO 15304 toggles plate vs description; the engine
# cycles nothing. The cycle-to-browse behaviour below is a port
# affordance for opening the strip on a member's carried item, a
# context the engine never uses; INFO opening the view-item screen
# 15502 is likewise a port route onto a real engine surface.
extends WindScreen
class_name ExamineStrip

signal info_requested(obj_id: int)

var item_ids: Array = []  # object ids of the member's carried items
var index := 0

var _icon: Sprite2D
var _name_t: TextBlitter
var _count_t: TextBlitter

func _init(p_item_ids: Array, p_index := 0) -> void:
	window_id = 15500
	item_ids = p_item_ids
	index = clampi(p_index, 0, maxi(item_ids.size() - 1, 0))

func _ready() -> void:
	# the 15200 bevel ships 145x87, larger than the 111x87 window
	skip_apfm = [15200]
	super._ready()
	var clipped := WindScreen.BevelPanel.new()
	clipped.rect = Rect2(Vector2.ZERO, Vector2(111, 87))
	clipped.seed_key = 15200
	_board.add_child(clipped)
	_board.move_child(clipped, 1)
	_icon = Sprite2D.new()
	_icon.centered = false
	_icon.position = Vector2(46, 14)
	_board.add_child(_icon)
	_name_t = TextBlitter.new()
	_name_t.ink = Color8(230, 200, 60)
	_name_t.relief = Color8(24, 24, 40)
	_name_t.position = Vector2(8, 40)
	_board.add_child(_name_t)
	_count_t = TextBlitter.new()
	_count_t.ink = Color8(154, 154, 178)
	_count_t.relief = Color8(24, 24, 40)
	_count_t.position = Vector2(8, 52)
	_board.add_child(_count_t)
	_refresh()

func _refresh() -> void:
	if item_ids.is_empty():
		_icon.visible = false
		_name_t.text = "NO ITEMS"
		_count_t.text = ""
		return
	var oid := int(item_ids[index])
	var info: Dictionary = InventoryScreen.obj_info(oid)
	_icon.texture = InventoryScreen.texture_for(str(info["png"]))
	_name_t.text = str(info.get("name", "?")).to_upper()
	_count_t.text = "%d / %d" % [index + 1, item_ids.size()]

func _cycle(dir: int) -> void:
	if item_ids.is_empty():
		return
	index = wrapi(index + dir, 0, item_ids.size())
	_refresh()

func _on_item(item: Dictionary) -> void:
	match int(item["id"]):
		15301:
			_cycle(-1)
		15302, 15303:
			_cycle(1)
		15304:
			if not item_ids.is_empty():
				info_requested.emit(int(item_ids[index]))
