extends SceneTree
func _init():
	var board := Node2D.new()
	board.scale = Vector2(4, 4)
	root.add_child(board)
	var hud := CombatHud.new()
	board.add_child(hud)
	hud.set_actor("K'TARCHEK", 15, 15, 150, "Okay")
	await process_frame
	await process_frame
	print("hud children: ", hud.get_child_count())
	for c in hud.get_children():
		var t := ""
		if c is Sprite2D:
			var sp: Sprite2D = c
			t = "tex=" + (sp.texture.resource_path if sp.texture != null else "NULL")
		print("  child: ", c.get_class(), " pos=", c.position, " ", t)
	quit()
