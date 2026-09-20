extends SceneTree
func _init():
	var ws := WindScreen.new(10500)
	root.add_child(ws)
	await process_frame
	await process_frame
	for c in ws._board.get_children():
		var tex := ""
		if c is Sprite2D:
			var sp: Sprite2D = c
			tex = sp.texture.resource_path if sp.texture != null else "NULL"
		print(str(c.get_class()), " pos=", c.position, " tex=", tex)
	quit()
