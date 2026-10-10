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
## A destroyer flies level this high (its centre; its keel hangs about 60 m
## lower on the Juggernaut) above the highest ground, water or building it
## could pass over: anywhere within zone_radius + destroyer_ground_margin of
## the zone's centre. The same height whatever side it comes from.
@export var destroyer_altitude := 400.0
## How far past zone_radius that ground is checked: the portal and the
## hull's length behind its centre.
@export var destroyer_ground_margin := 600.0
## Spacing of the ground samples for that check, in metres.
@export var destroyer_ground_step := 50.0

## Current wave number (0 before the first wave). Read by the HUD.
var wave := 0
## The destroyer currently in play, if any.
var destroyer: Destroyer
## Off = due waves are held back until it's turned on again (set_waves_enabled();
## the developer console's `waves off`).
var waves_enabled := true

var _wave_pending := false
## True once start() has run: before that, enemies dying don't bring a wave.
var _started := false
## A wave came due while waves were off.
var _wave_held := false


func _ready() -> void:
	add_to_group("enemy_spawner")


## Begins the waves. Called by the level once the player has control.
func start() -> void:
	_started = true
	_schedule_wave(first_wave_delay)


## Turns the waves on or off. Turning them on sends a wave that came due
## meanwhile (after wave_delay).
func set_waves_enabled(on: bool) -> void:
	waves_enabled = on
	if on and _wave_held:
		_wave_held = false
		_schedule_wave(wave_delay)


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
	if not is_inside_tree():
		return
	if not waves_enabled:
		_wave_held = true
		return
	_spawn_wave()


## Sends the next wave now (and its destroyer, if it's a destroyer wave),
## whether or not the current one is over. Used by the developer console.
func spawn_wave_now() -> void:
	_spawn_wave()


func _spawn_wave() -> void:
	var player := get_tree().get_first_node_in_group("player") as Node3D
	if player == null:
		return
	wave += 1
	var count := mini(mini(first_wave_size + (wave - 1) * wave_growth, max_wave_size), fighter_room())
	spawn_squad(squad_center(), count)

	if destroyer_every > 0 and wave % destroyer_every == 0 and not is_instance_valid(destroyer):
		spawn_destroyer()


## Where a new group of fighters appears: roughly ahead of the player, out of
## detection range, inside the boundary, above the ground and clear of the
## station. Vector3.ZERO if there is no player.
func squad_center() -> Vector3:
	var player := get_tree().get_first_node_in_group("player") as Node3D
	if player == null:
		return Vector3.ZERO
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
	return center


## Spawns `count` fighters of `scene` (default: enemy_scene) as one squad
## around `center`, patrolling there and facing random directions, and tracks
## them towards ending the wave. Ignores max_fighters (waves apply it first).
func spawn_squad(center: Vector3, count: int, scene: PackedScene = null) -> Array[EnemyFighter]:
	if scene == null:
		scene = enemy_scene
	var spawned: Array[EnemyFighter] = []
	var terrain := get_tree().get_first_node_in_group("terrain") as Terrain
	var parent := get_parent()
	var squad := EnemySquad.new()
	for i in count:
		var enemy := scene.instantiate() as EnemyFighter
		enemy.position = center + Vector3(randf_range(-1, 1), randf_range(-1, 1), randf_range(-1, 1)) * 40.0
		if terrain:
			# Each one clear of the ground under it, which can rise within the group.
			enemy.position.y = maxf(enemy.position.y, terrain.clearance_height(enemy.position.x, enemy.position.z) + spawn_altitude * 0.5)
		enemy.rotation.y = randf() * TAU
		parent.add_child(enemy)
		enemy.patrol_center = center
		squad.add(enemy)
		track(enemy)
		spawned.append(enemy)
	return spawned


## Sends in a destroyer_scene (warping in at the zone's edge, announced by
## mission control), unless one is already in play. Returns it, or null.
func spawn_destroyer() -> Destroyer:
	if is_instance_valid(destroyer):
		return null
	var angle := randf() * TAU
	var direction := Vector3(cos(angle), randf_range(-0.08, 0.08), sin(angle)).normalized()
	destroyer = destroyer_scene.instantiate() as Destroyer
	destroyer.position = direction * zone_radius
	# It flies level from here, so on a planet it must start high enough to
	# clear everything (it would otherwise warp in at sea level).
	var terrain := get_tree().get_first_node_in_group("terrain") as Terrain
	if terrain:
		destroyer.position.y = _destroyer_height(terrain)
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
	destination.y = destroyer.position.y
	destroyer.arrive(destination)
	track(destroyer)
	get_tree().call_group("mission_control", "announce_destroyer", destroyer)
	return destroyer


## Height for a destroyer's centre: destroyer_altitude above the highest
## clearance (ground, water, buildings) in the disc it could fly over.
func _destroyer_height(terrain: Terrain) -> float:
	var reach := zone_radius + destroyer_ground_margin
	var step := maxf(destroyer_ground_step, 1.0)
	var highest := -INF
	var x := -reach
	while x <= reach:
		var z := -reach
		while z <= reach:
			if x * x + z * z <= reach * reach:
				highest = maxf(highest, terrain.clearance_height(x, z))
			z += step
		x += step
	return highest + destroyer_altitude


func _on_enemy_destroyed() -> void:
	# Wait a frame so the destroyed enemy has actually left the scene.
	await get_tree().process_frame
	if not is_inside_tree() or not _started or _wave_pending or _wave_held:
		return
	if fighter_count() == 0 and not is_instance_valid(destroyer):
		_schedule_wave(wave_delay)
