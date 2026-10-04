class_name Level
extends Node3D
## Logic every mission shares: builds the level's world, plays the intro (and
## the leader's intro line), starts the enemy spawner once the player has
## control, restarts the level after the player dies, and keeps the mouse
## captured.
##
## Every mission scene inherits levels/level_base.tscn, which holds the shared
## nodes (ship, camera, wingmen, HUD, comms, pause menu, intro...). A mission
## adds its own world on top and, if it builds anything in code, extends this
## script and overrides _build_world().

## Seconds between the player's ship exploding and the level restarting.
@export var restart_delay := 3.0
## Off = no enemy waves (test missions).
@export var spawn_enemies := true
## The soundtrack (lead + loop). Empty = no music. Keeps playing across
## restarts after a death.
@export var music: LevelMusic

@export_group("Intro line")
## What the leader says over the comms as the level starts.
@export var intro_line := "We're approaching the combat zone."
## Seconds into the intro fly-by before the line starts.
@export var intro_line_delay := 0.5

## Set when restarting after death, so the player goes straight back in.
static var _skip_intro_once := false

var _intro_line_said := false

@onready var _intro: IntroCutscene = $IntroCutscene
@onready var _spawner: EnemySpawner = $EnemySpawner


func _ready() -> void:
	_build_world()
	Music.play(music)
	($Ship as Ship).died.connect(_on_player_died)
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	if _skip_intro_once:
		_skip_intro_once = false
		_begin_play()
	else:
		_intro.finished.connect(_begin_play, CONNECT_ONE_SHOT)
		_intro.play()
		get_tree().create_timer(intro_line_delay, false).timeout.connect(_say_intro_line)


## Override to generate the mission's world (asteroids, terrain...). Runs
## first in _ready(), before the intro starts.
func _build_world() -> void:
	pass


## Player has control: start sending enemies.
func _begin_play() -> void:
	if spawn_enemies:
		_spawner.start()
	# If the intro was skipped before the line started, say it now.
	_say_intro_line()


func _say_intro_line() -> void:
	if _intro_line_said or not is_inside_tree():
		return
	_intro_line_said = true
	var comms := Comms.find(get_tree())
	var leader := $Ship as Ship
	if comms and leader.speaker:
		comms.say(leader.speaker, intro_line)


func _on_player_died() -> void:
	await get_tree().create_timer(restart_delay, false).timeout
	_skip_intro_once = true
	get_tree().reload_current_scene()


func _unhandled_input(event: InputEvent) -> void:
	# Recapture if the mouse got released some other way (e.g. alt-tab).
	# Esc is handled by the pause menu.
	if event is InputEventMouseButton and event.pressed \
			and Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
