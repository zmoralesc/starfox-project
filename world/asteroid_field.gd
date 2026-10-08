class_name AsteroidField
extends Node3D
## Scatters a seeded field of asteroids round this node when the level loads:
## the same layout every run. Keeps the rocks out of the intro's fly-in lane
## (ships on autopilot don't dodge) and clear of the space station, if the
## level has one (`station` group).
##
## Builds itself in _ready(), before the level's own _ready() starts the
## intro, so a mission scene needs no script of its own for it.

@export var asteroid_count := 160
@export var field_radius := 900.0
## Vertical squash of the field (1 = round). Halve it when doubling
## field_radius to keep the field as thick as before.
@export var field_flatten := 0.5
## No asteroids spawn this close to the field's centre.
@export var safe_radius := 80.0
@export var field_seed := 1977

## The level's intro: its start point and camera spot set the lane kept clear.
## Null = no lane.
@export var intro: IntroCutscene
## Asteroids are kept this far from the intro fly-in path, so the formation
## (which flies itself during the intro) never hits one.
@export var intro_lane_radius := 60.0
## Asteroids are kept at least this far from the space station (its AI
## avoidance spheres), so there's room to fly between a rock and the station.
@export var station_clearance := 40.0

var _station: SpaceStation


func _ready() -> void:
	_station = get_tree().get_first_node_in_group("station") as SpaceStation
	# The station builds its avoidance spheres in its own _ready(), which runs
	# after this one if it comes later in the scene.
	if _station and not _station.is_node_ready():
		await _station.ready
		if not is_inside_tree():
			return
	_spawn_asteroids()


func _spawn_asteroids() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = field_seed
	for i in asteroid_count:
		var asteroid := Asteroid.new()
		asteroid.radius = lerpf(3.0, 28.0, pow(rng.randf(), 2.5))
		for attempt in 20:
			var dir := Vector3(rng.randfn(), rng.randfn() * field_flatten, rng.randfn()).normalized()
			var distance := maxf(field_radius * pow(rng.randf(), 1.0 / 3.0), safe_radius)
			asteroid.position = dir * distance
			var world_pos := to_global(asteroid.position)
			if not _blocks_intro(world_pos, asteroid.radius) \
					and not (_station and _station.overlaps(world_pos, asteroid.radius * 1.3, station_clearance)):
				break
		add_child(asteroid)


## True if a rock at world position `pos` would be in the intro's flight path
## or camera shot.
func _blocks_intro(pos: Vector3, radius: float) -> bool:
	if intro == null or intro.start_point == null or intro.camera_spot == null:
		return false
	var start: Transform3D = intro.start_point.global_transform
	var camera_spot: Vector3 = intro.camera_spot.global_position
	var forward := -start.basis.z
	# The lane runs from the start marker to well past the camera spot,
	# covering where the player takes control.
	var lane_length := (camera_spot - start.origin).dot(forward) + intro.handover_distance + 150.0
	var lane_end := start.origin + forward * lane_length
	var closest := Geometry3D.get_closest_point_to_segment(pos, start.origin, lane_end)
	var visual_radius := radius * 1.3
	return pos.distance_to(closest) < intro_lane_radius + visual_radius \
		or pos.distance_to(camera_spot) < 20.0 + visual_radius
