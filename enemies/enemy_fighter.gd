class_name EnemyFighter
extends AIPilot
## Hostile fighter with four behaviours:
##
## - PATROL: wanders around its patrol area, watching a forward view cone.
## - CHASE: has spotted the player; pursues and attacks while it can see them.
## - EVADE: just got hit; jinks away from the fire for a moment.
## - SEEK: lost sight of the player; searches around where they were last
##   seen, then gives up and goes back to patrolling.
##
## Asteroids block line of sight, so hiding behind rocks is a way to escape.

signal destroyed

enum State { PATROL, CHASE, EVADE, SEEK }

@export var max_health := 4
## Used for targeting, aim assist and obstacle avoidance.
@export var radius := 3.0
## The crosshair turns red over this fighter.
@export var highlight_on_crosshair := true
## The Attack order can pick this fighter.
@export var attack_target := true

@export_group("Senses")
## Half-angle (degrees) of the forward view cone used to spot the player on patrol.
@export var view_cone_deg := 45.0
@export var detection_distance := 400.0
## While searching they look harder: wider cone, a bit farther.
@export var seek_view_cone_deg := 60.0
@export var seek_detection_distance := 450.0
## Once chasing, they track the player within this range whenever nothing
## blocks the line of sight, even if the player is behind them.
@export var chase_tracking_distance := 700.0
## Seconds without line of sight before a chase turns into a search.
@export var lose_sight_time := 3.0
## How long to search before giving up and returning to patrol.
@export var seek_duration := 12.0

@export_group("Patrol")
@export var patrol_radius := 250.0
## Fraction of cruise speed used while patrolling.
@export var patrol_speed_factor := 0.8
## How far around the search point to look while seeking.
@export var search_radius := 150.0
## On planet missions, patrol and search points are at least this high above
## the ground, and at least this far inside the play boundary.
@export var patrol_min_altitude := 60.0
@export var patrol_boundary_margin := 150.0

@export_group("Evade")
@export var evade_duration := 2.5
## How often to change direction while evading.
@export var jink_interval := 0.6
## After evading, ignore new hits for this long so they get to fight back.
@export var evade_cooldown := 4.0

var health := 0
var state := State.PATROL
## Where this fighter patrols around. Defaults to its spawn point.
var patrol_center := Vector3.ZERO
var last_known_position := Vector3.ZERO

var _player: Ship
var _break_side := 1.0
var _state_time := 0.0
var _unseen_time := 0.0
var _evade_cooldown_left := 0.0
var _last_known_velocity := Vector3.ZERO
var _threat_origin := Vector3.ZERO
var _roam_point := Vector3.ZERO
var _roam_time := 0.0
var _search_center := Vector3.ZERO
var _jink_timer := 0.0
var _jink_direction := Vector3.ZERO
var _launch_time_left := 0.0
## The mission's play boundary, if it has one.
var _boundary: PlayBoundary


func _ready() -> void:
	super()
	add_to_group("enemies")
	add_to_group("targets")
	add_to_group("obstacles")
	health = max_health
	patrol_center = global_position
	_boundary = get_tree().get_first_node_in_group("boundary") as PlayBoundary
	_break_side = -1.0 if randf() < 0.5 else 1.0
	_enter_state(State.PATROL)


func take_hit(damage: int, _at: Vector3) -> void:
	if health <= 0:
		return  # already exploding; several bolts can land in one frame
	health -= damage
	if health > 0:
		return
	Impact.spawn(get_parent(), global_position, Color(1.0, 0.6, 0.25), 5.0)
	SoundFX.play_at(get_parent(), explosion_sound, global_position, 0.0, randf_range(0.9, 1.1))
	get_tree().call_group("hud", "add_score", 1)
	destroyed.emit()
	queue_free()


## Launched from a destroyer hangar: fly straight out for `duration` seconds,
## passing through the hull, before the normal AI takes over.
func begin_launch(duration: float) -> void:
	_launch_time_left = duration
	collision_mask = 0
	speed = cruise_speed


func _think(delta: float) -> void:
	if _launch_time_left > 0.0:
		_launch_time_left -= delta
		_stick = Vector2.ZERO
		_engage = null
		_target_speed = max_speed
		_level_up = Vector3.UP
		if _launch_time_left <= 0.0:
			collision_mask = LAYER_WORLD
		return
	super(delta)


## Called by a laser that hit us, with the point it was fired from.
func notify_shot(from: Vector3) -> void:
	_threat_origin = from
	if state != State.EVADE and _evade_cooldown_left <= 0.0:
		# They know roughly where the fire came from.
		last_known_position = from
		_last_known_velocity = Vector3.ZERO
		_enter_state(State.EVADE)


func _enter_state(new_state: State) -> void:
	state = new_state
	_state_time = 0.0
	match new_state:
		State.PATROL:
			_pick_roam_point(patrol_center, patrol_radius)
		State.CHASE:
			_unseen_time = 0.0
			_begin_attack()
		State.EVADE:
			_jink_timer = 0.0
		State.SEEK:
			# Head for where the player was probably going.
			_search_center = last_known_position + _last_known_velocity * 2.0
			_roam_point = _search_center
			_roam_time = 0.0


func _decide(delta: float) -> Vector3:
	_state_time += delta
	_evade_cooldown_left -= delta
	if not is_instance_valid(_player):
		_player = get_tree().get_first_node_in_group("player") as Ship
	_update_state(delta)

	match state:
		State.CHASE:
			return _attack_goal(_player, _break_side)
		State.EVADE:
			return _evade_goal(delta)
		State.SEEK:
			return _roam_goal(delta, _search_center, search_radius, max_speed)
		_:
			return _roam_goal(delta, patrol_center, patrol_radius, cruise_speed * patrol_speed_factor)


func _update_state(delta: float) -> void:
	match state:
		State.PATROL:
			if _can_spot(view_cone_deg, detection_distance):
				_enter_state(State.CHASE)
		State.SEEK:
			if _can_spot(seek_view_cone_deg, seek_detection_distance):
				_enter_state(State.CHASE)
			elif _state_time > seek_duration:
				_enter_state(State.PATROL)
		State.CHASE:
			if not _player_alive():
				_enter_state(State.PATROL)
			elif _has_line_of_sight(chase_tracking_distance):
				_unseen_time = 0.0
				_remember_player()
			else:
				_unseen_time += delta
				if _unseen_time > lose_sight_time:
					_enter_state(State.SEEK)
		State.EVADE:
			if _state_time > evade_duration:
				_evade_cooldown_left = evade_cooldown
				# Look back towards the threat: chase if the player is in clear view.
				if _has_line_of_sight(detection_distance):
					_remember_player()
					_enter_state(State.CHASE)
				else:
					_enter_state(State.SEEK)


## Wander between random points around `center`.
func _roam_goal(delta: float, center: Vector3, roam_radius: float, roam_speed: float) -> Vector3:
	_engage = null
	_level_up = Vector3.UP
	_target_speed = roam_speed
	_roam_time += delta
	if global_position.distance_to(_roam_point) < 40.0 or _roam_time > 15.0:
		_pick_roam_point(center, roam_radius)
	return _roam_point


func _pick_roam_point(center: Vector3, roam_radius: float) -> void:
	var offset := Vector3(randf_range(-1, 1), randf_range(-0.4, 0.4), randf_range(-1, 1))
	var point := center + offset.normalized() * randf_range(0.3, 1.0) * roam_radius
	if _boundary:
		point = _boundary.clamp_inside(point, patrol_boundary_margin)
	# Not inside a station or a big rock (_clear_of_obstacles also keeps it
	# above any ground, but at the AI's usual clearance, so lift it after).
	_roam_point = _above_ground(_clear_of_obstacles(point), patrol_min_altitude)
	_roam_time = 0.0


## Hard, randomly changing turns away from where the fire came from.
func _evade_goal(delta: float) -> Vector3:
	_engage = null
	_level_up = Vector3.UP
	_target_speed = boost_speed
	_jink_timer -= delta
	if _jink_timer <= 0.0:
		_jink_timer = jink_interval
		var away := _threat_origin.direction_to(global_position)
		var sideways := global_basis.x * (1.0 if randf() < 0.5 else -1.0) \
			+ global_basis.y * randf_range(-1.0, 1.0)
		_jink_direction = (away * 0.6 + sideways.normalized()).normalized()
	return global_position + _jink_direction * 100.0


func _remember_player() -> void:
	last_known_position = _player.global_position
	_last_known_velocity = _player.velocity


func _player_alive() -> bool:
	return is_instance_valid(_player) and not _player.is_dead


## True if the player is inside the given forward cone, in range and not hidden.
func _can_spot(cone_deg: float, max_distance: float) -> bool:
	if not _player_alive():
		return false
	var to_player := _player.global_position - global_position
	if (-global_basis.z).angle_to(to_player) > deg_to_rad(cone_deg):
		return false
	return _has_line_of_sight(max_distance)


## True if the player is within `max_distance` with no asteroid in between.
func _has_line_of_sight(max_distance: float) -> bool:
	if not _player_alive():
		return false
	var target_pos := _player.global_position
	if global_position.distance_to(target_pos) > max_distance:
		return false
	var query := PhysicsRayQueryParameters3D.create(global_position, target_pos, LAYER_WORLD)
	return get_world_3d().direct_space_state.intersect_ray(query).is_empty()
