# Party data for the UI screens: the shipped preset party values as
# captured in the oracle (K'ratchek's triple-class readout matches the
# DOSBox capture exactly). Static VAR, not const: screens and the save
# loader mutate these records in place (const containers are read-only).
class_name PartyData

static var MEMBERS := [
	{"name": "CERMAK", "hp": 54, "max": 54, "status": "Okay",
		"race": "HUMAN", "gender": "MALE", "align": "TRUE NEUTRAL",
		"classes": ["Fighter"], "levels": [3],
		"race_i": 1, "gender_i": 1, "align_i": 5, "class_ids": [9],
		"stats": [18, 15, 17, 12, 9, 12], "psi": [0, 0], "ac": 8, "bmp": 2095,
		"thac0": 18, "moves": 12, "dmg": "1*1D1+1",
		"weapon_lines": ["", "", "", ""], "exp": 4000, "exp_next": 8000},
	{"name": "K'RATCHEK", "hp": 19, "max": 19, "status": "Okay",
		"race": "THRI-KREEN", "gender": "FEMALE", "align": "TRUE NEUTRAL",
		"classes": ["Fighter", "Druid", "Psionic"], "levels": [2, 2, 2],
		"ready_class": 1,
		"race_i": 7, "gender_i": 2, "align_i": 5, "class_ids": [9, 5, 12],
		"stats": [19, 21, 19, 16, 19, 15], "psi": [52, 52], "ac": 6, "bmp": 2097,
		"thac0": 16, "moves": 15, "dmg": "4*1D4+7",
		"weapon_lines": ["Chatkcha", "1D6+2", "(4*1D4+7)", "(1D4+8)"], "exp": 2500, "exp_next": 4000,
		"spells": {"Druid": [6, 22, 3, 10, 7, 19, 23, 15, 21, 18]},},
	{"name": "SARIA", "hp": 45, "max": 45, "status": "Okay",
		"race": "HALF-ELF", "gender": "FEMALE", "align": "TRUE NEUTRAL",
		"classes": ["Ranger"], "levels": [3],
		"race_i": 4, "gender_i": 2, "align_i": 5, "class_ids": [15],
		"stats": [17, 16, 15, 13, 11, 10], "psi": [0, 0], "ac": 7, "bmp": 2059,
		"thac0": 18, "moves": 12, "dmg": "1*1D1+1",
		"weapon_lines": ["", "", "", ""], "exp": 4000, "exp_next": 8000, "spells": {"Druid": [3, 10, 7]}},
	{"name": "SILLA", "hp": 15, "max": 15, "status": "Okay",
		"race": "MUL", "gender": "MALE", "align": "LAWFUL NEUTRAL",
		"classes": ["Gladiator"], "levels": [3],
		"race_i": 6, "gender_i": 1, "align_i": 4, "class_ids": [10],
		"stats": [20, 15, 19, 10, 8, 9], "psi": [0, 0], "ac": 7, "bmp": 2099,
		"thac0": 16, "moves": 12, "dmg": "1*1D1+1",
		"weapon_lines": ["", "", "", ""], "exp": 4000, "exp_next": 8000},
]
