# The Draj demo: intro -> Slave Pens -> the Arena -> the first fight ->
# back to the pens, repeatable.
#
# Walking: arrow keys / WASD or click to BFS a path, on the exported
# GMAP blocking. The intro plays the baked CINE.GFF timeline (Enter =
# next part, Esc = skip). In the arena, entering the fight zone starts
# the arena fight: monsters spawn at the shipped spawn tiles, and combat
# uses the mined math (d20 vs THAC0 - AC, the bestiary attack dice).
# Winning returns you to the pens and the loop repeats, scaling each
# fight. The break-out options (escape tunnel, attacking guards) stay
# gated. SPIKE_DEMO=1 plays the whole loop scripted; SPIKE_SHOT saves a
# screenshot and quits.
extends Node2D

const STEP_TIME := 0.11
const WORLD := Vector2i(128, 98)
const TICK := 1.0 / 12.0  # intro pacing: one cine tick per wait unit

enum State { INTRO, PLAY, COMBAT, VICTORY, DEAD }

var demo: Dictionary
var region_id: int
var label_text := ""
var tile := Vector2i.ZERO
var party: Array[Dictionary] = []       # {sprite, bar_bg, bar_fg, hp, max_hp, ac, thac0, dice, sides, bonus, alive}
var monsters: Array[Dictionary] = []    # {sprite, bar*, hp, max_hp, ac, thac0, ..., tile, move_t, attack_t}
var trail: Array[Vector2] = []
var path: Array[Vector2i] = []
var armed := false
var busy := false
var cooldown := 0.0
var state := State.INTRO
var fight_count := 0
var fight_done := false
var target_mon := -1
var banner_t := 0.0
var _region_cache := {}
var _intro := {"parts": []}
var _intro_part := 0
var _intro_ev := 0
var _intro_tex: Texture2D
var _intro_wait := 0.0


func _ready() -> void:
	demo = JSON.parse_string(
		FileAccess.open("res://generated/demo.json", FileAccess.READ).get_as_text()
	)
	_intro = JSON.parse_string(
		FileAccess.open("res://generated/cine.json", FileAccess.READ).get_as_text()
	)
	$Camera.limit_left = 0
	$Camera.limit_top = 0
	$Camera.limit_right = WORLD.x * 16
	$Camera.limit_bottom = WORLD.y * 16
	if OS.get_environment("SPIKE_SHOT") != "":
		_start_game()
		await get_tree().create_timer(0.4).timeout
		await _snap(OS.get_environment("SPIKE_SHOT"))
		get_tree().quit()
		return
	_intro_play()
	if OS.get_environment("SPIKE_DEMO") != "":
		_scripted()


# ---------------------------------------------------------------- intro

func _intro_play() -> void:
	state = State.INTRO
	$Intro.visible = true
	_intro_part = 0
	_intro_ev = 0
	_intro_wait = 1.0


func _intro_process(delta: float) -> void:
	_intro_wait -= delta
	if _intro_wait > 0.0:
		return
	var parts: Array = _intro["parts"]
	if _intro_part >= parts.size():
		_start_game()
		return
	var timeline: Array = parts[_intro_part]["timeline"]
	if _intro_ev >= timeline.size():
		_intro_part += 1
		_intro_ev = 0
		_intro_wait = 0.5
		return
	var ev: Dictionary = timeline[_intro_ev]
	if ev["kind"] == "frame" or ev["kind"] == "still":
		_intro_tex = load("res://generated/cine/" + str(ev["png"]))
		$Intro/Frame.texture = _intro_tex
		_intro_wait = float(ev.get("wait", 1)) * TICK
	_intro_ev += 1


func _intro_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed:
		if event.keycode == KEY_ESCAPE:
			_start_game()
		elif event.keycode == KEY_ENTER:
			_intro_part += 1
			_intro_ev = 0
			_intro_wait = 0.1


# ------------------------------------------------------------- regions

func _start_game() -> void:
	$Intro.visible = false
	state = State.PLAY
	_enter_region(int(demo["start"]["region"]), Vector2i(int(demo["start"]["x"]), int(demo["start"]["y"])))


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

	for parent in [$Walls, $Entities, $Party, $Monsters]:
		for n in parent.get_children():
			parent.remove_child(n)
			n.queue_free()
	for w in data["walls"]:
		_add_sprite($Walls, "%s/sprites/%s" % [dir, w["png"]], Vector2(w["x"], w["y"] + w["h"]))
	for e in data["entities"]:
		var s := _add_sprite($Entities, "%s/sprites/%s" % [dir, e["png"]], Vector2(e["x"], e["y"] + e["h"]))
		s.flip_h = bool(e["flip"])

	monsters.clear()
	trail.clear()
	path.clear()
	armed = false
	busy = false
	target_mon = -1
	fight_done = false
	tile = at
	var bmps: Array = demo["party_bmps"]
	var spread := [Vector2(2, 6), Vector2(10, 2), Vector2(10, 10), Vector2(18, 6)]
	party.clear()
	var stats: Array = demo["party_stats"]
	for i in bmps.size():
		var s := _party_sprite(dir, int(bmps[i]), Vector2(at * 16) + spread[i])
		party.append(s)
	$Camera.position = Vector2(at * 16)
	$UI/Label.text = label_text


func _party_sprite(dir: String, bmp: int, top_left: Vector2) -> Dictionary:
	var st: Dictionary = demo["party_stats"][party.size()]
	var s := Sprite2D.new()
	s.texture = load("res://generated/%s/sprites/bmp_%04d.png" % [dir, bmp])
	s.centered = false
	s.offset = Vector2(0, -s.texture.get_height())
	s.flip_h = party.size() % 2 == 1
	s.position = top_left + Vector2(0, s.texture.get_height())
	$Party.add_child(s)
	var bars := _make_bars(s, s.texture.get_height())
	return {"sprite": s, "bar_bg": bars[0], "bar_fg": bars[1], "hp": int(st["hp"]),
		"max_hp": int(st["max_hp"]), "ac": int(st["ac"]), "thac0": int(st["thac0"]),
		"dice": int(st["dice"]), "sides": int(st["sides"]), "bonus": int(st["bonus"]),
		"alive": true, "attack_t": 0.0}


func _add_sprite(parent: Node2D, res: String, bottom_left: Vector2) -> Sprite2D:
	var s := Sprite2D.new()
	s.texture = load("res://generated/" + res)
	s.centered = false
	s.offset = Vector2(0, -s.texture.get_height())
	s.position = bottom_left
	parent.add_child(s)
	return s


func _make_bars(owner_node: Sprite2D, tex_h: float) -> Array:
	var bg := Polygon2D.new()
	bg.color = Color(0.1, 0.1, 0.1, 0.9)
	bg.polygon = PackedVector2Array([Vector2(-1, -2), Vector2(15, -2), Vector2(15, 1), Vector2(-1, 1)])
	owner_node.add_child(bg)
	var fg := Polygon2D.new()
	fg.color = Color(0.2, 0.9, 0.2, 0.95)
	fg.polygon = PackedVector2Array([Vector2(0, -1), Vector2(14, -1), Vector2(14, 0), Vector2(0, 0)])
	owner_node.add_child(fg)
	return [bg, fg]


func _update_bar(fg: Polygon2D, frac: float) -> void:
	var w := 14.0 * clampf(frac, 0.0, 1.0)
	fg.polygon = PackedVector2Array([Vector2(0, -1), Vector2(w, -1), Vector2(w, 0), Vector2(0, 0)])
	fg.color = Color(0.9, 0.2, 0.2, 0.95) if frac < 0.34 else Color(0.2, 0.9, 0.2, 0.95)


# ---------------------------------------------------------- map / walk

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
		out.append({"tr": tr, "tiles": _zone_tiles(tr)})
	return out


func _zone_tiles(tr: Dictionary) -> Array:
	var tiles: Array = []
	if tr.has("tiles"):
		for t in tr["tiles"]:
			tiles.append(Vector2i(int(t[0]), int(t[1])))
	else:
		var b: Array = tr["box"]
		for dx in range(int(b[2])):
			for dy in range(int(b[3])):
				tiles.append(Vector2i(int(b[0]) + dx, int(b[1]) + dy))
	return tiles


func _in_zone(t: Vector2i) -> Dictionary:
	for z in _exit_zones():
		if t in z["tiles"]:
			return z
	return {}


func _step(target: Vector2i) -> void:
	if not _walkable(target) or busy:
		path.clear()
		return
	busy = true
	var from := Vector2(tile * 16) + Vector2(0, 16)
	var to := Vector2(target * 16) + Vector2(0, 16)
	trail.push_front(from)
	trail = trail.slice(0, 8)
	var tw := create_tween()
	tw.tween_property(party[0]["sprite"], "position", to + Vector2(2, 0), STEP_TIME)
	for i in range(1, party.size()):
		if trail.size() > i:
			tw.parallel().tween_property(party[i]["sprite"], "position", trail[i] + Vector2(2, 0), STEP_TIME)
	await tw.finished
	tile = target
	busy = false
	var z := _in_zone(tile)
	if z.is_empty():
		armed = true
	elif armed and state == State.PLAY:
		var to_d: Dictionary = z["tr"]["to"]
		_enter_region(int(to_d["region"]), Vector2i(int(to_d["x"]), int(to_d["y"])))
		return
	if state == State.PLAY:
		_maybe_start_fight()


func _spawn_ring(center: Vector2i, count: int) -> Array[Vector2i]:
	# count walkable tiles ringing the party at BFS distance 3..6
	var dist := {center: 0}
	var q: Array[Vector2i] = [center]
	var picked: Array[Vector2i] = []
	var head := 0
	while head < q.size() and picked.size() < count:
		var t: Vector2i = q[head]
		head += 1
		var d: int = dist[t]
		if d >= 3 and d <= 6 and not _monster_on(t) and t != tile:
			picked.append(t)
			if picked.size() == count:
				break
		for dd in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
			var n: Vector2i = t + dd
			if _walkable(n) and not dist.has(n):
				dist[n] = d + 1
				q.append(n)
	return picked


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


# ------------------------------------------------------- process/input

func _process(delta: float) -> void:
	cooldown = maxf(0.0, cooldown - delta)
	banner_t = maxf(0.0, banner_t - delta)
	if banner_t <= 0.0:
		$UI/Banner.text = " "
	match state:
		State.INTRO:
			_intro_process(delta)
		State.PLAY, State.COMBAT, State.VICTORY:
			if party.size() > 0 and party[0]["sprite"] != null:
				$Camera.position = party[0]["sprite"].position + Vector2(8, -8)
	if state == State.COMBAT:
		_combat_tick(delta)
	if (state != State.PLAY and state != State.COMBAT) or busy:
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
	if state == State.INTRO:
		_intro_input(event)
		return
	if state != State.PLAY and state != State.COMBAT:
		return
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		var t := Vector2i((get_global_mouse_position() / 16.0).floor())
		if state == State.COMBAT:
			for mi in monsters.size():
				if monsters[mi]["alive"] and monsters[mi]["tile"] == t:
					target_mon = mi
					$UI/Banner.text = " "
					return
		var p := _bfs(tile, t)
		if not p.is_empty():
			path = p


# --------------------------------------------------------------- combat

func _fight_zone() -> Dictionary:
	return demo["fight"]


func _maybe_start_fight() -> void:
	if region_id != 42 or state != State.PLAY or fight_done:
		return
	var f: Dictionary = demo["fight"]
	var b: Array = f["zone_box"]
	if tile.x < int(b[0]) or tile.y < int(b[1]) or tile.x >= int(b[0]) + int(b[2]) or tile.y >= int(b[1]) + int(b[3]):
		return
	fight_done = true
	state = State.COMBAT
	var count: int = mini(2 + fight_count, f["spawn_tiles"].size())
	_show_banner("The Announcer rises: 'Slaves! Entertain the city of Draj!'")
	var m: Dictionary = f["monster"]
	var spots := _spawn_ring(tile, count)
	for i in count:
		var t: Vector2i = spots[i] if i < spots.size() else Vector2i(int(f["spawn_tiles"][i][0]), int(f["spawn_tiles"][i][1]))
		_spawn_monster(t, int(m["hp"]) + 2 * fight_count, m)
	target_mon = -1

func _spawn_monster(t: Vector2i, hp: int, m: Dictionary) -> void:
	var dir: String = demo["regions"]["42"]["dir"]
	var s := _add_sprite($Monsters, "%s/sprites/bmp_%04d.png" % [dir, int(m["bmp"])], Vector2(t * 16) + Vector2(0, 16))
	s.flip_h = monsters.size() % 2 == 1
	var bars := _make_bars(s, s.texture.get_height())
	monsters.append({"sprite": s, "bar_bg": bars[0], "bar_fg": bars[1], "hp": hp,
		"max_hp": hp, "ac": int(m["ac"]), "thac0": int(m["thac0"]),
		"dice": int(m["dice"]), "sides": int(m["sides"]), "bonus": int(m["bonus"]),
		"tile": t, "alive": true, "move_t": 0.0, "attack_t": 0.0, "stuck": 0, "speed_s": float(m["speed_s"]),
		"attack_s": float(m["attack_s"])})


func _monsters_alive() -> bool:
	for m in monsters:
		if m["alive"]:
			return true
	return false


func _combat_tick(delta: float) -> void:
	for mi in monsters.size():
		var m: Dictionary = monsters[mi]
		if not m["alive"]:
			continue
		m["move_t"] -= delta
		m["attack_t"] -= delta
		var tgt := _nearest_party_tile(m["tile"])
		if tgt.x < 0:
			continue
		var adjacent: bool = maxi(abs(m["tile"].x - tgt.x), abs(m["tile"].y - tgt.y)) <= 1
		if adjacent:
			if m["attack_t"] <= 0.0:
				m["attack_t"] = m["attack_s"]
				_monster_attack(mi, tgt)
		elif m["move_t"] <= 0.0:
			m["move_t"] = m["speed_s"]
			_monster_step(mi, tgt)
	for p in party:
		if p["bar_fg"] != null:
			_update_bar(p["bar_fg"], float(p["hp"]) / float(p["max_hp"]))
	for m in monsters:
		if m["alive"]:
			_update_bar(m["bar_fg"], float(m["hp"]) / float(m["max_hp"]))
	# party auto-attack against the current target
	if target_mon >= 0 and target_mon < monsters.size():
		var m2: Dictionary = monsters[target_mon]
		if not m2["alive"]:
			target_mon = -1
		elif path.is_empty() and not busy and not _adjacent_to_monster(party[0], m2):
			var best := Vector2i(-1, -1)
			var bd := 9999
			for dd in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
				var n: Vector2i = m2["tile"] + dd
				if _walkable(n):
					var d: int = abs(n.x - tile.x) + abs(n.y - tile.y)
					if d < bd:
						bd = d
						best = n
			if best.x >= 0:
				path = _bfs(tile, best)
		else:
			for p in party:
				if not p["alive"]:
					continue
				p["attack_t"] -= delta
				if p["attack_t"] <= 0.0 and _adjacent_to_monster(p, m2):
					p["attack_t"] = 1.0
					_party_attack(p, m2)


func _nearest_party_tile(from: Vector2i) -> Vector2i:
	var best := Vector2i(-1, -1)
	var best_d := 9999
	for i in party.size():
		if not party[i]["alive"]:
			continue
		var t := _occ_tile(party[i]["sprite"].position)
		var d: int = abs(t.x - from.x) + abs(t.y - from.y)
		if d < best_d:
			best_d = d
			best = t
	return best


func _occ_tile(pos: Vector2) -> Vector2i:
	# occupancy tile of a bottom-anchored sprite (feet on a tile edge)
	return Vector2i(int(pos.x / 16.0), int((pos.y - 1.0) / 16.0))


func _monster_step(mi: int, tgt: Vector2i) -> void:
	var m: Dictionary = monsters[mi]
	var dx: int = signi(tgt.x - m["tile"].x)
	var dy: int = signi(tgt.y - m["tile"].y)
	var moved := false
	for d in [Vector2i(dx, dy), Vector2i(dx, 0), Vector2i(0, dy), Vector2i(dx, -dy), Vector2i(-dx, dy)]:
		if d == Vector2i.ZERO:
			continue
		var n: Vector2i = m["tile"] + d
		if _walkable(n) and not _monster_on(n) and n != _leader_tile():
			m["sprite"].position = Vector2(n * 16) + Vector2(0, 16)
			m["tile"] = n
			m["stuck"] = 0
			moved = true
			return
	if not moved:
		m["stuck"] = int(m.get("stuck", 0)) + 1
		if m["stuck"] >= 4:  # greedy is wedged: path properly once
			var route := _bfs(m["tile"], tgt)
			if route.size() >= 1:
				m["sprite"].position = Vector2(route[0] * 16) + Vector2(0, 16)
				m["tile"] = route[0]
				m["stuck"] = 0


func _monster_on(t: Vector2i) -> bool:
	for m in monsters:
		if m["alive"] and m["tile"] == t:
			return true
	return false


func _leader_tile() -> Vector2i:
	return Vector2i(party[0]["sprite"].position / 16.0)


func _adjacent_to_monster(p: Dictionary, m: Dictionary) -> bool:
	var pt := _occ_tile(p["sprite"].position)
	return maxi(abs(pt.x - m["tile"].x), abs(pt.y - m["tile"].y)) <= 1


func _party_attack(p: Dictionary, m: Dictionary) -> void:
	var roll: int = _d(20)
	if roll == 20 or (roll != 1 and roll >= int(p["thac0"]) - int(m["ac"])):
		var dmg: int = _d(int(p["sides"]), int(p["dice"])) + int(p["bonus"])
		m["hp"] = maxi(0, m["hp"] - dmg)
		_update_bar(m["bar_fg"], float(m["hp"]) / float(m["max_hp"]))
		_float_text(m["sprite"].position, str(dmg), Color(1, 0.9, 0.3))
		if m["hp"] <= 0:
			m["alive"] = false
			m["sprite"].modulate = Color(0.4, 0.4, 0.4, 0.7)
			m["bar_bg"].visible = false
			m["bar_fg"].visible = false
			if not _monsters_alive():
				_victory()


func _monster_attack(mi: int, tgt: Vector2i) -> void:
	var m: Dictionary = monsters[mi]
	var pi := _party_index_at(tgt)
	if pi < 0 or not party[pi]["alive"]:
		return
	var p: Dictionary = party[pi]
	var roll: int = _d(20)
	if roll == 20 or (roll != 1 and roll >= int(m["thac0"]) - int(p["ac"])):
		var dmg: int = _d(int(m["sides"]), int(m["dice"])) + int(m["bonus"])
		p["hp"] = maxi(0, p["hp"] - dmg)
		_update_bar(p["bar_fg"], float(p["hp"]) / float(p["max_hp"]))
		_float_text(p["sprite"].position, str(dmg), Color(1, 0.3, 0.3))
		if p["hp"] <= 0:
			p["alive"] = false
			p["sprite"].modulate = Color(0.3, 0.3, 0.3, 0.6)
			p["bar_bg"].visible = false
			p["bar_fg"].visible = false
	if _party_wiped():
		_show_banner("The party has fallen in the arena of Draj...")
		state = State.DEAD
		await get_tree().create_timer(3.0).timeout
		for q in party:
			q["hp"] = q["max_hp"]
			q["alive"] = true
			q["sprite"].modulate = Color(1, 1, 1)
			_update_bar(q["bar_fg"], 1.0)
		_enter_region(41, Vector2i(int(demo["start"]["x"]), int(demo["start"]["y"])))
		state = State.PLAY


func _party_index_at(t: Vector2i) -> int:
	for i in party.size():
		if party[i]["alive"] and _occ_tile(party[i]["sprite"].position) == t:
			return i
	return -1


func _party_wiped() -> bool:
	for p in party:
		if p["alive"]:
			return false
	return true


func _victory() -> void:
	fight_count += 1
	state = State.VICTORY
	_show_banner("VICTORY!  The crowd roars.  The pens' doors open.  (%d)" % fight_count)
	await get_tree().create_timer(2.5).timeout
	state = State.PLAY


func _d(sides: int, count: int = 1) -> int:
	var t := 0
	for i in range(count):
		t += randi_range(1, sides)
	return t


func _show_banner(text: String) -> void:
	$UI/Banner.text = text
	banner_t = 3.0


func _float_text(at: Vector2, text: String, color: Color) -> void:
	var l := Label.new()
	l.text = text
	l.position = at + Vector2(4, -20)
	l.modulate = color
	$Floats.add_child(l)
	var tw := create_tween()
	tw.tween_property(l, "position:y", l.position.y - 24.0, 0.7)
	tw.parallel().tween_property(l, "modulate:a", 0.0, 0.7)
	tw.tween_callback(l.queue_free)


# ------------------------------------------------- scripted full loop

func _scripted() -> void:
	# Full-loop verification: intro beat -> skip -> pens -> arena stair
	# -> fight zone -> combat -> victory -> holding gate -> pens.
	await get_tree().create_timer(6.0).timeout
	_intro_part = 99  # skip the rest of the intro
	await get_tree().create_timer(1.0).timeout
	_walk_to_then(Vector2i(113, 27))  # the pens' arena stair (triggers the transition)
	await _drain()
	await get_tree().create_timer(0.3).timeout
	if region_id == 42:
		_walk_to_then(Vector2i(30, 22))  # into the fight zone
		await _drain()
		while state == State.COMBAT:
			if target_mon < 0 or not monsters[target_mon]["alive"]:
				target_mon = _nearest_mon()
			await get_tree().process_frame
		while state == State.VICTORY:
			await get_tree().process_frame
		await get_tree().create_timer(0.5).timeout
		if region_id == 42:
			_walk_to_then(Vector2i(30, 11))  # the holding gate back to the pens
			await _drain()
			await get_tree().create_timer(0.5).timeout
	get_tree().quit()


func _nearest_mon() -> int:
	var best := -1
	var bd := 99999
	for mi in monsters.size():
		if not monsters[mi]["alive"]:
			continue
		var d: int = abs(monsters[mi]["tile"].x - tile.x) + abs(monsters[mi]["tile"].y - tile.y)
		if d < bd:
			bd = d
			best = mi
	return best


func _walk_to_then(t: Vector2i) -> void:
	path = _bfs(tile, t)


func _drain() -> void:
	# the walk may hand control to a transition or a fight mid-path
	while (not path.is_empty() or busy) and state == State.PLAY:
		await get_tree().process_frame


func _snap(p: String) -> void:
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(p)
