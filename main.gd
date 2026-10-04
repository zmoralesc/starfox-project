extends Level
## The Asteroid Field mission: scatters the asteroid field. Everything else
## (intro, restart, spawner, mouse) is shared level logic in Level.

@export var asteroid_count := 160
@export var field_radius := 900.0
## No asteroids spawn this close to the starting position.
@export var safe_radius := 80.0
@export var field_seed := 1977

## Asteroids are kept this far from the intro fly-in path, so the formation
## (which flies itself during the intro) never hits one.
@export var intro_lane_radius := 60.0

@onready var _asteroids: Node3D = $Asteroids


func _build_world() -> void:
	_spawn_asteroids()


func _spawn_asteroids() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = field_seed
	for i in asteroid_count:
		var asteroid := Asteroid.new()
		asteroid.radius = lerpf(3.0, 28.0, pow(rng.randf(), 2.5))
		for attempt in 20:
			var dir := Vector3(rng.randfn(), rng.randfn() * 0.5, rng.randfn()).normalized()
			var distance := maxf(field_radius * pow(rng.randf(), 1.0 / 3.0), safe_radius)
			asteroid.position = dir * distance
			if not _blocks_intro(asteroid.position, asteroid.radius):
				break
		_asteroids.add_child(asteroid)


## True if a rock here would be in the intro's flight path or camera shot.
func _blocks_intro(pos: Vector3, radius: float) -> bool:
	var start: Transform3D = $IntroStart.global_transform
	var camera_spot: Vector3 = $IntroCameraSpot.global_position
	var forward := -start.basis.z
	# The lane runs from the start marker to well past the camera spot,
	# covering where the player takes control.
	var lane_length := (camera_spot - start.origin).dot(forward) + _intro.handover_distance + 150.0
	var lane_end := start.origin + forward * lane_length
	var closest := Geometry3D.get_closest_point_to_segment(pos, start.origin, lane_end)
	var visual_radius := radius * 1.3
	return pos.distance_to(closest) < intro_lane_radius + visual_radius \
		or pos.distance_to(camera_spot) < 20.0 + visual_radius
