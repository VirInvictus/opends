# QC harness: shows one WIND window for layout diffs against the oracle
# captures. Run with:
#   SPIKE_WIND=11500 godot --path . res://wind_test.tscn
# SPIKE_TEXT optionally preloads an EBOX string ("id:text,id:text").
extends Node2D


func _ready() -> void:
	var bg := ColorRect.new()
	bg.color = Color.BLACK
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.size = get_viewport_rect().size
	add_child(bg)
	var wid := int(OS.get_environment("SPIKE_WIND"))
	var screen := OS.get_environment("SPIKE_SCREEN")
	var ws: WindScreen
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
	else:
		ws = WindScreen.new(wid)
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
