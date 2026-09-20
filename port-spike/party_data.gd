# Party data for the UI screens: the shipped preset party values as
# captured in the oracle (K'ratchek's triple-class readout matches the
# DOSBox capture exactly). Wave 3 swaps this for live records.
class_name PartyData

const MEMBERS := [
	{"name": "CERMAK", "hp": 54, "max": 54, "status": "Okay",
		"race": "HUMAN", "gender": "MALE", "align": "TRUE NEUTRAL",
		"classes": ["Fighter"], "levels": [3],
		"stats": [18, 15, 17, 12, 9, 12], "psi": [0, 0], "ac": 8,
		"thac0": 18, "moves": 12, "dmg": "1*1D1+1",
		"weapon_lines": ["", "", "", ""], "exp": 4000, "exp_next": 8000},
	{"name": "K'RATCHEK", "hp": 19, "max": 19, "status": "Okay",
		"race": "THRI-KREEN", "gender": "FEMALE", "align": "TRUE NEUTRAL",
		"classes": ["Fighter", "Druid", "Psionic"], "levels": [2, 2, 2],
		"ready_class": 1,
		"stats": [19, 21, 19, 16, 19, 15], "psi": [52, 52], "ac": 6,
		"thac0": 16, "moves": 15, "dmg": "4*1D4+7",
		"weapon_lines": ["Chatkcha", "1D6+2", "(4*1D4+7)", "(1D4+8)"], "exp": 2500, "exp_next": 4000},
	{"name": "SARIA", "hp": 45, "max": 45, "status": "Okay",
		"race": "HALF-ELF", "gender": "FEMALE", "align": "TRUE NEUTRAL",
		"classes": ["Ranger"], "levels": [3],
		"stats": [17, 16, 15, 13, 11, 10], "psi": [0, 0], "ac": 7,
		"thac0": 18, "moves": 12, "dmg": "1*1D1+1",
		"weapon_lines": ["", "", "", ""], "exp": 4000, "exp_next": 8000},
	{"name": "SILLA", "hp": 15, "max": 15, "status": "Okay",
		"race": "MUL", "gender": "MALE", "align": "LAWFUL NEUTRAL",
		"classes": ["Gladiator"], "levels": [3],
		"stats": [20, 15, 19, 10, 8, 9], "psi": [0, 0], "ac": 7,
		"thac0": 16, "moves": 12, "dmg": "1*1D1+1",
		"weapon_lines": ["", "", "", ""], "exp": 4000, "exp_next": 8000},
]
