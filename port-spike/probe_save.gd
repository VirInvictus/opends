extends SceneTree
func _init():
	# seed cells like the inventory screen does, then round-trip
	PartyData.MEMBERS[1]["cells"] = []
	for i in 26:
		PartyData.MEMBERS[1]["cells"].append(null)
	PartyData.MEMBERS[1]["cells"][2] = {"obj": 1010}
	PartyData.MEMBERS[1]["cells"][3] = {"obj": 1011}
	var st := {
		"label": "TEST SAVE",
		"members": PartyData.MEMBERS,
		"port": {"region": 41, "tile": [112, 27], "fight_count": 2, "gold": 0},
	}
	var err: int = SaveIO.write_save("/tmp/spike-oracle/SAVE01.SAV", st)
	print("write: ", err)
	var back := SaveIO.read_save("/tmp/spike-oracle/SAVE01.SAV")
	print("label: ", back["label"])
	print("port: ", back["port"])
	print("member1 cells: ", back["members"][1].get("cells"))
	# the raw STXT chunk must read as the engine's save-name layout
	var f := FileAccess.open("/tmp/spike-oracle/SAVE01.SAV", FileAccess.READ)
	var data := f.get_buffer(f.get_length())
	print("has GFFI: ", data.slice(0, 4).get_string_from_ascii() == "GFFI")
	quit()
