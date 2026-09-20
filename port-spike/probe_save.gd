extends SceneTree
func _init():
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
	print("member0 hp: ", PartyData.MEMBERS[0]["hp"], " ac: ", PartyData.MEMBERS[0]["ac"],
		" name: ", PartyData.MEMBERS[0]["name"])
	print("member1 stats: ", PartyData.MEMBERS[1]["stats"])
	quit()
