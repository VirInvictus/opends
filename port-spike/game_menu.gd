# GameMenuScreen: WIND 10500 on the stone plate (BMP 10000). Every icon
# routes to its mined action (screen-flow.md 8.7): the view screens,
# the EXIT/LOAD-SAVE popups, preferences, overhead map, party collapse,
# the three cursor modes, center-on-leader (combat-gated) and X close.
# Tooltips print into item 11270 from the mined table.
extends WindScreen
class_name GameMenuScreen

const ROW_INK := Color8(214, 214, 222)
const ROW_RELIEF := Color8(24, 24, 40)
const TOOLTIPS := {
	10301: "EXIT TO DOS", 10302: "LOAD/SAVE GAME", 10303: "SET PREFERENCES",
	10305: "OVERHEAD MAP", 10306: "COLLAPSE PARTY", 10310: "MOVE CURSOR",
	10311: "LOOK CURSOR", 10312: "ATTACK CURSOR", 10313: "CENTER ON LEADER",
}

signal screen_requested(name: String)

func _init() -> void:
	window_id = 10500
	# collapse-party rests on the coloured party art; the silhouettes
	# are its pressed frame (oracle capture, 2026-09-20)
	resting_frames = {10313: 2}

var _tooltip: TextBlitter

func _ready() -> void:
	super._ready()
	_tooltip = TextBlitter.new()
	_tooltip.position = Vector2(32, 136)
	_tooltip.ink = ROW_INK
	_tooltip.relief = ROW_RELIEF
	_board.add_child(_tooltip)

func _unhandled_input(event: InputEvent) -> void:
	super._unhandled_input(event)
	if event is InputEventMouseMotion:
		var p: Vector2 = _board.get_global_transform().affine_inverse() * event.position
		var tip := ""
		for b in _buttons:
			if TOOLTIPS.has(int(b["id"])) and (b["rect"] as Rect2).has_point(p):
				tip = TOOLTIPS[int(b["id"])]
				break
		_tooltip.text = tip
	elif event is InputEventMouseButton and event.pressed \
			and event.button_index == MOUSE_BUTTON_LEFT:
		var pos: Vector2 = _board.get_global_transform().affine_inverse() * event.position
		for b in _buttons:
			var iid: int = int(b["id"])
			if (b["rect"] as Rect2).has_point(pos):
				_activate(iid)
				return

func _activate(iid: int) -> void:
	match iid:
		10300:
			screen_requested.emit("sheet")
		11304:
			screen_requested.emit("inventory")
		11305:
			screen_requested.emit("sheet:USE")
		11306:
			screen_requested.emit("sheet:EFFECTS")
		10301:
			_popup_exit()
		10302:
			screen_requested.emit("popup:loadsave")
		10303:
			screen_requested.emit("prefs")
		10305:
			screen_requested.emit("map")
		10306:
			screen_requested.emit("collapse")
		10310, 10311, 10312:
			pass  # cursor modes: combat-side wiring (Wave 3)
		10313:
			screen_requested.emit("center")
		10308:
			screen_requested.emit("close")

func _popup_exit() -> void:
	# combat shows QUIT/CANCEL; peace adds SAVE (screen-flow.md 8.7)
	screen_requested.emit("popup:exit")
