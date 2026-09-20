# MapScreen: the engine's overhead map (no WIND exists; O key / game
# menu 10305). BMP 10003 plate centred on black + the region minimap
# rendered 2:1 from the live tileset (each tile = its atlas tile's
# centre colour), cropped to the plate interior, matching the oracle
# map_arena.png.
extends Node2D
class_name MapScreen

const BOARD := Vector2(320, 200)
const PLATE := Vector2(265, 178)
const INTERIOR_POS := Vector2(14, 12)  # plate border inset
const SCALE := 2

static var _minimap_cache := {}

var region_id := 0
var _board: Node2D

func _init(p_region := 0) -> void:
	region_id = p_region

func _ready() -> void:
	_board = Node2D.new()
	add_child(_board)
	await get_tree().process_frame
	await get_tree().process_frame
	get_viewport().size_changed.connect(_fit)
	_fit()
	_layout()

func _fit() -> void:
	var vp := get_viewport_rect().size
	var k := maxi(int(minf(vp.x / BOARD.x, vp.y / BOARD.y)), 1)
	_board.scale = Vector2(k, k)
	_board.position = (vp - BOARD * k) / 2.0

static func build_minimap(rid: int) -> Image:
	if _minimap_cache.has(rid):
		return _minimap_cache[rid]
	var f := FileAccess.open("res://generated/r%d/region.json" % rid, FileAccess.READ)
	if f == null:
		return null
	var data: Dictionary = JSON.parse_string(f.get_as_text())
	var atlas: Image = (load("res://generated/r%d/tiles_atlas.png" % rid) as Texture2D).get_image()
	var img := Image.create(128, 98, false, Image.FORMAT_RGBA8)
	img.fill(Color(0, 0, 0, 0))
	for c in data["cells"]:
		# average the whole 16x16 tile art: at 2:1 the wall variants
		# keep their alternating pattern, as in the oracle capture
		var acc := Color(0, 0, 0, 0)
		for py in range(0, 16, 4):
			for px in range(0, 16, 4):
				acc += atlas.get_pixel(int(c[2]) * 16 + px, int(c[3]) * 16 + py)
		img.set_pixel(int(c[0]), int(c[1]), acc / 16.0)
	_minimap_cache[rid] = img
	return img

func _layout() -> void:
	var bg := Sprite2D.new()
	bg.texture = load("res://generated/ui/map_10003.png")
	bg.centered = false
	bg.position = (BOARD - PLATE) / 2.0
	_board.add_child(bg)
	var full := build_minimap(region_id)
	if full == null:
		return
	# crop the region grid to the plate interior at 2:1, from the
	# region origin: the oracle shows the fight pit at the upper left
	var interior := PLATE - INTERIOR_POS * 2.0
	var crop_cols := mini(int(interior.x) / SCALE, 128)
	var crop_rows := mini(int(interior.y) / SCALE, 98)
	var cropped := full.get_region(Rect2i(0, 0, crop_cols, crop_rows))
	var minimap := Sprite2D.new()
	minimap.texture = ImageTexture.create_from_image(cropped)
	minimap.centered = false
	minimap.scale = Vector2(SCALE, SCALE)
	minimap.position = bg.position + INTERIOR_POS
	_board.add_child(minimap)
