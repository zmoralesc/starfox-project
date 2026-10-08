class_name EnemyFighter
extends AIPilot
## Hostile fighter with four behaviours:
##
## - PATROL: wanders around its patrol area, watching a forward view cone.
## - CHASE: has spotted its `quarry` (the player or a wingman); pursues and
##   attacks while it can see them.
## - EVADE: just got hit; jinks away from the fire for a moment.
## - SEEK: lost sight of its quarry; searches around where they were last
##   seen, then gives up and goes back to patrolling.
##
## It goes for the nearest ship it spots, a wingman counting as
## wingman_distance_penalty farther than it is (so the player usually wins),
## and only a wingman with room for another pursuer
## (Wingman.can_take_pursuer()). Shot by a wingman with room, it turns on that
## wingman at once instead of evading (retaliate_against_wingmen). A
## disengaged wingman is no target: anyone chasing it gives up.
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
## What's left after it's destroyed: its model keeps flying, smoking, then
## explodes again (Wreck). Empty = it just vanishes in the first explosion.
@export var wreck_scene: PackedScene = preload("res://effects/wreck.tscn")

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

@export_group("Targets")
## Choosing whom to chase, a wingman counts as this much farther away (m)
## than it is: the player is preferred unless a wingman is clearly nearer.
@export var wingman_distance_penalty := 100.0
## Shot by a wingman (with room for another pursuer and in sight): go after it
## at once instead of evading. Makes the wingmen who do the most shooting draw
## the most fire.
@export var retaliate_against_wingmen := true

var health := 0
var state := State.PATROL
## Where this fighter patrols around. Defaults to its spawn point.
var patrol_center := Vector3.ZERO
var last_known_position := Vector3.ZERO

## Who this fighter is after (the player or a wingman), or was last after.
## Only meaningful while CHASE; read by Wingman and WingCommand.
var quarry: Fighter
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
## Whoever shot us last (untyped: it may have been freed since).
var _last_attacker = null
## Who has hit us, and when (shooter -> _clock at their latest hit). Read
## through seconds_since_hit_by(); WingCommand uses it for teamwork kills.
var _hits_by := {}
## Seconds since we spawned, paused with the game.
var _clock := 0.0
## The mission's play boundary, if it has one.
var _boundary: PlayBoundary
## Flash, flinch and damage smoke when shot (the Model flashes and flinches;
## smoke comes out of `Model/SmokePoint`, the engine, if there is one).
var _reaction: HitReaction


func _ready() -> void:
	super()
	add_to_group("enemies")
	add_to_group("targets")
	add_to_group("obstacles")
	health = max_health
	var model := get_node_or_null("Model") as Node3D
	_reaction = HitReaction.attach(self, model, model, radius, false,
		get_node_or_null("Model/SmokePoint") as Node3D)
	patrol_center = global_position
	_boundary = get_tree().get_first_node_in_group("boundary") as PlayBoundary
	_break_side = -1.0 if randf() < 0.5 else 1.0
	_enter_state(State.PATROL)


func take_hit(damage: int, at: Vector3) -> void:
	if health <= 0:
		return  # already exploding; several bolts can land in one frame
	health -= damage
	if health > 0:
		_reaction.hit(at, float(health) / max_health)
		return
	# The model goes to the wreck: as it was, not mid-flash or mid-flinch.
	_reaction.release()
	Explosion.spawn(get_parent(), global_position, explosion, explosion_size, velocity)
	SoundFX.play_at(get_parent(), explosion_sound, global_position, 0.0, randf_range(0.9, 1.1))
	get_tree().call_group("hud", "add_score", 1)
	# The fighter still goes at once (everything tracking it sees it gone);
	# only its model lives on, as a wreck.
	var model := get_node_or_null("Model") as Node3D
	if wreck_scene and model:
		Wreck.spawn(wreck_scene, get_parent(), self, model, velocity, explosion_sound)
	destroyed.emit()
	queue_free()


## Launched from a destroyer hangar: fly straight out for `duration` seconds,
## passing through the hull, before the normal AI takes over.
func begin_launch(duration: float) -> void:
	_launch_time_left = duration
	collision_mask = 0
	speed = cruise_speed


func _think(delta: float) -> void:
	_clock += delta
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


## Told where `player` is (a destroyer's escort, when its thrusters are shot):
## chase them if they're within tracking range, otherwise go and look for
## them. Ignored while already chasing or still launching.
func alert(player: Ship) -> void:
	if player == null or player.is_dead or state == State.CHASE or _launch_time_left > 0.0:
		return
	quarry = player
	_remember_quarry()
	_enter_state(State.CHASE if _has_line_of_sight(chase_tracking_distance) else State.SEEK)


## Called by a laser that hit us, with whoever fired it (after notify_shot).
## A wingman who shot us gets chased at once, if we can (_can_retaliate()).
func notify_attacker(shooter: Node3D) -> void:
	_last_attacker = shooter
	_hits_by[shooter] = _clock
	if _launch_time_left > 0.0 or (state == State.CHASE and quarry == shooter):
		return
	if _can_retaliate():
		quarry = shooter as Fighter
		_remember_quarry()
		_evade_cooldown_left = evade_cooldown
		_enter_state(State.CHASE)


## Seconds since `shooter` last hit us (INF if it never has).
func seconds_since_hit_by(shooter: Node) -> float:
	return _clock - _hits_by[shooter] if _hits_by.has(shooter) else INF


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
			# Head for where our quarry was probably going.
			_search_center = last_known_position + _last_known_velocity * 2.0
			_roam_point = _search_center
			_roam_time = 0.0


func _decide(delta: float) -> Vector3:
	_state_time += delta
	_evade_cooldown_left -= delta
	_update_state(delta)

	match state:
		State.CHASE:
			return _attack_goal(quarry, _break_side)
		State.EVADE:
			return _evade_goal(delta)
		State.SEEK:
			return _roam_goal(delta, _search_center, search_radius, max_speed)
		_:
			return _roam_goal(delta, patrol_center, patrol_radius, cruise_speed * patrol_speed_factor)


func _update_state(delta: float) -> void:
	match state:
		State.PATROL:
			_chase_if_spotted(view_cone_deg, detection_distance)
		State.SEEK:
			if not _chase_if_spotted(seek_view_cone_deg, seek_detection_distance) \
					and _state_time > seek_duration:
				_enter_state(State.PATROL)
		State.CHASE:
			if not _quarry_valid():
				# Shot down, or a wingman who has disengaged: let them go.
				_enter_state(State.PATROL)
			elif _has_line_of_sight(chase_tracking_distance):
				_unseen_time = 0.0
				_remember_quarry()
			else:
				_unseen_time += delta
				if _unseen_time > lose_sight_time:
					_enter_state(State.SEEK)
		State.EVADE:
			if _state_time > evade_duration:
				_evade_cooldown_left = evade_cooldown
				# Look back towards the threat: a wingman who shot us, if we
				# can turn on them; otherwise the player if in clear view.
				var player := _player()
				if _can_retaliate():
					quarry = _last_attacker
				elif player and _sees(player, detection_distance):
					quarry = player
				else:
					_enter_state(State.SEEK)
					return
				_remember_quarry()
				_enter_state(State.CHASE)


## Starts a chase if anyone is in the given view cone (see _spot()). Returns
## whether it did.
func _chase_if_spotted(cone_deg: float, max_distance: float) -> bool:
	var seen := _spot(cone_deg, max_distance)
	if seen == null:
		return false
	quarry = seen
	_remember_quarry()
	_enter_state(State.CHASE)
	return true


## Who we can see in the given forward cone, nearest first: the player, or a
## wingman with room for another pursuer (counted wingman_distance_penalty
## farther than it is). Null if nobody.
func _spot(cone_deg: float, max_distance: float) -> Fighter:
	var best: Fighter = null
	var best_distance := INF
	var player := _player()
	if player and _can_spot(player, cone_deg, max_distance):
		best = player
		best_distance = global_position.distance_to(player.global_position)
	for node in get_tree().get_nodes_in_group("wingmen"):
		var wingman := node as Wingman
		if wingman == null or not wingman.can_take_pursuer(self):
			continue
		var distance := global_position.distance_to(wingman.global_position) + wingman_distance_penalty
		if distance < best_distance and _can_spot(wingman, cone_deg, max_distance):
			best = wingman
			best_distance = distance
	return best


## True if the last thing to shoot us was a wingman we can see and go after.
func _can_retaliate() -> bool:
	if not retaliate_against_wingmen or not is_instance_valid(_last_attacker):
		return false
	var wingman := _last_attacker as Wingman
	return wingman != null and wingman.can_take_pursuer(self) and _sees(wingman, detection_distance)


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


func _remember_quarry() -> void:
	last_known_position = quarry.global_position
	_last_known_velocity = quarry.velocity


## The player, unless they're dead (or there is none).
func _player() -> Ship:
	var player := get_tree().get_first_node_in_group("player") as Ship
	return player if player and not player.is_dead else null


## True while our quarry is still worth chasing: alive, and not a wingman who
## has disengaged.
func _quarry_valid() -> bool:
	if not is_instance_valid(quarry):
		return false
	if quarry is Ship:
		return not (quarry as Ship).is_dead
	if quarry is Wingman:
		return (quarry as Wingman).is_targetable()
	return true


## True if `ship` is inside the given forward cone, in range and not hidden.
func _can_spot(ship: Fighter, cone_deg: float, max_distance: float) -> bool:
	var to_ship := ship.global_position - global_position
	if (-global_basis.z).angle_to(to_ship) > deg_to_rad(cone_deg):
		return false
	return _sees(ship, max_distance)


## True if our quarry is within `max_distance` with no asteroid in between.
func _has_line_of_sight(max_distance: float) -> bool:
	return _quarry_valid() and _sees(quarry, max_distance)


## True if `ship` is within `max_distance` with no asteroid in between.
func _sees(ship: Fighter, max_distance: float) -> bool:
	var target_pos := ship.global_position
	if global_position.distance_to(target_pos) > max_distance:
		return false
	var query := PhysicsRayQueryParameters3D.create(global_position, target_pos, LAYER_WORLD)
	return get_world_3d().direct_space_state.intersect_ray(query).is_empty()
