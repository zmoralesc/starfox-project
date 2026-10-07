class_name AIPilot
extends Fighter
## Shared brain for AI-flown fighters: steering towards a point, dodging
## obstacles, leading moving targets and making attack runs.
##
## Subclasses override _decide() to choose a goal each frame, usually by
## calling _attack_goal() or returning a formation point.

enum AttackPhase { APPROACH, BREAK }

## Points checked along the flight path for ground (see _avoid_ground).
const GROUND_SAMPLES := 6
## Attacking a structure: directions tried around it for a pull-out point with
## a clear view (_viewpoint()), and how far short of it (beyond its radius) the
## line-of-sight check stops, so the surface it's mounted on doesn't count.
const VIEW_RING := 8
const VIEW_MARGIN := 3.0

@export_group("AI")
## How hard the AI yanks the stick towards its goal.
@export var steer_gain := 2.5
@export var attack_range := 450.0
## Fire when the nose is within this many degrees of the aim point
## (on top of the target's own angular size).
@export var fire_tolerance_deg := 1.5
## Break off a run on a static target when this close to its surface.
@export var break_distance := 50.0
## How far out to fly before turning in for another run.
@export var break_out_distance := 150.0
## How far behind an enemy fighter to sit while chasing it.
@export var pursuit_distance := 50.0
## Seconds of flight ahead to check for obstacles.
@export var avoid_lookahead_time := 1.5
@export var avoid_margin := 6.0
## Attacking a structure (a destroyer part): where our path runs into an
## ObstacleBox (its hull) within this distance (m, plus the target's radius) of
## the target, the box is what the target is mounted on and is ignored, so we
## can line up a shot. Farther along the path, the box still counts.
@export var mount_ignore_distance := 60.0
## Seconds spent steering away from a surface after scraping it.
@export var recover_duration := 0.8
## While engaging, also turn at the rate the target is moving across our view,
## so the nose stays on a turning target instead of trailing behind it. Makes
## the pilot a much better shot; enemy fighters leave it off.
@export var lead_turns := false
## Adds random noise to the aim point so the pilot's shots are less perfectly converged.
@export var aim_scatter := 0.0

@export_group("Ground")
## On planet missions, keep at least this high above the ground, water or
## buildings (Terrain.clearance_height()). Our flight path is checked ground_lookahead_time ahead; if it dips lower, we
## pull up. Goals are raised to this height too, except a target we are
## shooting at (the path check still stops us diving into the ground after it).
@export var ground_clearance := 25.0
## Seconds of flight ahead to check for ground.
@export var ground_lookahead_time := 2.0

var _stick := Vector2.ZERO
var _target_speed := 0.0
var _level_up := Vector3.UP
var _firing := false
## What we're shooting at this frame, if anything.
var _engage: Node3D
var _phase := AttackPhase.APPROACH
var _phase_time := 0.0
var _waypoint := Vector3.ZERO
var _waypoint_timeout := 4.0
var _recover_time := 0.0
var _recover_direction := Vector3.UP
## The mission's Terrain, if it has one (found through the "terrain" group).
var _terrain: Terrain
## Set while our flight path would come too close to the ground and we are
## pulling up.
var _ground_danger := false


func _ready() -> void:
	super()
	_target_speed = cruise_speed
	_terrain = get_tree().get_first_node_in_group("terrain") as Terrain


#region Pilot interface

func _think(delta: float) -> void:
	_phase_time += delta
	var goal := _avoid_ground(_avoid_obstacles(_decide(delta)))
	# Just scraped something: pull away from its surface for a moment
	# instead of grinding along it towards a goal on the other side.
	if get_slide_collision_count() > 0:
		var normal := Vector3.ZERO
		for i in get_slide_collision_count():
			normal += get_slide_collision(i).get_normal()
		# Still pulling away from an earlier hit: add that surface in. Wedged in
		# a corner (a wall and a ledge above), we then pull out between the two
		# instead of turning towards one, then the other, every frame, and
		# going nowhere.
		if _recover_time > 0.0:
			normal += _recover_direction
		_recover_direction = normal.normalized() if normal.length_squared() > 0.0001 else Vector3.UP
		_recover_time = recover_duration
	if _recover_time > 0.0:
		_recover_time -= delta
		_engage = null
		goal = global_position + (_recover_direction * 0.8 - global_basis.z * 0.2) * 100.0
	_stick = _steer_towards(goal)
	if lead_turns and is_instance_valid(_engage) and _recover_time <= 0.0:
		_stick = (_stick + _tracking_stick(_engage)).limit_length(1.0)


## Returns the world point to fly towards this frame. Also sets _target_speed,
## _engage and _level_up as needed. Default: cruise straight ahead.
func _decide(_delta: float) -> Vector3:
	_engage = null
	_level_up = Vector3.UP
	_target_speed = cruise_speed
	return global_position - global_basis.z * 100.0


func _aim(_delta: float) -> void:
	var forward := -global_basis.z
	if is_instance_valid(_engage):
		aim_point = _lead_point(_engage)
		var to_aim := aim_point - global_position
		var dist := to_aim.length()
		var tolerance := atan2(radius_of(_engage), dist) + deg_to_rad(fire_tolerance_deg)
		_firing = dist < attack_range and forward.angle_to(to_aim) < tolerance
		if aim_scatter > 0.0:
			aim_point += Vector3(randf_range(-1, 1), randf_range(-1, 1), randf_range(-1, 1)) * aim_scatter
	else:
		aim_point = global_position + forward * aim_distance
		_firing = _wants_idle_fire()


## Whether to fire straight ahead when there's nothing to engage.
func _wants_idle_fire() -> bool:
	return false


func _get_stick() -> Vector2:
	return _stick


func _get_target_speed() -> float:
	return _target_speed


func _wants_fire() -> bool:
	return _firing


func _get_level_up() -> Vector3:
	return _level_up

#endregion


## Restarts the attack pattern with a fresh approach.
func _begin_attack() -> void:
	_set_phase(AttackPhase.APPROACH)


## Flies to `point` (or for `timeout` seconds), then starts an attack run.
func _fly_to_then_attack(point: Vector3, timeout: float) -> void:
	_waypoint = point
	_waypoint_timeout = timeout
	_set_phase(AttackPhase.BREAK)


## Goal for attacking `target`. Fighters get chased from behind; anything else
## gets strafing runs. `side` (-1 or 1) is which way to break off.
func _attack_goal(target: Node3D, side: float) -> Vector3:
	_level_up = Vector3.UP
	if _phase == AttackPhase.BREAK:
		_engage = null
		_target_speed = max_speed
		if _phase_time < _waypoint_timeout and global_position.distance_to(_waypoint) >= 30.0:
			return _waypoint
		_set_phase(AttackPhase.APPROACH)

	var target_pos := target.global_position
	var dist := global_position.distance_to(target_pos)
	var r := radius_of(target)
	_engage = target

	var fighter := target as Fighter
	if fighter:
		# Sit behind it and match speed; break if we overshoot or meet head-on.
		# Only close the distance when roughly facing it - charging in while
		# it's off to the side just makes us orbit it at high speed.
		var facing := -global_basis.z.dot((target_pos - global_position).normalized())
		_target_speed = fighter.speed + (dist - pursuit_distance - _pursuit_offset()) * 0.8 * clampf(facing, 0.0, 1.0)
		if facing < 0.5:
			_target_speed = minf(_target_speed, cruise_speed)
		var head_on := global_basis.z.dot(fighter.global_basis.z) < -0.5
		if dist < r + 15.0 or (head_on and dist < 80.0):
			return _start_break(target_pos, r + break_out_distance * 0.6, side)
		return _lead_point(target)

	_target_speed = max_speed
	# A structure (a destroyer part) can be shot only from where it can be
	# seen: if the hull it's on is in the way, reposition rather than press on.
	var view_margin := r + VIEW_MARGIN
	if dist < r + break_distance or not _clear_view(global_position, target_pos, view_margin):
		return _start_break(target_pos, r + break_out_distance, side, view_margin)
	return _lead_point(target)


## Extra distance to hang back while chasing a fighter. Lets two pilots chasing
## the same target settle at different distances instead of in the same spot.
func _pursuit_offset() -> float:
	return 0.0


## Pulls out of an attack run on whatever is at `from`. With `view_margin` > 0
## (attacking a structure), the point we pull out to must have a clear view of
## it (see _viewpoint()), so the next run doesn't start behind the hull it's
## mounted on.
func _start_break(from: Vector3, distance: float, side: float, view_margin := 0.0) -> Vector3:
	# Pull out sideways and towards world up (not our own up, which may point
	# down if we're banked), so we climb away from whatever the target sits on.
	var away := (global_basis.x * side + Vector3.UP * 0.5 - global_basis.z * 0.5).normalized()
	var point := _clear_of_obstacles(from + away * distance)
	if view_margin > 0.0 and not _clear_view(point, from, view_margin):
		point = _viewpoint(from, distance, away, view_margin)
	_fly_to_then_attack(point, 4.0)
	_engage = null
	_target_speed = max_speed
	return _waypoint


## A point `distance` from `target_pos` that can see it (_clear_view()), in the
## direction closest to `preferred`: tried around a ring level with the target,
## a ring above it and straight above. Falls back to `preferred` if none can.
func _viewpoint(target_pos: Vector3, distance: float, preferred: Vector3, margin: float) -> Vector3:
	var best := _clear_of_obstacles(target_pos + preferred * distance)
	var best_dot := -INF
	var directions: Array[Vector3] = [Vector3.UP]
	for i in VIEW_RING:
		var flat := Vector3.FORWARD.rotated(Vector3.UP, TAU * i / VIEW_RING)
		directions.append(flat)
		directions.append((flat + Vector3.UP * 0.7).normalized())
	for dir in directions:
		var facing := dir.dot(preferred)
		if facing <= best_dot:
			continue
		var point := _clear_of_obstacles(target_pos + dir * distance)
		if _clear_view(point, target_pos, margin):
			best = point
			best_dot = facing
	return best


## True if nothing solid (World layer: terrain, asteroids, a destroyer's hull)
## lies between `from` and `target_pos`, stopping `margin` short of the target
## so the surface it's mounted on doesn't count.
func _clear_view(from: Vector3, target_pos: Vector3, margin: float) -> bool:
	var offset := from - target_pos
	if offset.length() <= margin:
		return true
	var to := target_pos + offset.normalized() * margin
	var query := PhysicsRayQueryParameters3D.create(from, to, Fighter.LAYER_WORLD)
	return get_world_3d().direct_space_state.intersect_ray(query).is_empty()


## Moves a waypoint out of any obstacle it ended up inside, and above the ground.
func _clear_of_obstacles(point: Vector3) -> Vector3:
	point = _above_ground(point, _ground_clearance())
	for node in get_tree().get_nodes_in_group("obstacles"):
		if node == self:
			continue
		var box := node as ObstacleBox
		if box:
			# Out through the nearest face, a little beyond the clearance.
			var out := box.way_out(point, box.margin + avoid_margin)
			if out != Vector3.ZERO:
				point += out + out.normalized() * 1.0
			continue
		var obstacle := node as Node3D
		var clearance := radius_of(obstacle) * 1.3 + avoid_margin
		var offset := point - obstacle.global_position
		if offset.length() < clearance:
			var push := offset.normalized() if offset.length() > 0.1 else Vector3.UP
			point = obstacle.global_position + push * clearance
	return point


func _set_phase(phase: AttackPhase) -> void:
	_phase = phase
	_phase_time = 0.0


## Converts a world-space goal into a virtual stick deflection.
func _steer_towards(goal: Vector3) -> Vector2:
	var local := global_basis.inverse() * (goal - global_position)
	if local.length_squared() < 0.01:
		return Vector2.ZERO
	local = local.normalized()
	var s := Vector2(local.x, -local.y)
	if local.z > 0.0:
		# Goal is behind us: turn as hard as possible.
		return s.normalized() if s.length() > 0.01 else Vector2.RIGHT
	return (s * steer_gain).limit_length(1.0)


## If an obstacle sits on our current flight path, replace the goal with a
## point that skirts around its nearest side.
func _avoid_obstacles(goal: Vector3) -> Vector3:
	var forward := -global_basis.z
	var look := maxf(speed * avoid_lookahead_time, 40.0)
	# While attacking, obstacles at or beyond the target don't matter: the attack
	# run breaks off before reaching it. Without this, whatever a target is
	# mounted on (e.g. a destroyer's bridge tower) keeps pushing us off our aim.
	if is_instance_valid(_engage):
		look = minf(look, global_position.distance_to(_engage.global_position) - radius_of(_engage))
	# Attacking a structure (a destroyer turret, say): an obstacle whose
	# clearance zone holds the target is what it's mounted on, so it doesn't
	# count either; avoiding it would keep us from ever lining up a shot (the
	# break-off takes us away). Not for fighters: a rock beside one still counts.
	var structure: Node3D = _engage if is_instance_valid(_engage) and not _engage is Fighter else null
	var nearest := INF
	var result := goal
	for node in get_tree().get_nodes_in_group("obstacles"):
		# A fighter we're chasing is handled by the pursuit logic instead.
		if node == self or (node == _engage and node is Fighter):
			continue
		var box := node as ObstacleBox
		if box:
			var grow := box.margin + avoid_margin
			if global_position.distance_to(box.global_position) > look + box.radius + grow:
				continue
			var entry_t := box.entry_distance(global_position, forward, minf(look, nearest), grow)
			if entry_t == INF or entry_t >= nearest:
				continue
			# (Nudged in, so the point counts as inside despite rounding.)
			var entry := global_position + forward * (entry_t + 0.01)
			# A box is often a whole hull, so it can't be skipped outright like a
			# sphere holding the target: only where our path meets it near the target.
			if structure and entry.distance_to(structure.global_position) < mount_ignore_distance + radius_of(structure):
				continue
			nearest = entry_t
			# Round its nearest side: out of the clearance zone sideways, plus half
			# the clearance again (as for spheres).
			var out := box.way_out(entry, grow, forward)
			if out == Vector3.ZERO:
				out = global_basis.y * grow
			result = entry + out + out.normalized() * grow * 0.5
			continue
		var obstacle := node as Node3D
		var rel := obstacle.global_position - global_position
		var t := rel.dot(forward)
		if t < 0.0 or t > look or t >= nearest:
			continue
		var clearance := radius_of(obstacle) * 1.3 + avoid_margin
		if structure and obstacle.global_position.distance_to(structure.global_position) < clearance:
			continue
		var miss := rel - forward * t  # from our path to the obstacle's centre
		if miss.length() >= clearance:
			continue
		nearest = t
		var push := -miss.normalized() if miss.length() > 0.1 else global_basis.y
		result = global_position + forward * t + push * clearance * 1.5
	return result


## On planet missions: raise the goal above the ground, and if our current
## flight path would come closer to the ground than _ground_clearance() within
## ground_lookahead_time, replace the goal with a climb. The path is followed as
## a straight line, which is cautious in a turn but never late.
func _avoid_ground(goal: Vector3) -> Vector3:
	_ground_danger = false
	if _terrain == null:
		return goal
	var clearance := _ground_clearance()
	if not is_instance_valid(_engage):
		goal = _above_ground(goal, clearance)
	var forward := -global_basis.z
	var look := maxf(speed, cruise_speed) * _ground_lookahead()
	var deficit := 0.0
	var probe := _ground_probe_direction()
	for i in GROUND_SAMPLES + 1:
		var p := global_position + probe * (look * i / GROUND_SAMPLES)
		deficit = maxf(deficit, _terrain.clearance_height(p.x, p.z) + clearance - p.y)
	if deficit <= 0.0:
		return goal
	_ground_danger = true
	# Climb: keep heading the same way over the ground, nose up, steeper the
	# deeper the path cuts into the safety margin.
	var flat := Vector3(forward.x, 0.0, forward.z)
	flat = flat.normalized() if flat.length_squared() > 0.01 else -global_basis.y.slide(Vector3.UP).normalized()
	return global_position + flat * look * 0.25 + Vector3.UP * (clearance + deficit)


## How high above the ground to stay right now, and how many seconds ahead to
## check. Wingmen in formation fly lower and look less far.
func _ground_clearance() -> float:
	return ground_clearance


func _ground_lookahead() -> float:
	return ground_lookahead_time


## Which way our flight path runs for the ground check: along the nose.
func _ground_probe_direction() -> Vector3:
	return -global_basis.z


## `point` raised to at least `clearance` above the ground, water or buildings below it.
## Unchanged where there is no terrain.
func _above_ground(point: Vector3, clearance: float) -> Vector3:
	if _terrain == null:
		return point
	point.y = maxf(point.y, _terrain.clearance_height(point.x, point.z) + clearance)
	return point


## Stick deflection that turns us at the rate the line of sight to `node` is
## rotating. Added on top of the normal steering, it removes the steady aiming
## error that steering alone leaves when following a turning target.
func _tracking_stick(node: Node3D) -> Vector2:
	var rel := node.global_position - global_position
	var dist_sq := rel.length_squared()
	var target_velocity = node.get("velocity")
	if dist_sq < 1.0 or not target_velocity is Vector3:
		return Vector2.ZERO
	var los_rate := global_basis.inverse() * (rel.cross(target_velocity - velocity) / dist_sq)
	# Inverse of Fighter's mapping: pitch rate = -stick.y * pitch_rate, yaw rate = -stick.x * yaw_rate.
	return Vector2(-los_rate.y / yaw_rate, -los_rate.x / pitch_rate)


## Where to aim so bolts meet a moving target.
func _lead_point(node: Node3D) -> Vector3:
	var pos := node.global_position
	var target_velocity = node.get("velocity")
	if not target_velocity is Vector3:
		return pos
	var travel_time := global_position.distance_to(pos) / (laser_speed + speed)
	return pos + target_velocity * travel_time
