# TextBlitter: FONT/100 rendered as two white masks (ink + relief) that
# modulate to any color pair, since the engine recolors text at print
# time (%C ink/relief pairs). Glyphs advance by their own width, line
# pitch 9, no kerning and no bearings, exactly like the engine.
class_name TextBlitter
extends Node2D

static var _metrics: Dictionary
static var _ink: Texture2D
static var _relief: Texture2D

var text := "":
	set(v):
		text = v
		queue_redraw()
var ink := Color.BLACK:
	set(v):
		ink = v
		queue_redraw()
var relief := Color(56 / 255.0, 56 / 255.0, 85 / 255.0):
	set(v):
		relief = v
		queue_redraw()


static func _ensure() -> void:
	if not _metrics.is_empty():
		return
	var f := FileAccess.open("res://generated/ui/font_metrics.json", FileAccess.READ)
	_metrics = JSON.parse_string(f.get_as_text())
	_ink = load("res://generated/ui/" + str(_metrics["ink_png"]))
	_relief = load("res://generated/ui/" + str(_metrics["relief_png"]))


static func width_of(s: String) -> float:
	_ensure()
	var w := 0.0
	for ch in s:
		var g: Dictionary = _metrics["chars"].get(str(ch.unicode_at(0)), {})
		w += float(g.get("w", 4))
	return w


func _ready() -> void:
	_ensure()


func _draw() -> void:
	_ensure()
	var cw: int = int(_metrics["cell_w"])
	var h: int = int(_metrics["height"])
	var pen := 0.0
	for ch in text:
		var code := ch.unicode_at(0)
		if code == 10:
			continue
		var g: Dictionary = _metrics["chars"].get(str(code), {})
		if g.is_empty():
			pen += 4.0
			continue
		var w: int = int(g["w"])
		var r := Rect2(g["u"], g["v"], w, h)
		draw_texture_rect_region(
			_relief, Rect2(Vector2(pen, 0), Vector2(w, h)), r, relief)
		draw_texture_rect_region(
			_ink, Rect2(Vector2(pen, 0), Vector2(w, h)), r, ink)
		pen += w
