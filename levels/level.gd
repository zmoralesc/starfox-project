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

## Seconds between the player's wreck exploding and someone crying out for them.
@export var lament_delay := 0.5
## Seconds between that lament starting and the screen starting to fade to
## black before the restart.
@export var restart_delay := 2.5
## Off = no enemy waves (test missions).
@export var spawn_enemies := true
## The soundtrack (lead + loop). Empty = no music. Keeps playing across
## restarts after a death.
@export var music: LevelMusic
## Explosion styles set off once, invisibly small, when the mission loads, so
## the first real one doesn't stutter while its materials and shaders are built.
@export var prewarm_explosions: Array[ExplosionStyle] = [
	preload("res://effects/explosions/fighter.tres"),
	preload("res://effects/explosions/asteroid.tres"),
	preload("res://effects/explosions/destroyer_part.tres"),
	preload("res://effects/explosions/destroyer_chain.tres"),
	preload("res://effects/explosions/destroyer_final.tres"),
]
## The same for the water splash (WaterSplash), on missions with a `terrain`
## (there is no water to hit in space). Null = none.
@export var prewarm_splash: PackedScene = preload("res://effects/water_splash.tscn")
## The same for the bolts' hit effects (HitBurst scenes: on targets, on surfaces).
@export var prewarm_hit_bursts: Array[PackedScene] = [
	preload("res://effects/hit_burst.tscn"),
	preload("res://effects/surface_hit.tscn"),
]

@export_group("Intro line")
## What the leader says over the comms as the level starts.
@export var intro_line := "We're approaching the combat zone."
## Seconds into the intro fly-by before the line starts.
@export var intro_line_delay := 0.5
## What mission control (Peppy, the MissionControl's advisor) says once the
## player has control, after the intro. Empty = nothing.
@export_multiline var intro_advisor_line := ""
## Seconds after the player gets control before that line.
@export var intro_advisor_delay := 2.0

## Set when restarting after death, so the player goes straight back in.
static var _skip_intro_once := false

var _intro_line_said := false

@onready var _intro: IntroCutscene = $IntroCutscene
@onready var _spawner: EnemySpawner = $EnemySpawner


func _ready() -> void:
	_build_world()
	for style in prewarm_explosions:
		Explosion.prewarm(self, style)
	if prewarm_splash and get_tree().get_first_node_in_group("terrain"):
		WaterSplash.prewarm(prewarm_splash, self)
	for burst in prewarm_hit_bursts:
		HitBurst.prewarm(burst, self)
	Music.play(music)
	($Ship as Ship).wreck_destroyed.connect(_on_player_lost)
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
	if intro_advisor_line != "":
		get_tree().create_timer(intro_advisor_delay, false).timeout.connect(_say_intro_advisor_line)


func _say_intro_line() -> void:
	if _intro_line_said or not is_inside_tree():
		return
	_intro_line_said = true
	var comms := Comms.find(get_tree())
	var leader := $Ship as Ship
	if comms and leader.speaker:
		# HIGH so that if it's still on screen when the advisor's line comes
		# (intro skipped), that line queues behind it rather than cutting it
		# off (a HIGH line interrupts a LOW one). Nothing else is talking yet.
		comms.say(leader.speaker, intro_line, Comms.Priority.HIGH)


func _say_intro_advisor_line() -> void:
	if not is_inside_tree():
		return
	var mission_control := get_tree().get_first_node_in_group("mission_control") as MissionControl
	if mission_control:
		mission_control.say(intro_advisor_line)


## The death sequence, from the wreck's explosion on (the ship's died signal
## came earlier, when it became a wreck: Ship._die()): after lament_delay someone cries out,
## then the screen fades to black and the mission restarts.
func _on_player_lost() -> void:
	await get_tree().create_timer(lament_delay, false).timeout
	if not is_inside_tree():
		return
	_say_lament()
	await get_tree().create_timer(restart_delay, false).timeout
	if not is_inside_tree():
		return
	_restart()


## Restarts the mission after the player's death, behind a fade to black.
## Anything that should happen between losing the ship and trying again (lives,
## a game over instead of a restart) belongs here.
func _restart() -> void:
	_skip_intro_once = true
	SceneFader.reload_scene()


## A random character (a wingman or the mission's advisor) cries out for the
## lost leader, Star Fox 64 style, cutting off whatever else was being said.
func _say_lament() -> void:
	var comms := Comms.find(get_tree())
	if comms == null:
		return
	var speakers: Array[CommsSpeaker] = []
	for wingman in get_tree().get_nodes_in_group("wingmen"):
		var speaker := wingman.get("speaker") as CommsSpeaker
		if speaker and not speaker.laments.is_empty():
			speakers.append(speaker)
	var mission_control := get_tree().get_first_node_in_group("mission_control") as MissionControl
	if mission_control and mission_control.advisor and not mission_control.advisor.laments.is_empty():
		speakers.append(mission_control.advisor)
	if speakers.is_empty():
		return
	var chosen: CommsSpeaker = speakers.pick_random()
	comms.say(chosen, Array(chosen.laments).pick_random(), Comms.Priority.URGENT)


func _unhandled_input(event: InputEvent) -> void:
	# Recapture if the mouse got released some other way (e.g. alt-tab).
	# Esc is handled by the pause menu.
	if event is InputEventMouseButton and event.pressed \
			and Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
