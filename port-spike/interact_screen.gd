# InteractScreen: WIND 3020, the interact strip (92x77) shown when
# clicking a world entity: TALK 15306 / STEAL 15308 / GIVE 15307 /
# INFO 15309 (screen-flow.md 8.1 area; port-digs-2026-09-20.md 3).
# The engine starts steal/give/INFO disabled and enables them from a
# capability mask (bit 0x4 talk, 0x1 steal, 0x10 give). The 15200
# plate art (145x87) is larger than the window - the engine clips it,
# so the port draws the bevel clipped to the window rect.
extends WindScreen
class_name InteractScreen

signal action(kind: String)

const CAP_TALK := 0x4
const CAP_STEAL := 0x1
const CAP_GIVE := 0x10

var caps := CAP_TALK | CAP_STEAL | CAP_GIVE | 0x2  # INFO always

const KINDS := {
	15306: "talk",
	15308: "steal",
	15307: "give",
	15309: "info",
}

func _init(p_caps := -1) -> void:
	window_id = 3020
	if p_caps >= 0:
		caps = p_caps

func _ready() -> void:
	# the 15200 plate (145x87) would overflow the 92x77 window: skip it
	# and draw the bevel clipped to the window rect instead
	skip_apfm = [15200]
	super._ready()
	var clipped := WindScreen.BevelPanel.new()
	clipped.rect = Rect2(Vector2.ZERO, Vector2(92, 77))
	clipped.seed_key = 15200
	_board.add_child(clipped)
	_board.move_child(clipped, 1)
	# dim buttons the capability mask does not allow
	for b in _buttons:
		var iid := int(b["id"])
		var enabled := true
		match iid:
			15306:
				enabled = (caps & CAP_TALK) != 0
			15308:
				enabled = (caps & CAP_STEAL) != 0
			15307:
				enabled = (caps & CAP_GIVE) != 0
		var spr: Sprite2D = b["sprite"]
		if spr != null:
			spr.modulate.a = 1.0 if enabled else 0.35
	item_activated.connect(_on_item)

func _on_item(item: Dictionary) -> void:
	var kind: String = KINDS.get(int(item["id"]), "")
	if kind != "":
		action.emit(kind)
