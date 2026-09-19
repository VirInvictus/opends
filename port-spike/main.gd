# The Draj demo: walk the Slave Pens and the Arena.
#
# Grid walking on the exported blocked maps (arrow keys / WASD, or click
# to BFS a path), region transitions on the exits pinned from the games'
# GPL handlers, and a four-gladiator party that follows the leader's
# trail. SPIKE_SHOT saves a screenshot and quits; SPIKE_DEMO runs a
# scripted start -> pens -> arena walk for verification.
extends Node2D

const STEP_TIME := 0.11
const WORLD := Vector2i(128, 98)

var demo: Dictionary
var region_id: int
var label_text := ""
var tile := Vector2i.ZERO
var party: Array[Sprite2D] = []
var trail: Array[Vector2] = []
var path: Array[Vector2i] = []
var armed := false
var busy := false
var cooldown := 0.0
var _region_cache := {}


func _ready() -> void:
	demo = JSON.parse_string(
		FileAccess.open("res://generated/demo.json", FileAccess.READ).get_as_text()
	)
	$Camera.limit_left = 0
	$Camera.limit_top = 0
	$Camera.limit_right = WORLD.x * 16
	$Camera.limit_bottom = WORLD.y * 16
	_enter_region(int(demo["start"]["region"]), Vector2i(int(demo["start"]["x"]), int(demo["start"]["y"])))
	if OS.get_environment("SPIKE_SHOT") != "":
		await get_tree().create_timer(0.4).timeout
		await _snap(OS.get_environment("SPIKE_SHOT"))
		get_tree().quit()
		return
	if OS.get_environment("SPIKE_DEMO") != "":
		_scripted()


func _enter_region(rid: int, at: Vector2i) -> void:
	region_id = rid
	var dir: String = demo["regions"][str(rid)]["dir"]
	var data: Dictionary = JSON.parse_string(
		FileAccess.open("res://generated/%s/region.json" % dir, FileAccess.READ).get_as_text()
	)
	label_text = demo["regions"][str(rid)]["label"]
	_region_cache.clear()

	var tiles: TileMapLayer = $Tiles
	tiles.tile_set = load("res://generated/%s/tileset.tres" % dir)
	tiles.clear()
	for c in data["cells"]:
		tiles.set_cell(Vector2i(int(c[0]), int(c[1])), 0, Vector2i(int(c[2]), int(c[3])))

	for parent in [$Walls, $Entities, $Party]:
		for n in parent.get_children():
			parent.remove_child(n)
			n.queue_free()
	for w in data["walls"]:
		_add_sprite($Walls, "%s/sprites/%s" % [dir, w["png"]], Vector2(w["x"], w["y"] + w["h"]))
	for e in data["entities"]:
		var s := _add_sprite($Entities, "%s/sprites/%s" % [dir, e["png"]], Vector2(e["x"], e["y"] + e["h"]))
		s.flip_h = bool(e["flip"])

	trail.clear()
	path.clear()
	armed = false
	tile = at
	party.clear()
	var bmps: Array = demo["party_bmps"]
	var spread := [Vector2(2, 6), Vector2(10, 2), Vector2(10, 10), Vector2(18, 6)]
	for i in bmps.size():
		var s := Sprite2D.new()
		s.texture = load("res://generated/%s/sprites/bmp_%04d.png" % [dir, int(bmps[i])])
		s.centered = false
		s.offset = Vector2(0, -s.texture.get_height())
		s.flip_h = i % 2 == 1
		$Party.add_child(s)
		s.position = Vector2(at * 16) + spread[i] + Vector2(0, s.texture.get_height())
		party.append(s)
	$Camera.position = Vector2(at * 16)


func _add_sprite(parent: Node2D, res: String, bottom_left: Vector2) -> Sprite2D:
	# Bottom-anchored: position sits at the sprite's bottom edge (offset
	# lifts the texture), so the y-sort orders occlusion by the feet.
	var s := Sprite2D.new()
	s.texture = load("res://generated/" + res)
	s.centered = false
	s.offset = Vector2(0, -s.texture.get_height())
	s.position = bottom_left
	parent.add_child(s)
	return s


func _region_json() -> Dictionary:
	if not _region_cache.has(region_id):
		var dir: String = demo["regions"][str(region_id)]["dir"]
		_region_cache[region_id] = JSON.parse_string(
			FileAccess.open("res://generated/%s/region.json" % dir, FileAccess.READ).get_as_text()
		)
	return _region_cache[region_id]


func _walkable(t: Vector2i) -> bool:
	if t.x < 0 or t.y < 0 or t.x >= WORLD.x or t.y >= WORLD.y:
		return false
	var rows: Array = _region_json()["blocked_rows"]
	return rows[t.y][t.x] == "."


func _exit_zones() -> Array:
	var out: Array = []
	for tr in demo["transitions"]:
		if int(tr["region"]) != region_id or tr["to"] == null:
			continue
		var tiles: Array = []
		if tr.has("tiles"):
			for t in tr["tiles"]:
				tiles.append(Vector2i(int(t[0]), int(t[1])))
		else:
			var b: Array = tr["box"]
			for dx in range(int(b[2])):
				for dy in range(int(b[3])):
					tiles.append(Vector2i(int(b[0]) + dx, int(b[1]) + dy))
		out.append({"tr": tr, "tiles": tiles})
	return out


func _in_zone(t: Vector2i) -> Dictionary:
	for z in _exit_zones():
		if t in z["tiles"]:
			return z
	return {}


func _process(delta: float) -> void:
	cooldown = maxf(0.0, cooldown - delta)
	$UI/Label.text = label_text
	if party.size() > 0:
		$Camera.position = party[0].position + Vector2(8, -8)
	if busy:
		return
	if not path.is_empty():
		_step(path.pop_front())
		return
	var dir := Vector2i.ZERO
	if Input.is_key_pressed(KEY_LEFT) or Input.is_key_pressed(KEY_A):
		dir = Vector2i(-1, 0)
	elif Input.is_key_pressed(KEY_RIGHT) or Input.is_key_pressed(KEY_D):
		dir = Vector2i(1, 0)
	elif Input.is_key_pressed(KEY_UP) or Input.is_key_pressed(KEY_W):
		dir = Vector2i(0, -1)
	elif Input.is_key_pressed(KEY_DOWN) or Input.is_key_pressed(KEY_S):
		dir = Vector2i(0, 1)
	if dir != Vector2i.ZERO and cooldown <= 0.0:
		cooldown = STEP_TIME
		_step(tile + dir)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		var t := Vector2i((get_global_mouse_position() / 16.0).floor())
		var p := _bfs(tile, t)
		if not p.is_empty():
			path = p


func _step(target: Vector2i) -> void:
	if not _walkable(target) or busy:
		path.clear()
		return
	busy = true
	var from := Vector2(tile * 16) + Vector2(0, 16)   # feet at the tile's bottom edge
	var to := Vector2(target * 16) + Vector2(0, 16)
	trail.push_front(from)
	trail = trail.slice(0, 8)
	var tw := create_tween()
	tw.tween_property(party[0], "position", to + Vector2(2, 0), STEP_TIME)
	for i in range(1, party.size()):
		if trail.size() > i:
			tw.parallel().tween_property(party[i], "position", trail[i] + Vector2(2, 0), STEP_TIME)
	await tw.finished
	tile = target
	busy = false
	var z := _in_zone(tile)
	if z.is_empty():
		armed = true
	elif armed and z["tr"]["to"] != null:
		var to_d: Dictionary = z["tr"]["to"]
		_enter_region(int(to_d["region"]), Vector2i(int(to_d["x"]), int(to_d["y"])))


func _bfs(src: Vector2i, dst: Vector2i) -> Array[Vector2i]:
	var prev := {}
	var seen := {src: true}
	var q: Array[Vector2i] = [src]
	while not q.is_empty():
		var t: Vector2i = q.pop_front()
		if t == dst:
			break
		for d in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
			var n: Vector2i = t + d
			if _walkable(n) and not seen.has(n):
				seen[n] = true
				prev[n] = t
				q.append(n)
	if not seen.has(dst):
		return []
	var out: Array[Vector2i] = []
	var cur := dst
	while cur != src:
		out.push_front(cur)
		cur = prev[cur]
	return out


func _scripted() -> void:
	# Verification walk: pens start -> the arena stair -> transition ->
	# arena floor, with screenshots at each beat.
	await get_tree().create_timer(0.4).timeout
	await _snap("/tmp/spike/demo_pens.png")
	var route := _bfs(tile, Vector2i(113, 27))  # the stair box tile
	path = Array(route.slice(0, maxi(0, route.size() - 2)), TYPE_VECTOR2I, "", null)
	await _drain()
	await get_tree().create_timer(0.2).timeout
	await _snap("/tmp/spike/demo_stair.png")
	path = Array(route.slice(maxi(0, route.size() - 2)), TYPE_VECTOR2I, "", null)
	await _drain()
	await get_tree().create_timer(0.3).timeout
	if region_id == 42:
		await _snap("/tmp/spike/demo_arena.png")
		path = _bfs(tile, Vector2i(30, 22))
		await _drain()
		await _snap("/tmp/spike/demo_arena_floor.png")
	get_tree().quit()


func _drain() -> void:
	while not path.is_empty() or busy:
		await get_tree().process_frame


func _snap(p: String) -> void:
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(p)
