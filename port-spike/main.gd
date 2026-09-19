# One-region Godot spike: rebuild the exported region and snap it.
#
# Fills the TileMapLayer from generated/region.json, adds wall and
# entity sprites at their exported draw positions, and (when SPIKE_SHOT
# is set) saves a viewport screenshot and quits.
extends Node2D


func _ready() -> void:
	var f := FileAccess.open("res://generated/region.json", FileAccess.READ)
	var data: Dictionary = JSON.parse_string(f.get_as_text())

	var tiles: TileMapLayer = $Tiles
	for c in data["cells"]:
		tiles.set_cell(Vector2i(c[0], c[1]), 0, Vector2i(int(c[2]), int(c[3])))

	var walls: Node2D = $Walls
	for w in data["walls"]:
		var s := Sprite2D.new()
		s.texture = load("res://generated/" + str(w["png"]))
		s.centered = false
		s.position = Vector2(w["x"], w["y"])
		walls.add_child(s)

	var entities: Node2D = $Entities
	for e in data["entities"]:
		var s := Sprite2D.new()
		s.texture = load("res://generated/" + str(e["png"]))
		s.centered = false
		s.position = Vector2(e["x"], e["y"])
		s.flip_h = bool(e["flip"])
		entities.add_child(s)

	if OS.get_environment("SPIKE_SHOT") != "":
		_snap(OS.get_environment("SPIKE_SHOT"))


func _snap(path: String) -> void:
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	img.save_png(path)
	get_tree().quit()
