# The Draj demo: intro -> Slave Pens -> the Arena -> the first fight ->
# back to the pens, repeatable. Combat follows the engine's structure
# (docs/combat-flow.md + the turn-system research): a single-actor token
# passes to the highest morale-threshold combatant each pick, party and
# monsters share one stream, a round is one pass of that queue, movement
# costs 10 (orthogonal) / 14 (diagonal) from move x 10, and attacks use
# the parity alternator over the blows byte.
#
# Walking: arrow keys / WASD or click to BFS a path. The intro plays the
# baked CINE.GFF timeline (Enter = next part, Esc = skip). SPIKE_DEMO=1
# plays the whole opening loop scripted; SPIKE_SHOT saves a screenshot.
extends Node2D

const STEP_TIME := 0.11
const WORLD := Vector2i(128, 98)
const TICK := 1.0 / 12.0
const STEP_COST := [10, 14, 10, 14, 10, 14, 10, 14]  # N,NE,E,SE,S,SW,W,NW

enum State { INTRO, PLAY, COMBAT, VICTORY, DEAD }
enum Phase { PICK, PARTY, MONSTER }

var demo: Dictionary
var region_id: int
var label_text := ""
var tile := Vector2i.ZERO
var party: Array[Dictionary] = []
var monsters: Array[Dictionary] = []
var trail: Array[Vector2] = []
var path: Array[Vector2i] = []
var armed := false
# UI-parity screens (WindScreen family): opened by the mined hotkeys,
# drawn over the world in a CanvasLayer, movement blocked while open.
# Party records sync into PartyData so every screen shows live HP/AC/
# THAC0/moves. The world build order maps onto PartyData.MEMBERS (the
# engine's UI order: CERMAK, K'RATCHEK, SARIA, SILLA) so records and
# names stay aligned.
var ui_layer: Node2D
var ui_screen: Node2D
var ui_open := false
var combat_hud: CombatHud
const PRESET_NAMES := ["CERMAK", "K'RATCHEK", "SARIA", "SILLA"]
const PARTY_ORDER := [0, 3, 1, 2]  # demo.json party row per UI member
var busy := false
var cooldown := 0.0
var state := State.INTRO
var phase := Phase.PICK
var fight_count := 0
var fight_done := false
var arena_intro_done := false
var round_no := 0
var queue: Array[Dictionary] = []
var actor_i := -1
var target_mon := -1
var move_pts := 0
var attacks_left := 0
var acted := false
var banner_t := 0.0
var _region_cache := {}
var _intro := {"parts": []}
var _intro_part := 0
var _intro_ev := 0
var _intro_wait := 0.0
var _intro_qc := false
var created_char = null


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
	ui_layer = Node2D.new()
	ui_layer.name = "Screens"
	$UI.add_child(ui_layer)
	combat_hud = CombatHud.new()
	combat_hud.visible = false
	$UI.add_child(combat_hud)
	if OS.get_environment("SPIKE_SHOT") != "":
		_start_game()
		if OS.get_environment("SPIKE_AT") != "":
			var xy: PackedStringArray = OS.get_environment("SPIKE_AT").split(",")
			_enter_region(int(demo["start"]["region"]), Vector2i(int(xy[0]), int(xy[1])))
		await get_tree().create_timer(0.4).timeout
		await _snap(OS.get_environment("SPIKE_SHOT"))
		get_tree().quit()
		return
	# The original boots into the intro and only then shows the menu;
	# launching a game from the menu comes back here with the intro done.
	if Engine.has_meta("skip_intro"):
		Engine.remove_meta("skip_intro")
		_start_game()
		return
	# QC hook: SPIKE_UI=<screen> opens a UI screen over the running game
	# and saves SPIKE_OUT once it is up.
	if OS.get_environment("SPIKE_UI") != "":
		_start_game()
		var target: String = OS.get_environment("SPIKE_UI")
		await get_tree().create_timer(1.0).timeout
		_sync_party_data()
		_open_screen(target)
		await get_tree().create_timer(0.5).timeout
		await _snap(OS.get_environment("SPIKE_OUT"))
		get_tree().quit()
		return
	if OS.get_environment("SPIKE_SPLAT") != "":
		# QC: fire one splat over the leader and snap it
		_start_game()
		await get_tree().create_timer(0.6).timeout
		_spawn_splat(party[0]["sprite"], int(OS.get_environment("SPIKE_SPLAT")))
		await get_tree().create_timer(0.2).timeout
		await _snap(OS.get_environment("SPIKE_OUT"))
		get_tree().quit()
		return
	_intro_play()
	if OS.get_environment("SPIKE_INTRO") != "":
		_intro_qc = true
	elif OS.get_environment("SPIKE_DEMO") != "":
		_scripted()
	elif OS.get_environment("SPIKE_TOUR") != "":
		_tour()


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
		if _intro_qc:
			print("[INTRO-QC] complete")
			get_tree().quit()
			return
		if OS.get_environment("SPIKE_DEMO") == "" and OS.get_environment("SPIKE_TOUR") == "":
			# Boot flow per the original: intro, then the main menu.
			get_tree().change_scene_to_file("res://menu.tscn")
			return
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
		$Intro/Frame.texture = load("res://generated/cine/" + str(ev["png"]))
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
	print("[GAME] start_game, created=", created_char != null)
	$Intro.visible = false
	state = State.PLAY
	if FileAccess.file_exists("res://generated/created.json"):
		created_char = JSON.parse_string(
			FileAccess.open("res://generated/created.json", FileAccess.READ).get_as_text()
		)
	# SPIKE_REGION+SPIKE_AT drop the party straight into a region/tile
	# (fight QC without the cross-region walk)
	if OS.get_environment("SPIKE_REGION") != "" and OS.get_environment("SPIKE_AT") != "":
		var xy: PackedStringArray = OS.get_environment("SPIKE_AT").split(",")
		_enter_region(int(OS.get_environment("SPIKE_REGION")),
			Vector2i(int(xy[0]), int(xy[1])))
		return
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
		# sort feet one pixel past the row bottom: the engine's wall pass
		# overdraws same-row entities
		_add_sprite($Walls, "%s/sprites/%s" % [dir, w["png"]], Vector2(w["x"], float(w.get("sort_y", w["y"] + w["h"]))))
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
	for i in bmps.size():
		var src: int = PARTY_ORDER[i]
		var st: Dictionary = demo["party_stats"][src]
		var bmp_i: int = int(bmps[src])
		var nm := ""
		if created_char != null and i == 0 and bool(created_char.get("use_presets", true)) == false:
			st = created_char.duplicate()
			bmp_i = int(created_char["bmp"])
			nm = str(created_char.get("name", ""))
		var s := _add_sprite($Party, "%s/sprites/bmp_%04d.png" % [dir, bmp_i], Vector2(at * 16) + spread[i])
		s.flip_h = i % 2 == 1
		var bars := _make_bars(s)
		party.append({"sprite": s, "bar_bg": bars[0], "bar_fg": bars[1],
			"hp": int(st["hp"]), "max_hp": int(st["max_hp"]), "ac": int(st["ac"]),
			"thac0": int(st["thac0"]), "move": int(st["move"]), "blows": int(st["blows"]),
			"dice": int(st["dice"]), "sides": int(st["sides"]), "bonus": int(st["bonus"]),
			"dex": int(PartyData.MEMBERS[i]["stats"][1]),
			"name": nm, "alive": true})
	$Camera.position = Vector2(at * 16)
	$UI/Label.text = label_text
	if region_id == 42 and not arena_intro_done:
		arena_intro_done = true
		var leader: String = str(party[0].get("name", "")) if str(party[0].get("name", "")) != "" else PRESET_NAMES[0]
		_say_sequence([
			{"port": ANNOUNCER_PORT, "text": ANNOUNCER["citizens"]},
			{"port": ANNOUNCER_PORT, "text": ANNOUNCER["gift"]},
			{"port": ANNOUNCER_PORT, "text": ANNOUNCER["celgor"]},
			{"port": ANNOUNCER_PORT, "text": ANNOUNCER["donotworry"] % leader},
		], func() -> void: pass)


func _add_sprite(parent: Node2D, res: String, bottom_left: Vector2) -> Sprite2D:
	var s := Sprite2D.new()
	s.texture = load("res://generated/" + res)
	s.centered = false
	s.offset = Vector2(0, -s.texture.get_height())
	s.position = bottom_left
	parent.add_child(s)
	return s


func _make_bars(owner_node: Sprite2D) -> Array:
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


func _step_to(target: Vector2i, mover: Dictionary) -> void:
	if not _walkable(target) or busy:
		path.clear()
		return
	busy = true
	var step_cost := 10 if (target.x == tile.x or target.y == tile.y) else 14
	var from := Vector2(tile * 16) + Vector2(0, 16)
	var to := Vector2(target * 16) + Vector2(0, 16)
	trail.push_front(from)
	trail = trail.slice(0, 8)
	var tw := create_tween()
	tw.tween_property(mover["sprite"], "position", to + Vector2(2, 0), STEP_TIME)
	for i in range(1, party.size()):
		if trail.size() > i and state == State.PLAY:
			tw.parallel().tween_property(party[i]["sprite"], "position", trail[i] + Vector2(2, 0), STEP_TIME)
	await tw.finished
	if state == State.PLAY:
		tile = target
		move_pts = maxi(0, move_pts - step_cost)
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


## Is a world entity standing on this tile? (entities carry pixel
## positions; the tile is the top-left 16x16 block)
func _entity_at(t: Vector2i) -> bool:
	for e in _region_json().get("entities", []):
		if Vector2i(int(e["x"]) / 16, int(e["y"]) / 16) == t:
			return true
	return false


func _open_interact() -> void:
	_close_ui()
	var interact := InteractScreen.new(InteractScreen.CAP_TALK | 0x2)
	interact.action.connect(func(kind: String) -> void:
		if kind == "talk":
			_close_ui()
			_say_sequence([
				{"port": ANNOUNCER_PORT, "text": ANNOUNCER["citizens"]},
				{"port": ANNOUNCER_PORT, "text": ANNOUNCER["gift"]},
			], func() -> void: pass)
		else:
			_close_ui())
	ui_screen = interact
	ui_layer.add_child(interact)
	ui_open = true


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
			if party.size() > 0:
				$Camera.position = party[0]["sprite"].position + Vector2(8, -8)
	if state == State.COMBAT and phase == Phase.PARTY and not busy and cooldown <= 0.0:
		var cdir := Vector2i.ZERO
		if Input.is_key_pressed(KEY_LEFT) or Input.is_key_pressed(KEY_A):
			cdir = Vector2i(-1, 0)
		elif Input.is_key_pressed(KEY_RIGHT) or Input.is_key_pressed(KEY_D):
			cdir = Vector2i(1, 0)
		elif Input.is_key_pressed(KEY_UP) or Input.is_key_pressed(KEY_W):
			cdir = Vector2i(0, -1)
		elif Input.is_key_pressed(KEY_DOWN) or Input.is_key_pressed(KEY_S):
			cdir = Vector2i(0, 1)
		if cdir != Vector2i.ZERO:
			cooldown = STEP_TIME
			_combat_step_member(tile + cdir)
	if state != State.PLAY or busy:
		return
	if not path.is_empty():
		_step_to(path.pop_front(), party[0])
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
		_step_to(tile + dir, party[0])


func _unhandled_input(event: InputEvent) -> void:
	if ui_open:
		if event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE:
			_close_ui()
		return
	if state == State.PLAY and not busy and event is InputEventKey and event.pressed:
		if event.keycode == KEY_F1:
			_save_game()
			return
		if event.keycode == KEY_F2:
			_load_game()
			return
		match event.keycode:
			KEY_TAB:
				_open_screen("gamemenu")
				return
			KEY_V:
				_open_screen("sheet")
				return
			KEY_I:
				_open_screen("inventory")
				return
			KEY_U, KEY_C:
				_open_screen("sheet:USE")
				return
			KEY_E:
				_open_screen("sheet:EFFECTS")
				return
			KEY_O:
				_open_screen("map")
				return
	if state == State.INTRO:
		_intro_input(event)
		return
	if state == State.COMBAT and phase == Phase.PARTY and event is InputEventKey and event.pressed:
		if event.keycode == KEY_ENTER:
			_end_party_turn()
		return
	if state == State.COMBAT and phase == Phase.PARTY and attacks_left > 0 \
			and event is InputEventMouseButton and event.pressed \
			and event.button_index == MOUSE_BUTTON_LEFT:
		var t := Vector2i((get_global_mouse_position() / 16.0).floor())
		if _cheby(_party_tile(0), t) <= 1:
			var mi := _monster_at(t)
			if mi >= 0:
				_party_attack(mi)
				return
	if state != State.PLAY or busy:
		return
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		var t := Vector2i((get_global_mouse_position() / 16.0).floor())
		if _entity_at(t):
			_open_interact()
			return
		var p := _bfs(tile, t)
		if not p.is_empty():
			path = p


# --------------------------------------------- save / load (F1/F2)

func _save_game() -> void:
	DirAccess.make_dir_recursive_absolute("user://saves")
	_sync_party_data()
	var state := {
		"label": "%s, the pens" % PartyData.MEMBERS[0]["name"],
		"members": PartyData.MEMBERS,
		"port": {"region": region_id, "tile": [tile.x, tile.y],
			"fight_count": fight_count, "gold": 0},
	}
	var err: int = SaveIO.write_save("user://saves/SAVE01.SAV", state)
	MessageBox.flash($UI, "GAME SAVED" if err == OK else "SAVE FAILED")

func _load_game() -> void:
	_load_from("user://saves/SAVE01.SAV")

func _load_from(path: String) -> void:
	var st: Dictionary = SaveIO.read_save(path)
	if st["port"].is_empty():
		_show_banner("No saved game found")
		return
	var port: Dictionary = st["port"]
	region_id = int(port["region"])
	fight_count = int(port.get("fight_count", 0))
	for mi in party.size():
		party[mi]["hp"] = int(PartyData.MEMBERS[mi]["hp"])
		party[mi]["max_hp"] = int(PartyData.MEMBERS[mi]["max"])
		party[mi]["alive"] = str(PartyData.MEMBERS[mi]["status"]) == "Okay"
		if mi < st["members"].size() and st["members"][mi].has("cells"):
			PartyData.MEMBERS[mi]["cells"] = st["members"][mi]["cells"]
	var t: Array = port["tile"]
	_enter_region(region_id, Vector2i(int(t[0]), int(t[1])))
	MessageBox.flash($UI, "GAME LOADED")


# --------------------------------------------- UI screens

func _open_screen(which: String) -> void:
	_sync_party_data()
	var ws: Node2D
	match which:
		"gamemenu":
			var gm := GameMenuScreen.new()
			gm.screen_requested.connect(_menu_route)
			ws = gm
		"loadscreen":
			var ls := LoadScreen.new()
			ls.load_requested.connect(_load_from)
			ws = ls
		"sheet":
			ws = SheetScreen.new(SheetScreen.Mode.VIEW)
		"inventory":
			ws = InventoryScreen.new()
		"spells":
			ws = SpellScreen.new()
		"prefs":
			ws = PrefsScreen.new()
		"map":
			ws = MapScreen.new(region_id)
		_:
			if which.begins_with("sheet:"):
				var mode_name: String = which.get_slice(":", 1)
				ws = SheetScreen.new(SheetScreen.Mode[mode_name])
			elif which.begins_with("popup:"):
				_open_game_popup(which.get_slice(":", 1))
				return
			else:
				return
	_close_ui()
	ui_screen = ws
	ui_layer.add_child(ws)
	ui_open = true


## The game menu's modals (screen-flow.md 8.7): EXIT asks SAVE/QUIT
## in peace, QUIT/CANCEL in combat; LOAD/SAVE offers LOAD/SAVE/RESTART
## in peace, LOAD/RESTART in combat.
func _open_game_popup(kind: String) -> void:
	var in_combat := state == State.COMBAT
	var popup: PopupScreen
	if kind == "exit":
		popup = PopupScreen.new("EXIT: SAVE GAME?" if not in_combat else "EXIT GAME?",
			["SAVE", "QUIT", "CANCEL"] if not in_combat else ["QUIT", "CANCEL"])
		popup.chosen.connect(_on_exit_choice.bind(in_combat))
	elif kind == "loadsave":
		popup = PopupScreen.new("RESTART GAME?",
			["LOAD", "SAVE", "RESTART"] if not in_combat else ["LOAD", "RESTART"])
		popup.chosen.connect(_on_loadsave_choice)
	else:
		return
	_close_ui()
	ui_screen = popup
	ui_layer.add_child(popup)
	ui_open = true


func _on_exit_choice(i: int, in_combat: bool) -> void:
	match i:
		1:
			_close_ui()
			_save_game()
			if not in_combat:
				get_tree().quit()
		2:
			_close_ui()
			get_tree().quit()
		_:
			_close_ui()


func _on_loadsave_choice(i: int) -> void:
	match i:
		1:
			_close_ui()
			_open_screen("loadscreen")
		2:
			_close_ui()
			_save_game()
		3:
			_close_ui()
			fight_count = 0
			_enter_region(41, Vector2i(int(demo["start"]["x"]), int(demo["start"]["y"])))
		_:
			_close_ui()

func _close_ui() -> void:
	if ui_screen != null:
		ui_screen.queue_free()
	ui_screen = null
	ui_open = false

func _menu_route(which: String) -> void:
	if which == "close":
		_close_ui()
	else:
		_open_screen(which)

func _sync_party_data() -> void:
	for i in party.size():
		var p: Dictionary = party[i]
		var m: Dictionary = PartyData.MEMBERS[i]
		m["name"] = str(p["name"]) if str(p["name"]) != "" else PRESET_NAMES[i]
		m["hp"] = int(p["hp"])
		m["max"] = int(p["max_hp"])
		m["ac"] = int(p["ac"])
		m["thac0"] = int(p["thac0"])
		m["moves"] = int(p["move"])
		m["status"] = "Okay" if bool(p["alive"]) else "Dead"


# --------------------------------------------- the actor-token machine

func _combat_tickless_guard(_delta: float) -> void:
	pass  # per-frame combat upkeep placeholder (bars update on damage)


func _combat_step_member(target: Vector2i) -> void:
	# movement for whichever party member holds the token
	var a: Dictionary = queue[actor_i]
	var src := _party_tile(a["idx"])
	var cost := 10 if (target.x == src.x or target.y == src.y) else 14
	if not _walkable(target) or _monster_on(target) or move_pts < cost or busy:
		return
	move_pts -= cost
	var s: Sprite2D = party[a["idx"]]["sprite"]
	var tw := create_tween()
	tw.tween_property(s, "position", Vector2(target * 16) + Vector2(2, 16), STEP_TIME)
	if a["idx"] == 0:
		tile = target


# The arena announcer's lines: real GPL-2 strings (docs/dialogs.md
# machinery; extracted with dialog-extract), portrait PORT 119.
const ANNOUNCER_PORT := 119
const ANNOUNCER := {
	"citizens": "Citizens of Draj!\nBefore you is a handful of gladiators. Watch\nand be entertained as they fight to the\ndeath with the denizens of our land.",
	"gift": "Behold the gift of your king Tectuktitlay, vicious defender of Draj -- the gift of battle and death!",
	"celgor": "This day the mage Celgor will battle a fearsome rampager. Watch and enjoy!",
	"donotworry": "Do not worry, %s. Your turn will come soon. Stand back and watch the battle.",
	"trainer": "Monster Trainer: release your horde!",
	"stepforward": "Gladiators: Step forward, into the arena!",
	"heal": "Attention gladiators: Go back to the pens to heal your wounds.",
	"yell": "Yell something back at the Announcer?",
	"worst": "Wounded rats, huh? Send out your worst!",
	"best": "You're the best announcer I've seen.",
	"again": "I want to fight again! Now!",
	"wellthanks": "Well, thanks!",
	"takethis": "What?! You upstarts! Take this!",
	"release2": "Monster Trainer: Release the monsters!",
}


func _say_sequence(pages: Array, then: Callable) -> void:
	var auto := 1.2 if OS.get_environment("SPIKE_DEMO") != "" else 0.0
	var dlg := DialogScreen.new(pages, auto)
	dlg.finished.connect(then)
	_close_ui()
	ui_screen = dlg
	ui_layer.add_child(dlg)
	ui_open = true


func _maybe_start_fight() -> void:
	if region_id != 42 or state != State.PLAY or fight_done:
		return
	var f: Dictionary = demo["fight"]
	var b: Array = f["zone_box"]
	if tile.x < int(b[0]) or tile.y < int(b[1]) or tile.x >= int(b[0]) + int(b[2]) or tile.y >= int(b[1]) + int(b[3]):
		return
	fight_done = true
	round_no = 0
	var leader: String = str(party[0].get("name", "")) if str(party[0].get("name", "")) != "" else PRESET_NAMES[0]
	_say_sequence([
		{"port": ANNOUNCER_PORT, "text": ANNOUNCER["trainer"]},
		{"port": ANNOUNCER_PORT, "text": ANNOUNCER["stepforward"]},
	], _begin_fight)


func _begin_fight() -> void:
	var f: Dictionary = demo["fight"]
	var m: Dictionary = f["monster"]
	var count: int = mini(2 + fight_count, f["spawn_tiles"].size())
	var spots := _spawn_ring(tile, count)
	for i in count:
		var t: Vector2i = spots[i] if i < spots.size() else Vector2i(int(f["spawn_tiles"][i][0]), int(f["spawn_tiles"][i][1]))
		_spawn_monster(t, int(m["hp"]) + 2 * fight_count, m)
	state = State.COMBAT
	_new_round()


func _spawn_ring(center: Vector2i, count: int) -> Array[Vector2i]:
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


func _spawn_monster(t: Vector2i, hp: int, m: Dictionary) -> void:
	var dir: String = demo["regions"]["42"]["dir"]
	var s := _add_sprite($Monsters, "%s/sprites/bmp_%04d.png" % [dir, int(m["bmp"])], Vector2(t * 16) + Vector2(0, 16))
	s.flip_h = monsters.size() % 2 == 1
	var bars := _make_bars(s)
	monsters.append({"sprite": s, "bar_bg": bars[0], "bar_fg": bars[1], "hp": hp,
		"max_hp": hp, "ac": int(m["ac"]), "thac0": int(m["thac0"]), "move": int(m["move"]),
		"blows": int(m["blows"]), "dice": int(m["dice"]), "sides": int(m["sides"]),
		"bonus": int(m["bonus"]), "tile": t, "alive": true})


func _monster_on(t: Vector2i) -> bool:
	for m in monsters:
		if m["alive"] and m["tile"] == t:
			return true
	return false


func _monster_at(t: Vector2i) -> int:
	for mi in monsters.size():
		if monsters[mi]["alive"] and monsters[mi]["tile"] == t:
			return mi
	return -1


func _monsters_alive() -> bool:
	for m in monsters:
		if m["alive"]:
			return true
	return false


func _new_round() -> void:
	round_no += 1
	queue.clear()
	var act_mods := [5, 0, -5, -10]
	for i in party.size():
		if party[i]["alive"]:
			var thr: int = 20 + _d(10) + _dex_reaction(int(party[i].get("dex", 10))) + act_mods[i]
			queue.append({"kind": "p", "idx": i, "thr": thr, "roll": _d(200),
				"move_pts": party[i]["move"] * 10, "blows": _blows_this_round(party[i]["blows"]),
				"done": false})
	for mi in monsters.size():
		if monsters[mi]["alive"]:
			var thr2: int = 20 + _d(10)
			queue.append({"kind": "m", "idx": mi, "thr": thr2, "roll": _d(200),
				"move_pts": monsters[mi]["move"] * 10,
				"blows": _blows_this_round(monsters[mi]["blows"]), "done": false})
	queue.sort_custom(func(a, b):
		if a["thr"] != b["thr"]:
			return a["thr"] > b["thr"]
		return a["roll"] > b["roll"])
	# round_init resets the rear-attack direction memory (+0x5b)
	for mm in monsters:
		mm["dir_last"] = -1
	for pp in party:
		pp["dir_last"] = -1
	actor_i = -1
	_next_actor()


func _blows_this_round(base: int) -> int:
	# the engine's parity alternator: blows = (base + odd/even round) / 2
	return int((base + (round_no & 1)) / 2.0)


func _actor_ok(a: Dictionary) -> bool:
	if a["kind"] == "p":
		return party[a["idx"]]["alive"]
	return monsters[a["idx"]]["alive"]


func _next_actor() -> void:
	if state != State.COMBAT:
		return
	if not _monsters_alive():
		_victory()
		combat_hud.visible = false
		return
	if _party_wiped():
		_party_down()
		combat_hud.visible = false
		return
	actor_i += 1
	if actor_i >= queue.size():
		_new_round()
		return
	var a: Dictionary = queue[actor_i]
	if not _actor_ok(a) or a["done"]:
		_next_actor()
		return
	if a["kind"] == "p":
		_party_turn(a)
	else:
		_monster_turn(a)


func _preset_name(idx: int) -> String:
	var preset_names := ["Cermak", "Saria", "Cilla", "K'ratchek"]
	return preset_names[idx] if idx < 4 else "Gladiator"


func _party_turn(a: Dictionary) -> void:
	phase = Phase.PARTY
	move_pts = a["move_pts"]
	attacks_left = a["blows"]
	tile = _party_tile(0)
	var pm: Dictionary = party[a["idx"]]
	combat_hud.visible = true
	combat_hud.set_actor(str(pm.get("name", "")) if str(pm.get("name", "")) != "" else _preset_name(a["idx"]),
		int(pm["hp"]), int(pm["max_hp"]), move_pts, "Okay")
	var nm: String = _preset_name(a["idx"])
	_show_banner("Round %d - %s  (move %d, %d attack%s)  [Enter = done]" % [
		round_no, nm, int(move_pts / 10.0), attacks_left,
		"s" if attacks_left != 1 else ""])


func _end_party_turn() -> void:
	queue[actor_i]["done"] = true
	path.clear()
	_next_actor()


func _monster_turn(a: Dictionary) -> void:
	phase = Phase.MONSTER
	var mi: int = a["idx"]
	var m: Dictionary = monsters[mi]
	combat_hud.visible = true
	combat_hud.set_actor(str(m.get("name", "the beast")), int(m["hp"]), int(m["max_hp"]),
		int(a["move_pts"]), "Okay")
	_show_banner("Round %d - the beast is upon you..." % round_no)
	await get_tree().create_timer(0.35).timeout
	var tgt := _nearest_party_tile(m["tile"])
	var steps: int = int(a["move_pts"] / 10.0)
	while steps > 0 and m["alive"] and state == State.COMBAT:
		if _cheby(m["tile"], tgt) <= 1:
			break
		var route := _bfs(m["tile"], tgt)
		if route.is_empty():
			break
		var n: Vector2i = route[0]
		if not _walkable(n) or _monster_on(n) or _party_on(n):
			break
		m["sprite"].position = Vector2(n * 16) + Vector2(0, 16)
		m["tile"] = n
		steps -= 1
		await get_tree().create_timer(0.12).timeout
	if m["alive"] and state == State.COMBAT and _cheby(m["tile"], tgt) <= 1:
		var pi := _party_index_at(tgt)
		if pi >= 0:
			for b in a["blows"]:
				if not m["alive"] or not party[pi]["alive"]:
					break
				_monster_attack(m, party[pi])
				await get_tree().create_timer(0.35).timeout
	a["done"] = true
	await get_tree().create_timer(0.2).timeout
	_next_actor()


func _cheby(a: Vector2i, b: Vector2i) -> int:
	return maxi(abs(a.x - b.x), abs(a.y - b.y))


func _party_tile(i: int) -> Vector2i:
	return _occ_tile(party[i]["sprite"].position)


func _party_on(t: Vector2i) -> bool:
	for i in party.size():
		if party[i]["alive"] and _party_tile(i) == t:
			return true
	return false


func _nearest_party_tile(from: Vector2i) -> Vector2i:
	var best := Vector2i(-1, -1)
	var best_d := 9999
	for i in party.size():
		if not party[i]["alive"]:
			continue
		var t := _party_tile(i)
		var d: int = _cheby(t, from)
		if d < best_d:
			best_d = d
			best = t
	return best


func _occ_tile(pos: Vector2) -> Vector2i:
	return Vector2i(int(pos.x / 16.0), int((pos.y - 1.0) / 16.0))


func _party_index_at(t: Vector2i) -> int:
	for i in party.size():
		if party[i]["alive"] and _party_tile(i) == t:
			return i
	return -1


func _party_attack(mi: int) -> void:
	if attacks_left <= 0 or mi >= monsters.size() or not monsters[mi]["alive"]:
		return
	attacks_left -= 1
	var p: Dictionary = party[0]
	var t: Dictionary = monsters[mi]
	# rear/flank: hitting from the same direction twice grants THAC0-2
	# (combat-flow.md section 5, CSTATE2 +0x5b direction memory)
	var at := _party_tile(0)
	var dir := _attack_dir(at, _occ_tile(t["sprite"].position))
	var thac0: int = int(p["thac0"])
	if int(t.get("dir_last", -1)) == dir:
		thac0 -= 2
	t["dir_last"] = dir
	# crit-adjust: a crit roll of 4 doubles the blow budget, 1 halves it
	# (1-blow attack -> the halve leaves nothing: the swing never lands)
	var crit := _d(4)
	var blows := 2 if crit == 4 else (0 if crit == 1 else 1)
	for b in blows:
		if not t["alive"]:
			break
		var roll: int = _d(20)
		if roll != 20 and (roll == 1 or roll < thac0 - int(t["ac"])):
			_spawn_splat(t["sprite"], 3)  # grey puff = miss
			continue
		var dmg: int = _d(int(p["sides"]), int(p["dice"])) + int(p["bonus"])
		t["hp"] = maxi(0, int(t["hp"]) - dmg)
		_update_bar(t["bar_fg"], float(t["hp"]) / float(t["max_hp"]))
		# splat frames by damage class (BMP 5014): small/big red hits,
		# gold star on the kill; green is the poison frame, unused here
		var killed: bool = int(t["hp"]) <= 0
		_spawn_splat(t["sprite"], 4 if killed else (1 if dmg >= 3 else 0))
		if killed:
			t["alive"] = false
			t["sprite"].modulate = Color(0.4, 0.4, 0.4, 0.7)
			t["bar_bg"].visible = false
			t["bar_fg"].visible = false
			if not _monsters_alive():
				_victory()


func _hud_refresh_member(idx: int) -> void:
	if not combat_hud.visible or idx >= party.size():
		return
	var p: Dictionary = party[idx]
	var nm: String = str(p.get("name", "")) if str(p.get("name", "")) != "" else _preset_name(idx)
	combat_hud.set_actor(nm, int(p["hp"]), int(p["max_hp"]), int(p["move"]) * 10,
		"Okay" if bool(p["alive"]) else "Dead")


func _monster_attack(m: Dictionary, p: Dictionary) -> void:
	var at := _occ_tile(m["sprite"].position)
	var dir := _attack_dir(at, _party_tile(party.find(p)))
	var thac0: int = int(m["thac0"])
	if int(p.get("dir_last", -1)) == dir:
		thac0 -= 2
	p["dir_last"] = dir
	# monster attackers add [0x11ae]-1 (the text-speed pref) to damage:
	# the engine's own quirk (combat-flow.md section 5, 0x16b7)
	var dmg_bonus: int = int(m["bonus"]) + PrefsScreen.text_speed - 1
	var crit := _d(4)
	var blows := 2 if crit == 4 else (0 if crit == 1 else 1)
	for b in blows:
		if not p["alive"]:
			break
		var roll: int = _d(20)
		if roll != 20 and (roll == 1 or roll < thac0 - int(p["ac"])):
			_spawn_splat(p["sprite"], 3)  # grey puff = miss
			continue
		var dmg: int = _d(int(m["sides"]), int(m["dice"])) + dmg_bonus
		p["hp"] = maxi(0, int(p["hp"]) - dmg)
		_hud_refresh_member(party.find(p))
		_update_bar(p["bar_fg"], float(p["hp"]) / float(p["max_hp"]))
		_spawn_splat(p["sprite"], 1 if dmg >= 3 else 0)
		if p["hp"] <= 0:
			p["alive"] = false
			p["sprite"].modulate = Color(0.3, 0.3, 0.3, 0.6)
			p["bar_bg"].visible = false
			p["bar_fg"].visible = false
			break


func _party_wiped() -> bool:
	for p in party:
		if p["alive"]:
			return false
	return true


func _victory() -> void:
	fight_count += 1
	state = State.VICTORY
	_say_sequence([
		{"port": ANNOUNCER_PORT, "text": ANNOUNCER["heal"]},
		{"port": ANNOUNCER_PORT, "text": ANNOUNCER["yell"]},
	], _offer_yell)


func _offer_yell() -> void:
	var replies := [ANNOUNCER["worst"], ANNOUNCER["best"], ANNOUNCER["again"]]
	var auto := 1.5 if OS.get_environment("SPIKE_DEMO") != "" else 0.0
	var pick := ChoiceScreen.new(replies, auto, 1)
	pick.chosen.connect(_on_yell)
	_close_ui()
	ui_screen = pick
	ui_layer.add_child(pick)
	ui_open = true


func _on_yell(i: int) -> void:
	if i == 1:
		# the compliment: the announcer is pleased, the pens open
		_say_sequence([{"port": ANNOUNCER_PORT, "text": ANNOUNCER["wellthanks"]}],
			func() -> void: state = State.PLAY)
	else:
		# taunts release another horde
		_say_sequence([
			{"port": ANNOUNCER_PORT, "text": ANNOUNCER["takethis"]},
			{"port": ANNOUNCER_PORT, "text": ANNOUNCER["release2"]},
		], _begin_fight)


func _party_down() -> void:
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


## DEX missile table (docs/rules-tables.md, DGROUP 0x7dc): the engine
## reads this same table for the round threshold's dex_reaction
## (combat-flow.md section 4, ovr10 stub 14). Stat 3 -> -3 ... 25 -> +5.
func _dex_reaction(dex: int) -> int:
	var table := [-3, -2, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 2, 3, 3, 4, 4, 4, 5, 5]
	return table[clampi(dex, 3, 25) - 3]


## 8-way direction code from the attacker to the target tile
## (N=0, clockwise), used for the rear/flank rule.
func _attack_dir(from: Vector2i, to: Vector2i) -> int:
	var d := to - from
	if d == Vector2i.ZERO:
		return 0
	return wrapi(int(round(atan2(float(d.x), float(-d.y)) / (PI / 4.0))), 0, 8)


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


## BMP 5014 splat over a hit target (frames: 0 small red, 1 big red,
## 2 green, 3 grey puff, 4 gold star; the demo maps big hits, misses
## and kills onto them).
func _spawn_splat(target: Sprite2D, frame: int) -> void:
	var s := Sprite2D.new()
	s.texture = load("res://generated/ui/splat_f%d.png" % frame)
	s.centered = false
	var tw := target.texture.get_width() / 2.0 - s.texture.get_width() / 2.0
	s.position = target.position + Vector2(tw,
		-target.texture.get_height() - s.texture.get_height() / 2.0 + 8.0)
	$Floats.add_child(s)
	var anim := create_tween()
	anim.tween_interval(0.45)
	anim.tween_property(s, "modulate:a", 0.0, 0.25)
	anim.tween_callback(s.queue_free)


# ------------------------------------------------- scripted full loop

func _scripted() -> void:
	await get_tree().create_timer(6.0).timeout
	_intro_part = 99
	_intro_wait = 0.0
	await get_tree().create_timer(1.0).timeout
	_walk_to_then(Vector2i(113, 27))
	await _drain()
	while ui_open:
		await get_tree().process_frame
	await get_tree().create_timer(0.3).timeout
	if region_id == 42:
		while ui_open:
			await get_tree().process_frame
		_walk_to_then(Vector2i(30, 22))
		await _drain()
		while ui_open:
			await get_tree().process_frame
		while state == State.COMBAT:
			if phase == Phase.PARTY and attacks_left > 0:
				var mi := _nearest_mon()
				if mi >= 0 and _cheby(_party_tile(0), monsters[mi]["tile"]) <= 1:
					_party_attack(mi)
					await get_tree().create_timer(0.4).timeout
					if attacks_left <= 0:
						_end_party_turn()
				else:
					_end_party_turn()
			await get_tree().process_frame
		await get_tree().create_timer(1.0).timeout
		if region_id == 42:
			_walk_to_then(Vector2i(30, 11))
			await _drain()
			await get_tree().create_timer(0.5).timeout
	get_tree().quit()


func _nearest_mon() -> int:
	var best := -1
	var bd := 99999
	for mi in monsters.size():
		if not monsters[mi]["alive"]:
			continue
		var d: int = _cheby(monsters[mi]["tile"], tile)
		if d < bd:
			bd = d
			best = mi
	return best


func _walk_to_then(t: Vector2i) -> void:
	path = _bfs(tile, t)


func _drain() -> void:
	while (not path.is_empty() or busy) and state == State.PLAY:
		await get_tree().process_frame


func _snap(p: String) -> void:
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(p)


# ------------------------------------------------- exploration tour

func _tour() -> void:
	_start_game()
	await get_tree().create_timer(0.6).timeout
	var stops := [
		[Vector2i(68, 80), "the fountain court"],
		[Vector2i(29, 88), "Pehtucl's quarters (southwest)"],
		[Vector2i(14, 52), "the monster pens (west)"],
		[Vector2i(86, 65), "Mirlon's corner (center)"],
		[Vector2i(98, 95), "Dinos' kitchen (southeast)"],
		[Vector2i(85, 78), "Scar's corner"],
		[Vector2i(113, 27), "the arena stair"],
	]
	for s in stops:
		_show_banner(String(s[1]))
		_walk_to_then(s[0])
		await _drain()
		await get_tree().create_timer(1.2).timeout
	_enter_region(42, Vector2i(30, 13))
	await get_tree().create_timer(0.6).timeout
	_show_banner("The Arena of Draj")
	await get_tree().create_timer(1.5).timeout
	_walk_to_then(Vector2i(30, 24))
	await _drain()
	await get_tree().create_timer(1.0).timeout
	get_tree().quit()
