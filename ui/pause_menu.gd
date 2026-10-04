extends CanvasLayer
## In-game pause menu. Keeps processing while the tree is paused.
##
## Esc / gamepad Start toggles it; Esc or gamepad B also closes it. The game
## also pauses itself when the window loses focus.

const TITLE_SCENE := "res://ui/title_screen.tscn"

@onready var _resume_button: Button = %ResumeButton
@onready var _settings_button: Button = %SettingsButton
@onready var _quit_button: Button = %QuitButton
@onready var _menu: Control = $Center
@onready var _settings: Control = %SettingsMenu


func _ready() -> void:
	hide()
	_resume_button.pressed.connect(resume)
	_settings_button.pressed.connect(_on_settings_pressed)
	_quit_button.pressed.connect(_on_quit_pressed)
	_settings.closed.connect(_on_settings_closed)


func _unhandled_input(event: InputEvent) -> void:
	# The settings screen handles its own Back / Esc.
	if _settings.visible:
		return
	if event.is_action_pressed("pause"):
		if get_tree().paused:
			resume()
		else:
			pause()
		get_viewport().set_input_as_handled()
	elif visible and event.is_action_pressed("ui_cancel"):
		resume()
		get_viewport().set_input_as_handled()


func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT and is_inside_tree() and not get_tree().paused:
		pause()


func pause() -> void:
	get_tree().paused = true
	show()
	_menu.show()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	_resume_button.grab_focus()


func resume() -> void:
	if _settings.visible:
		_settings.close()
	get_tree().paused = false
	hide()
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func _on_settings_pressed() -> void:
	_menu.hide()
	_settings.open()


func _on_settings_closed() -> void:
	_menu.show()
	_settings_button.grab_focus()


func _on_quit_pressed() -> void:
	get_tree().paused = false
	get_tree().change_scene_to_file(TITLE_SCENE)
