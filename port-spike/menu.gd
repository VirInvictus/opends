# The main menu and character creation, on the original's rules.
#
# The menu screen is assembled entirely from the game's own data
# (generated/ui.json): BMP 20029 stone panel + BMP 20028 burning arc as
# the furniture, the four ICON/2048..2051 flickering text buttons at
# their WIND/3000 positions, accelerator keys S/C/L/E from ACCL/8100
# (screen-flow.md 2). Creation mechanics follow the mined pipeline
# (docs/chargen-flow.md): race list with class masks (record 104), stat
# roll = best of 4 x (4d4 + racial modifier + 4) with prime stats
# floored at 17 and the racial+20 cap, level 3 start with XP from the
# class row, HP from the class hit die.
extends Control

const RACES := ["Human", "Dwarf", "Elf", "Half-Elf", "Half-Giant", "Mul", "Thri-kreen"]
const RACE_MODS := [
	[0, 0, 0, 0, 0, 0], [1, -1, 2, 0, 0, -2], [0, 2, -2, 1, -1, 0],
	[0, 1, -1, 0, 0, 0], [4, -5, 2, -5, -3, -3], [-2, 2, -1, 0, 2, -1],
	[2, 0, 1, -1, 0, -2], [0, 2, 0, -1, 1, -2],
]  # STR DEX CON INT WIS CHA, record 103 +0x14d
const RACE_MASK := [0xFF, 0xB5, 0xBF, 0xFF, 0xB6, 0xF7, 0xF5]  # record 104, bit (0x80 >> c)
const RACE_MOVE := [12, 6, 12, 12, 14, 12, 15]
const RACE_BMP := [2095, 2095, 2059, 2095, 2095, 2095, 2097]
const CLASSES := ["Cleric", "Druid", "Fighter", "Gladiator", "Preserver", "Psionicist", "Ranger", "Thief"]
const CLASS_MIN := [9, 12, 9, 13, 9, 12, 14, 9]  # record 103 +0x180
const CLASS_PRIME := [4, 4, 0, 0, 3, 4, 4, 1]  # stat index of the prime requirement
const CLASS_DIE := [8, 8, 10, 10, 4, 6, 8, 6]  # group hit die
const CLASS_RATE := [8, 8, 12, 12, 4, 8, 12, 6]  # THAC0 rate per 12 levels
const XP_ROWS := [
	[0, 15, 30, 60, 130, 275, 550, 1100, 2250, 4500, 6750, 9000, 11250, 13500, 15750, 18000, 20250, 22500, 24750, 27000],
	[0, 20, 40, 75, 125, 200, 350, 600, 900, 1250, 6750, 9000, 11250, 13500, 15750, 18000, 20250, 22500, 24750, 27000],
	[0, 20, 40, 80, 160, 320, 640, 1250, 2500, 5000, 7500, 10000, 12500, 15000, 17500, 20000, 22500, 25000, 27500, 30000],
	[0, 20, 40, 80, 160, 320, 640, 1250, 2500, 5000, 7500, 10000, 12500, 15000, 17500, 20000, 22500, 25000, 27500, 30000],
	[0, 25, 50, 100, 200, 400, 600, 900, 1350, 2500, 3750, 7500, 11250, 15000, 18750, 22500, 26250, 30000, 33750, 37500],
	[0, 22, 44, 88, 165, 300, 550, 1000, 2000, 4000, 6000, 8000, 10000, 12000, 15000, 18000, 21000, 14000, 17000, 30000],
	[0, 22, 45, 90, 180, 360, 750, 1500, 3000, 6000, 9000, 12000, 15000, 18000, 21000, 24000, 27000, 30000, 33000, 36000],
	[0, 12, 25, 50, 100, 200, 400, 700, 1100, 1600, 2200, 4400, 6600, 8800, 11000, 13200, 15400, 17600, 19800, 22000],
]  # DS2 DATA:1000 (RESOURCE.GFF); entry k = XP x100 for level k+1

const STAT_NAMES := ["STR", "DEX", "CON", "INT", "WIS", "CHA"]

var race_idx := 0
var gender := 0  # 0 male, 1 female
var class_idx := 2  # Fighter
var stats := [0, 0, 0, 0, 0, 0]
var stat_labels: Array[Label] = []
var created := false
var ui_data := {}
var _board: Node2D
var _menu_buttons: Array[Dictionary] = []
var _menu_scale := 2.0
var _msg: Label


func _ready() -> void:
	ui_data = JSON.parse_string(
		FileAccess.open("res://generated/ui.json", FileAccess.READ).get_as_text()
	)
	var bg := ColorRect.new()
	bg.color = Color.BLACK
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	_board = Node2D.new()
	_board.name = "MenuBox"
	add_child(_board)
	_build_menu()
	_creation_panel()
	get_viewport().size_changed.connect(_layout_board)
	_layout_board()
	if OS.get_environment("SPIKE_MENU") != "":
		_on_create()
		_scripted_create()
	elif OS.get_environment("SPIKE_DEMO") != "":
		# Demo QC boots straight into the intro + scripted loop.
		get_tree().change_scene_to_file("res://main.tscn")


func _layout_board() -> void:
	var vp := get_viewport().get_visible_rect().size
	_menu_scale = minf(vp.x / 320.0, vp.y / 200.0)
	_board.scale = Vector2(_menu_scale, _menu_scale)
	_board.position = (vp - Vector2(320, 200) * _menu_scale) / 2.0
	var panel := get_node_or_null("Create")
	if panel is Control:
		panel.position = (vp - (panel as Control).size) / 2.0


func _tex(fname: String) -> Texture2D:
	return load("res://generated/ui/" + fname)


func _build_menu() -> void:
	for key in ["panel", "arc"]:
		var art: Dictionary = ui_data[key]
		var s := Sprite2D.new()
		s.texture = _tex(str(art["png"]))
		s.centered = false
		s.position = Vector2(float(art["pos"][0]), float(art["pos"][1]))
		_board.add_child(s)
	for b in ui_data["buttons"]:
		var frames: Array = b["frames"]
		var stf := SpriteFrames.new()
		stf.add_animation("flicker")
		stf.set_animation_speed("flicker", 6.0)
		stf.set_animation_loop("flicker", true)
		for f in frames:
			if int(f["w"]) < 8:  # some icons carry a 1x1 placeholder frame
				continue
			stf.add_frame("flicker", _tex(str(f["png"])))
		var s := AnimatedSprite2D.new()
		s.sprite_frames = stf
		s.animation = "flicker"
		s.centered = false
		s.position = Vector2(float(b["x"]), float(b["y"]))
		s.name = str(b["name"])
		_board.add_child(s)
		_menu_buttons.append({"name": str(b["name"]), "rect": Rect2(
			Vector2(float(b["x"]), float(b["y"])),
			Vector2(float(b["w"]), float(b["h"])))})
	_msg = Label.new()
	_msg.position = Vector2(40, 182)
	_msg.size = Vector2(240, 14)
	_msg.add_theme_font_size_override("font_size", 10)
	_msg.add_theme_color_override("font_color", Color(0.75, 0.65, 0.45))
	_msg.text = ""
	_board.add_child(_msg)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not created:
		match event.keycode:
			KEY_S:
				_on_start()
			KEY_C:
				_on_create()
			KEY_L:
				_on_load()
			KEY_E:
				get_tree().quit()
	elif event is InputEventMouseButton and event.pressed \
			and event.button_index == MOUSE_BUTTON_LEFT and not created:
		var pos: Vector2 = (_board.get_global_transform().affine_inverse() * event.position)
		for b in _menu_buttons:
			if (b["rect"] as Rect2).has_point(pos):
				match b["name"]:
					"start":
						_on_start()
					"create":
						_on_create()
					"load":
						_on_load()
					"exit":
						get_tree().quit()


func _on_start() -> void:
	var f := FileAccess.open("res://generated/created.json", FileAccess.WRITE)
	f.store_string(JSON.stringify({"use_presets": true}))
	_launch()


func _on_load() -> void:
	_msg.text = "Load Game is not part of this demo."
	_msg.modulate = Color(0.9, 0.3, 0.2)


func _on_exit() -> void:
	get_tree().quit()


func _on_create() -> void:
	created = true
	_board.visible = false
	$Create.visible = true
	_layout_board()
	_reroll()


func _scripted_create() -> void:
	# QC path: pick Mul Gladiator, reroll twice, name it, accept.
	await get_tree().create_timer(1.0).timeout
	(_node("Races") as ItemList).select(5)
	_on_change()
	(_node("Classes") as ItemList).select(3)
	_reroll()
	await get_tree().create_timer(0.8).timeout
	_reroll()
	(_node("NameBox") as LineEdit).text = "Demo"
	await get_tree().create_timer(0.8).timeout
	_accept()


# ------------------------------------------------------------ creation

func _creation_panel() -> void:
	var panel := PanelContainer.new()
	panel.name = "Create"
	panel.visible = false
	panel.position = Vector2(60, 24)
	panel.size = Vector2(520, 352)
	add_child(panel)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	panel.add_child(row)

	var left := VBoxContainer.new()
	left.add_theme_constant_override("separation", 4)
	row.add_child(left)
	left.add_child(_head("Race"))
	var races := ItemList.new()
	races.name = "Races"
	races.custom_minimum_size = Vector2(150, 120)
	for r in RACES:
		races.add_item(r)
	races.select(0)
	races.item_selected.connect(func(_i): _on_change())
	left.add_child(races)
	left.add_child(_head("Gender"))
	var gen := ItemList.new()
	gen.name = "Gender"
	gen.custom_minimum_size = Vector2(150, 48)
	gen.add_item("Male")
	gen.add_item("Female")
	gen.select(0)
	gen.item_selected.connect(func(_i): _on_change())
	left.add_child(gen)
	left.add_child(_head("Name"))
	var namef := LineEdit.new()
	namef.name = "NameBox"
	namef.text = "Nameless"
	namef.custom_minimum_size = Vector2(150, 30)
	left.add_child(namef)

	var mid := VBoxContainer.new()
	mid.add_theme_constant_override("separation", 4)
	row.add_child(mid)
	mid.add_child(_head("Class"))
	var classes := ItemList.new()
	classes.name = "Classes"
	classes.custom_minimum_size = Vector2(150, 120)
	for c in CLASSES:
		classes.add_item(c)
	classes.select(2)
	classes.item_selected.connect(func(_i): _on_change())
	mid.add_child(classes)
	mid.add_child(_head("Class facts"))
	var facts := Label.new()
	facts.name = "Facts"
	facts.text = ""
	mid.add_child(facts)

	var right := VBoxContainer.new()
	right.add_theme_constant_override("separation", 4)
	row.add_child(right)
	right.add_child(_head("Ability scores"))
	for i in 6:
		var l := Label.new()
		l.text = "%s: --" % STAT_NAMES[i]
		l.add_theme_font_size_override("font_size", 15)
		right.add_child(l)
		stat_labels.append(l)
	var reroll := Button.new()
	reroll.text = "Reroll"
	reroll.custom_minimum_size = Vector2(120, 28)
	reroll.pressed.connect(_reroll)
	right.add_child(reroll)
	var go := Button.new()
	go.text = "Accept - walk into the pens"
	go.custom_minimum_size = Vector2(160, 32)
	go.pressed.connect(_accept)
	right.add_child(go)
	var banner := Label.new()
	banner.name = "CBanner"
	banner.text = " "
	banner.add_theme_color_override("font_color", Color(0.9, 0.5, 0.2))
	right.add_child(banner)


func _head(txt: String) -> Label:
	var l := Label.new()
	l.text = txt
	l.add_theme_font_size_override("font_size", 14)
	l.add_theme_color_override("font_color", Color(0.9, 0.62, 0.2))
	return l


func _node(n: String) -> Node:
	return $Create.find_child(n, true, false)


func _sel(n: String) -> int:
	var il: ItemList = _node(n)
	var sel := il.get_selected_items()
	return sel[0] if sel.size() > 0 else 0


func _on_change() -> void:
	_filter_classes()
	_show_facts()


func _filter_classes() -> void:
	var classes: ItemList = _node("Classes")
	var mask: int = RACE_MASK[_sel("Races")]
	classes.clear()
	for c in CLASSES.size():
		if mask & (0x80 >> c):
			classes.add_item(CLASSES[c])
	classes.select(0)


func _show_facts() -> void:
	var facts: Label = _node("Facts")
	var ci := _sel("Classes")
	facts.text = "Hit die: d%d\nPrime: %s (min 17 on roll)\nClass minimum: %s %d" % [
		CLASS_DIE[ci], STAT_NAMES[CLASS_PRIME[ci]],
		STAT_NAMES[CLASS_PRIME[ci]], CLASS_MIN[ci]]


func _d4() -> int:
	return randi_range(1, 4)


func _d(sides: int) -> int:
	return randi_range(1, sides)


func _roll_stat(stat_i: int, primes: Array, race: int) -> int:
	var racial: int = RACE_MODS[race][stat_i]
	var best := 0
	for attempt in 4:  # best of four, per the engine's reroll service
		var v: int = _d4() + _d4() + _d4() + _d4() + racial + 4
		if v > best:
			best = v
	if stat_i in primes:
		best = maxi(best, 17)
	return clampi(best, 3, racial + 20)


func _reroll() -> void:
	var race := _sel("Races")
	var ci := _sel("Classes")
	var primes: Array = [CLASS_PRIME[ci]]
	stats = []
	for i in 6:
		stats.append(_roll_stat(i, primes, race))
	for i in 6:
		var mark := " *" if i == CLASS_PRIME[ci] else ""
		stat_labels[i].text = "%s: %d%s" % [STAT_NAMES[i], stats[i], mark]
	_show_facts()


func _accept() -> void:
	var race := _sel("Races")
	var ci := _sel("Classes")
	var gender := _sel("Gender")
	var cname: String = _node("NameBox").text
	if cname.strip_edges() == "":
		cname = "Nameless"
	var group_die: int = CLASS_DIE[ci]
	var con_floor := 1
	var hp: int = group_die  # level 1: maximum die
	for l in range(2, 4):  # levels 2..3: roll, floored
		hp += maxi(_d(group_die), con_floor)
	var thac0: int = 20 - (CLASS_RATE[ci] * 2) / 12
	var xp: int = XP_ROWS[ci][2] * 100
	var bmp: int = RACE_BMP[race]
	var rec := {
		"use_presets": false, "name": cname, "race": race, "gender": gender,
		"class": CLASSES[ci], "level": 3, "xp": xp, "bmp": bmp,
		"hp": hp, "max_hp": hp, "ac": 10, "thac0": thac0,
		"move": RACE_MOVE[race], "blows": 2 if CLASS_RATE[ci] == 12 else 1,
		"dice": 1, "sides": 8, "bonus": 1, "stats": stats,
	}
	var f := FileAccess.open("res://generated/created.json", FileAccess.WRITE)
	f.store_string(JSON.stringify(rec))
	_launch()


func _launch() -> void:
	Engine.set_meta("skip_intro", true)
	get_tree().change_scene_to_file("res://main.tscn")
