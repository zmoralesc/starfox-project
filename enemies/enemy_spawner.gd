class_name EnemySpawner
extends Node
## Sends enemy fighters in waves. Each wave appears some distance from the
## player; every few waves a destroyer also arrives (through a warp portal
## beyond the edge of the zone: Destroyer.warp_in).
## The next wave comes a few seconds after every enemy (destroyer included)
## is gone. Also enforces a cap on how many enemy fighters can exist at once,
## counting both wave fighters and ones launched from destroyer hangars.

## The level's fighter type, used for waves and for destroyer hangar launches
## (unless the destroyer has its own: Destroyer.level_fighters).
## enemy_fighter.tscn is the elite fighter; light_fighter.tscn is the basic one.
@export var enemy_scene: PackedScene = preload("res://enemies/enemy_fighter.tscn")
@export var destroyer_scene: PackedScene = preload("res://enemies/destroyer.tscn")
@export var first_wave_size := 3
## Extra fighters per wave.
@export var wave_growth := 1
@export var max_wave_size := 8
@export var spawn_distance := 600.0
@export var first_wave_delay := 6.0
@export var wave_delay := 6.0
## A destroyer arrives on every Nth wave (5, 10, 15...). 0 = never.
@export var destroyer_every := 5
## Edge of the play area, centred on the origin. Destroyers arrive from a
## random direction on it (warping in just beyond it: Destroyer.portal_margin).
@export var zone_radius := 1000.0
## Most enemy fighters allowed alive at once.
@export var max_fighters := 12

@export_group("Space station")
## Waves appear at least this far from the space station (if the mission has
## one): the group's centre, which then scatters up to 40 m each way.
@export var spawn_station_margin := 100.0
## A destroyer heads for a point this far outside the station's bounding
## sphere instead of the zone's centre, and stops stop_distance short of it,
## so its bow (375 m ahead of its centre) stays clear of the station.
@export var destroyer_station_clearance := 300.0

@export_group("Planet missions")
## Waves appear at least this high above the ground, water or buildings (the group's
## centre; each fighter at least half this over the ground under it).
@export var spawn_altitude := 80.0
## ...and at least this far inside the play boundary (if the mission has one).
@export var spawn_boundary_margin := 250.0

## Current wave number (0 before the first wave). Read by the HUD.
var wave := 0
## The destroyer currently in play, if any.
var destroyer: Destroyer

var _wave_pending := false


func _ready() -> void:
	add_to_group("enemy_spawner")


## Begins the waves. Called by the level once the player has control.
func start() -> void:
	_schedule_wave(first_wave_delay)


## Enemy fighters currently alive.
func fighter_count() -> int:
	return get_tree().get_nodes_in_group("enemies") \
		.filter(func(n: Node) -> bool: return not n.is_queued_for_deletion()).size()


## How many more fighters can be added without exceeding max_fighters.
func fighter_room() -> int:
	return maxi(max_fighters - fighter_count(), 0)


## Count this enemy towards ending the wave.
func track(enemy: Node) -> void:
	enemy.destroyed.connect(_on_enemy_destroyed)


func _schedule_wave(delay: float) -> void:
	_wave_pending = true
	# A non-process-always timer, so it waits while the game is paused.
	await get_tree().create_timer(delay, false).timeout
	_wave_pending = false
	if is_inside_tree():
		_spawn_wave()


func _spawn_wave() -> void:
	var player := get_tree().get_first_node_in_group("player") as Node3D
	if player == null:
		return
	wave += 1
	var count := mini(mini(first_wave_size + (wave - 1) * wave_growth, max_wave_size), fighter_room())

	# Appear roughly ahead of the player, out of detection range and facing
	# random directions, so the player can find them before being found.
	var jitter := Vector3(randf_range(-1, 1), randf_range(-0.4, 0.4), randf_range(-1, 1)) * 0.7
	var direction := (-player.global_basis.z + jitter).normalized()
	var center := player.global_position + direction * spawn_distance
	var boundary := get_tree().get_first_node_in_group("boundary") as PlayBoundary
	if boundary:
		center = boundary.clamp_inside(center, spawn_boundary_margin)
	var terrain := get_tree().get_first_node_in_group("terrain") as Terrain
	if terrain:
		center.y = maxf(center.y, terrain.clearance_height(center.x, center.z) + spawn_altitude)
	var station := get_tree().get_first_node_in_group("station") as SpaceStation
	if station:
		center = station.push_clear(center, spawn_station_margin)
	var parent := get_parent()
	var squad := EnemySquad.new()
	for i in count:
		var enemy := enemy_scene.instantiate() as EnemyFighter
		enemy.position = center + Vector3(randf_range(-1, 1), randf_range(-1, 1), randf_range(-1, 1)) * 40.0
		if terrain:
			# Each one clear of the ground under it, which can rise within the group.
			enemy.position.y = maxf(enemy.position.y, terrain.clearance_height(enemy.position.x, enemy.position.z) + spawn_altitude * 0.5)
		enemy.rotation.y = randf() * TAU
		parent.add_child(enemy)
		enemy.patrol_center = center
		squad.add(enemy)
		track(enemy)

	if destroyer_every > 0 and wave % destroyer_every == 0 and not is_instance_valid(destroyer):
		_spawn_destroyer()


func _spawn_destroyer() -> void:
	var angle := randf() * TAU
	var direction := Vector3(cos(angle), randf_range(-0.08, 0.08), sin(angle)).normalized()
	destroyer = destroyer_scene.instantiate() as Destroyer
	destroyer.position = direction * zone_radius
	destroyer.spawner = self
	if destroyer.level_fighters:
		destroyer.fighter_scene = enemy_scene
	get_parent().add_child(destroyer)
	# Heading for the zone's centre, it would park in a station there: stop
	# short of the station on the side it came from instead.
	var destination := Vector3.ZERO
	var station := get_tree().get_first_node_in_group("station") as SpaceStation
	if station:
		var from_station := destroyer.position - station.global_position
		from_station.y = 0.0
		destination = station.global_position \
			+ from_station.normalized() * (station.bounding_radius() + destroyer_station_clearance)
	destroyer.arrive(destination)
	track(destroyer)
	get_tree().call_group("mission_control", "announce_destroyer", destroyer)


func _on_enemy_destroyed() -> void:
	# Wait a frame so the destroyed enemy has actually left the scene.
	await get_tree().process_frame
	if not is_inside_tree() or _wave_pending:
		return
	if fighter_count() == 0 and not is_instance_valid(destroyer):
		_schedule_wave(wave_delay)
