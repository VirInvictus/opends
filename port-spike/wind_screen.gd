# WindScreen: draws one WIND window from generated/ui/winds.json on a
# 320x200 board, scaled to the viewport the way the engine's windows
# sit on the screen. Border plate or APFM bevels are furniture; BUTNs
# are stateful hot zones (icon faces stay unflattened: frame 0 rests,
# 1 highlights, 2 presses, 3 selects, per the state model); EBOXes are
# TextBlitter targets. One window id = one build, no hand layout.
class_name WindScreen
extends Node2D

signal item_activated(item: Dictionary)

const BOARD := Vector2(320, 200)
# Stone palette sampled off the sheet oracle capture; the APFM panels
# are dithered stone with 1px bevel edges (light top/left, dark
# bottom/right; sunken cells reverse it).
const BASE_TONES := [
	Color8(89, 89, 113), Color8(77, 77, 105),
	Color8(69, 69, 97), Color8(57, 57, 85),
]
const EDGE_LIGHT := Color8(194, 194, 219)
const EDGE_DARK := Color8(32, 32, 57)

static var _winds: Dictionary

var window_id := 0
var data: Dictionary = {}
var _buttons: Array[Dictionary] = []
## Items whose shipped faces are flash variants only: the resting art
## is engine-printed text (e.g. the creation class list), so the port
## draws no sprite for them.
var no_resting_art: Array[int] = []
## APFM ids the engine does not paint in normal play (belt quick-cells
## and container cells only appear in their modes; 13200 is the centre
## card the port furnishes itself). Skipped at layout time.
var skip_apfm: Array[int] = []
var _hovered := 0
var _pressed := 0
var _board: Node2D
var _origin := Vector2.ZERO


static func _ensure_winds() -> void:
	if not _winds.is_empty():
		return
	var f := FileAccess.open("res://generated/ui/winds.json", FileAccess.READ)
	_winds = JSON.parse_string(f.get_as_text())


static func winds() -> Dictionary:
	_ensure_winds()
	return _winds


func _init(p_id := 0) -> void:
	window_id = p_id


func _ready() -> void:
	_ensure_winds()
	data = _winds.get(str(window_id), {})
	assert(not data.is_empty(), "no such WIND: %d" % window_id)
	_board = Node2D.new()
	add_child(_board)
	_layout()
	get_viewport().size_changed.connect(_fit)
	_fit()


## Origin of the window inside the board (window x/y from the chunk).
func board_origin() -> Vector2:
	return _origin


func item_by_id(iid: int) -> Dictionary:
	for it in data["items"]:
		if int(it["id"]) == iid:
			return it
	return {}


func _layout() -> void:
	_origin = Vector2(float(data["x"]), float(data["y"]))
	var bg: String = data.get("bg_png", "")
	if bg != "":
		var bgs := Sprite2D.new()
		bgs.texture = load("res://generated/ui/" + bg)
		bgs.centered = false
		bgs.position = _origin
		_board.add_child(bgs)
	var plate: String = data.get("border_png", "")
	if plate != "":
		var s := Sprite2D.new()
		s.texture = load("res://generated/ui/" + plate)
		s.centered = false
		s.position = _origin
		_board.add_child(s)
	# The engine paints APFM panels first, then buttons, and dynamic text
	# always last (the print service draws over window furniture), even
	# though the item array interleaves them arbitrarily.
	for pass_kind in ["APFM", "BUTN", "EBOX"]:
		for it in data["items"]:
			if str(it["type"]) != pass_kind:
				continue
			var pos := _origin + Vector2(float(it["x"]), float(it["y"]))
			match pass_kind:
				"APFM":
					if int(it["id"]) in skip_apfm:
						continue
					var b := BevelPanel.new()
					b.position = pos
					b.rect = Rect2(Vector2.ZERO, Vector2(float(it.get("w", 4)), float(it.get("h", 4))))
					b.sunken = float(it.get("w", 0)) <= 24.0 and float(it.get("h", 0)) <= 24.0
					b.seed_key = int(it["id"])
					_board.add_child(b)
				"EBOX":
					var t := TextBlitter.new()
					t.name = "EBOX%d" % int(it["id"])
					t.position = pos
					_board.add_child(t)
				"BUTN":
					var frames: Array = it.get("icon_frames", [])
					var label: String = it.get("text", "")
					if (frames.is_empty() and label == "") or int(it["id"]) in no_resting_art:
						# invisible hot zone (race cycle, steppers): no art
						_buttons.append({
							"item": it,
							"rect": Rect2(pos, Vector2(float(it.get("w", 8)), float(it.get("h", 8)))),
							"sprite": null,
							"frames": frames,
							"frame": 0,
							"id": int(it["id"]),
							"userid": int(it.get("userid", 0)),
						})
						continue
					var s := Sprite2D.new()
					s.centered = false
					s.position = pos
					if not frames.is_empty():
						s.texture = load("res://generated/ui/" + str(frames[0]["png"]))
					else:
						var b2 := BevelPanel.new()
						b2.rect = Rect2(Vector2.ZERO, Vector2(float(it.get("w", 8)), float(it.get("h", 8))))
						b2.sunken = false
						b2.seed_key = int(it["id"])
						s.add_child(b2)
					_board.add_child(s)
					if label != "":
						var lt := TextBlitter.new()
						lt.position = Vector2(float(it.get("textx", 0)), float(it.get("texty", 0)))
						lt.text = label
						lt.ink = Color8(24, 24, 24)
						s.add_child(lt)
					_buttons.append({
						"item": it,
						"rect": Rect2(pos, Vector2(float(it.get("w", 8)), float(it.get("h", 8)))),
						"sprite": s,
						"frames": frames,
						"frame": 0,
						"id": int(it["id"]),
						"userid": int(it.get("userid", 0)),
					})


func accl_keys() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for it in data["items"]:
		if str(it["type"]) == "ACCL":
			var c: Array = it.get("keys", [])
			out.assign(c)
	return out


func _fit() -> void:
	var vp := get_viewport_rect().size
	var k := minf(vp.x / BOARD.x, vp.y / BOARD.y)
	_board.scale = Vector2(k, k)
	_board.position = (vp - BOARD * k) / 2.0


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		var pos: Vector2 = _board.get_global_transform().affine_inverse() * event.position
		if event.pressed:
			for b in _buttons:
				if (b["rect"] as Rect2).has_point(pos):
					_set_frame(b, 2)
					_pressed = b["id"]
					break
		elif _pressed != 0:
			for b in _buttons:
				if int(b["id"]) == _pressed:
					_set_frame(b, 0)
					if (b["rect"] as Rect2).has_point(pos):
						item_activated.emit(b["item"])
					break
			_pressed = 0
	elif event is InputEventMouseMotion and _pressed == 0:
		var pos: Vector2 = _board.get_global_transform().affine_inverse() * event.position
		var hover := 0
		for b in _buttons:
			if (b["rect"] as Rect2).has_point(pos):
				hover = b["id"]
				break
		if hover != _hovered:
			_hovered = hover
			for b in _buttons:
				if _pressed != 0 and int(b["id"]) == _pressed:
					continue
				_set_frame(b, 1 if int(b["id"]) == hover else 0)


func _set_frame(b: Dictionary, f: int) -> void:
	var frames: Array = b["frames"]
	if frames.is_empty():
		return
	# 3-frame faces are ink swaps (0 normal, 1 highlight, 2 pressed);
	# 4-frame faces: 0 normal, 1 hover, 2 blink/blank, 3 selected. Never
	# show a 1x1 dummy frame (w < 8).
	var n := frames.size()
	var idx := clampi(f, 0, n - 1)
	var fr: Dictionary = frames[idx]
	if int(fr["w"]) < 8:
		idx = 0
	if int(b["frame"]) == idx:
		return
	b["frame"] = idx
	var spr: Sprite2D = b["sprite"]
	spr.texture = load("res://generated/ui/" + str(frames[idx]["png"]))


## The engine's press-flash: 1<->2 for a few ticks; call from screens.
func flash(item_id: int, ticks := 4) -> void:
	for b in _buttons:
		if int(b["id"]) == item_id:
			_set_frame(b, 2)
			await get_tree().process_frame
			await get_tree().process_frame
			_set_frame(b, 0)
			return


## First-letter accelerator dispatch (the popup model: NEW/QUIT/CANCEL).
func hit_letter(code: int) -> Dictionary:
	for b in _buttons:
		var label: String = b["item"].get("text", "")
		if label != "" and label.unicode_at(0) == code:
			return b["item"]
	return {}


class BevelPanel:
	extends Node2D

	var rect := Rect2()
	var sunken := false
	var seed_key := 0

	func _draw() -> void:
		var r := Rect2(Vector2.ZERO, rect.size)
		draw_rect(r, _tone(r.position), true)
		# sparse dither for the stone grain
		var rng := RandomNumberGenerator.new()
		rng.seed = seed_key * 2654435761 + int(rect.size.x) * 97 + int(rect.size.y)
		var grains := int(rect.size.x * rect.size.y / 6.0)
		for i in grains:
			var p := Vector2(rng.randf_range(0, rect.size.x - 1), rng.randf_range(0, rect.size.y - 1))
			draw_rect(Rect2(p, Vector2(1, 1)), BASE_TONES[rng.randi() % BASE_TONES.size()], true)
		var light := EDGE_DARK if sunken else EDGE_LIGHT
		var dark := EDGE_LIGHT if sunken else EDGE_DARK
		draw_rect(Rect2(r.position, Vector2(r.size.x, 1)), light, true)
		draw_rect(Rect2(r.position, Vector2(1, r.size.y)), light, true)
		draw_rect(Rect2(Vector2(r.position.x, r.end.y - 1), Vector2(r.size.x, 1)), dark, true)
		draw_rect(Rect2(Vector2(r.end.x - 1, r.position.y), Vector2(1, r.size.y)), dark, true)

	func _tone(_p: Vector2) -> Color:
		return BASE_TONES[0]
