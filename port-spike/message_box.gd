# MessageBox: WIND 10501, the engine's transient message strip
# (bmp10001 face, 192x28; the whole face is BUTN 10309 - click
# acknowledges). Fed by the 0x520:0x34 service with lines like
# "GAME SAVED" (screen-flow.md 8.7). Renders centred, auto-fades.
extends Node2D
class_name MessageBox

const PLATE := Vector2(192, 28)
const BOARD := Vector2(320, 200)

var text := ""
var hold_seconds := 2.0

static func flash(layer: Node2D, p_text: String, hold := 2.0) -> void:
	var mb := MessageBox.new()
	mb.text = p_text
	mb.hold_seconds = hold
	layer.add_child(mb)

func _ready() -> void:
	var k := maxi(int(minf(get_viewport_rect().size.x / BOARD.x,
		get_viewport_rect().size.y / BOARD.y)), 1)
	var board := Node2D.new()
	board.scale = Vector2(k, k)
	add_child(board)
	var plate := Sprite2D.new()
	plate.texture = load("res://generated/ui/bmp10001.png")
	plate.centered = false
	plate.position = (BOARD - PLATE) / 2.0
	board.add_child(plate)
	var t := TextBlitter.new()
	t.ink = Color8(214, 214, 222)
	t.relief = Color8(24, 24, 40)
	t.text = text
	t.position = plate.position + Vector2((PLATE.x - TextBlitter.width_of(text)) / 2.0,
		(PLATE.y - 9.0) / 2.0 + 1.0)
	board.add_child(t)
	var tw := create_tween()
	tw.tween_interval(hold_seconds)
	tw.tween_property(self, "modulate:a", 0.0, 0.4)
	tw.tween_callback(queue_free)
