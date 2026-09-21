# QC harness: shows one WIND window for layout diffs against the oracle
# captures. Run with:
#   SPIKE_WIND=11500 SPIKE_OUT=/tmp/x.png godot --path . res://wind_test.tscn
# SPIKE_SCREEN selects a controller (creation/inventory/sheet/spells/
# gamemenu/prefs/combathud); SPIKE_TEXT preloads EBOX strings
# ("id:text,id:text"). The viewport is saved to SPIKE_OUT automatically.
extends Node2D


func _ready() -> void:
	var bg := ColorRect.new()
	bg.color = Color.BLACK
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.size = get_viewport_rect().size
	add_child(bg)
	var wid := int(OS.get_environment("SPIKE_WIND"))
	var screen := OS.get_environment("SPIKE_SCREEN")
	var ws: Node2D
	if screen == "creation":
		ws = CreationScreen.new()
	elif screen == "inventory":
		ws = InventoryScreen.new()
	elif screen == "sheet":
		ws = SheetScreen.new()
	elif screen == "spells":
		ws = SpellScreen.new()
	elif screen == "gamemenu":
		ws = GameMenuScreen.new()
	elif screen == "prefs":
		ws = PrefsScreen.new()
	elif screen == "load":
		ws = LoadScreen.new()
	elif screen == "use":
		ws = SheetScreen.new(SheetScreen.Mode.USE)
	elif screen == "effects":
		ws = SheetScreen.new(SheetScreen.Mode.EFFECTS)
	elif screen == "map":
		ws = MapScreen.new(42)
	elif screen == "popup":
		ws = PopupScreen.new("EXIT GAME?", ["QUIT", "CANCEL"])
	elif screen == "choices":
		ws = ChoiceScreen.new([
			"Wounded rats, huh? Send out your worst!",
			"You're the best announcer I've seen.",
			"I want to fight again! Now!",
		])
	elif screen == "msgbox":
		MessageBox.flash(get_tree().root.get_node("^root/MsgHost") if false else self, "GAME SAVED")
		ws = null
	elif screen == "dialog":
		var pages := [{"port": 119, "text": "Citizens of Draj!\nBefore you is a handful of gladiators. Watch\nand be entertained as they fight to the\ndeath with the denizens of our land."}]
		ws = DialogScreen.new(pages)
	elif screen == "combathud":
		# defer: the window manager resizes us after the first frame;
		# size the board from the settled viewport
		await get_tree().process_frame
		await get_tree().process_frame
		var vp := get_viewport_rect().size
		var k := int(minf(vp.x / 320.0, vp.y / 200.0))
		k = maxi(k, 1)
		var board := Node2D.new()
		board.scale = Vector2(k, k)
		board.position = (vp - Vector2(320, 200) * k) / 2.0
		add_child(board)
		var hud := CombatHud.new()
		board.add_child(hud)
		hud.set_actor("K'TARCHEK", 15, 15, 150, "Okay")
	else:
		ws = WindScreen.new(wid)
	if ws != null:
		add_child(ws)
	var spec := OS.get_environment("SPIKE_TEXT")
	if spec != "":
		for part in spec.split(","):
			var kv := part.split(":", true, 1)
			if kv.size() != 2:
				continue
			var box := _find_blitter(ws, int(kv[0]))
			if box != null:
				box.text = kv[1]
	# QC hook: force a held item so the cursor icon and drop-target
	# highlight render in the still (SPIKE_HELD=<object id>)
	if ws is InventoryScreen and OS.get_environment("SPIKE_HELD") != "":
		ws.held = int(OS.get_environment("SPIKE_HELD"))
		ws._refresh()
	_snap()

func _snap() -> void:
	print("[SNAP] waiting frames")
	for i in 6:
		await RenderingServer.frame_post_draw
	var out := OS.get_environment("SPIKE_OUT")
	if out == "":
		out = "/tmp/spike-oracle/wind_test.png"
	print("[SNAP] saving to ", out)
	get_viewport().get_texture().get_image().save_png(out)
	print("[SNAP] saved")
	get_tree().quit()

func _find_blitter(root: Node, iid: int) -> TextBlitter:
	var want := "EBOX%d" % iid
	var stack := [root]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		if n.name == want and n is TextBlitter:
			return n
		for c in n.get_children():
			stack.push_back(c)
	return null
