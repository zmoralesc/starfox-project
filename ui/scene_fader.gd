extends CanvasLayer
## Autoload (SceneFader) that fades the screen to black, changes scene, and
## fades back in. Blocks clicks while fading.

@export var fade_out_time := 0.6
@export var fade_in_time := 0.9

var _rect: ColorRect
var _busy := false


func _ready() -> void:
	layer = 100
	process_mode = Node.PROCESS_MODE_ALWAYS
	_rect = ColorRect.new()
	_rect.color = Color.BLACK
	_rect.modulate.a = 0.0
	_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(_rect)


func is_fading() -> bool:
	return _busy


func change_scene(path: String) -> void:
	await _transition(get_tree().change_scene_to_file.bind(path))


## Fades out, restarts the current scene (Level, after the player's death),
## and fades back in.
func reload_scene() -> void:
	await _transition(get_tree().reload_current_scene)


## Fades to black, calls `swap` (which changes the scene), then fades back in
## over the new one.
func _transition(swap: Callable) -> void:
	if _busy:
		return
	_busy = true
	_rect.mouse_filter = Control.MOUSE_FILTER_STOP
	await _fade_to(1.0, fade_out_time)
	# Paused during the fade-out (the fade runs regardless): don't carry it
	# over into the new scene, whose pause menu would be closed.
	get_tree().paused = false
	swap.call()
	# The new scene is added at the end of this frame; start fading in once it's there.
	await get_tree().process_frame
	await get_tree().process_frame
	await _fade_to(0.0, fade_in_time)
	_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_busy = false


func _fade_to(alpha: float, duration: float) -> void:
	var tween := create_tween()
	tween.tween_property(_rect, "modulate:a", alpha, duration)
	await tween.finished
