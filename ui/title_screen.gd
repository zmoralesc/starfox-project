extends Node3D
## Title screen: a slowly turning starfield behind a Start / Settings / Exit
## menu. Start opens the mission selector; picking a mission loads its level.

@export var camera_spin_speed := 0.03
## Title music (lead + loop). Empty = silence (fades out a level's music when
## quitting to the title).
@export var music: LevelMusic

@onready var _camera: Camera3D = $Camera3D
@onready var _start_button: Button = %StartButton
@onready var _settings_button: Button = %SettingsButton
@onready var _exit_button: Button = %ExitButton
@onready var _menu: Control = $UI/Center
@onready var _settings: Control = %SettingsMenu
@onready var _mission_select: Control = %MissionSelect


func _ready() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	_start_button.pressed.connect(_on_start_pressed)
	_exit_button.pressed.connect(_on_exit_pressed)
	_settings_button.pressed.connect(_on_settings_pressed)
	_settings.closed.connect(_on_settings_closed)
	_mission_select.chosen.connect(_on_mission_chosen)
	_mission_select.closed.connect(_on_mission_select_closed)
	# Browsers can't close the tab from a game, so hide Exit on web builds.
	_exit_button.visible = not OS.has_feature("web")
	# Focus Start so keyboard and gamepad work without touching the mouse.
	_start_button.grab_focus()
	Music.play(music)


func _process(delta: float) -> void:
	_camera.rotate_y(camera_spin_speed * delta)


func _on_start_pressed() -> void:
	_menu.hide()
	_mission_select.open()


func _on_mission_chosen(mission: Mission) -> void:
	SceneFader.change_scene(mission.scene_path)


func _on_mission_select_closed() -> void:
	_menu.show()
	_start_button.grab_focus()
	Music.play(music)


func _on_settings_pressed() -> void:
	_menu.hide()
	_settings.open()


func _on_settings_closed() -> void:
	_menu.show()
	_settings_button.grab_focus()


func _on_exit_pressed() -> void:
	get_tree().quit()
