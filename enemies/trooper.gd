class_name Trooper
extends EnemyFighter
## Shogun Trooper: an armoured humanoid robot that hovers, turns on the spot,
## fires bursts from a cannon arm in any direction and lands to fight as a
## turret. Its weak point is the backpack.
##
## It keeps EnemyFighter's states (PATROL, CHASE, EVADE, SEEK: what the HUD,
## wingmen and orders read) and its senses, retaliation and squads, but not
## its flight: it never flies forward (speed stays 0) and all its movement is
## the hover velocity it returns from _velocity_offset(). On top of the state
## it has a `mode`, what its body is doing:
##
## - HOVER: holds a point, jittering round it (hover_jitter). In CHASE, a point
##   on a ring engage_distance from its quarry, on the side away from the
##   quarry's heading; on PATROL and SEEK, it drifts between roam points.
## - DASH: a long, fast hop of dash_distance every dash_interval in CHASE (the
##   "erratic" movement): sideways, up or down, and back in or out towards its
##   ring; sometimes it swerves partway (dash_swerve_chance) or goes straight
##   into another (dash_chain_chance). Also the dodge away from a shot (EVADE).
## - APPROACH, DESCEND, LANDED, TAKEOFF: on planet missions it sets down on a
##   flat, dry spot, on the ground or a rooftop (preferred), and fights from
##   there without dashing, until shot, out of sight, or landed_time is up.
##
## And, separately, a `weapon` phase: READY, WINDUP (a tell of windup_time),
## BURST (burst_count bolts). It fires while it hovers, dashes or stands, but
## from the wind-up to the last bolt it neither dodges shots nor changes target.
##
## Bolts that hit within weak_point_radius of Model/BackpackPoint do
## weak_point_multiplier times the damage.

enum Mode { HOVER, DASH, APPROACH, DESCEND, LANDED, TAKEOFF }
enum Weapon { READY, WINDUP, BURST }

@export_group("Hover")
## How firmly it holds its hover point (spring stiffness, 1/s²; critically damped).
@export var hover_spring := 4.0
## Most acceleration the hover spring may use (m/s²).
@export var hover_acceleration := 60.0
## Top speed while holding or following a point (m/s). Below the player's
## cruise speed, so you can fly away from one.
@export var hover_max_speed := 40.0
## Top speed drifting on patrol or while searching.
@export var patrol_hover_speed := 14.0
## On planets, hover points are at least this high above the ground, water or buildings.
@export var hover_altitude := 30.0
## The ring it holds around its quarry (m, random in this range per chase or dash).
@export var engage_distance := Vector2(120.0, 220.0)
## How much it leans into its movement (degrees at dash_speed).
@export var lean_angle_deg := 18.0
## While chasing, the point it holds wanders this far (m) each way...
@export var hover_jitter := 7.0
## ...about this often (Hz, roughly; three uneven waves).
@export var hover_jitter_rate := 0.8

@export_group("Dash")
## Top dash speed (m/s); each dash peaks somewhere between dash_speed_min_factor
## and 1 times this.
@export var dash_speed := 90.0
@export_range(0.1, 1.0) var dash_speed_min_factor := 0.7
## Dash length (m, random in this range).
@export var dash_distance := Vector2(60.0, 110.0)
## Seconds between dashes while chasing (random in this range each time).
@export var dash_interval := Vector2(0.4, 1.6)
## After a dash, chance of going straight into another one in a new direction
## (after dash_chain_pause seconds).
@export_range(0.0, 1.0) var dash_chain_chance := 0.4
@export var dash_chain_pause := Vector2(0.05, 0.25)
## Chance a dash swerves off in a new direction partway, at a random point
## between 25% and 70% of the way.
@export_range(0.0, 1.0) var dash_swerve_chance := 0.35
@export var dash_acceleration := 260.0
@export var brake_deceleration := 200.0
## Shot outside a burst: chance of dashing away from the shooter at once.
@export_range(0.0, 1.0) var dodge_chance := 0.5
## Seconds after a dodge before it can dodge again.
@export var dodge_cooldown := 3.0

@export_group("Cannon")
@export var burst_count := 3
## Seconds between bursts (from the last bolt to the next wind-up).
@export var burst_cooldown := 2.5
## The tell before a burst: the cannon glows and comes up.
@export var windup_time := 0.4
## How far the chest and arm can turn to aim: degrees either side of the body's
## facing, and down / up from level.
@export var aim_yaw_limit_deg := 70.0
@export var aim_pitch_limits_deg := Vector2(-60.0, 85.0)

@export_group("Weak point")
## Hits this close to Model/BackpackPoint (m) count as backpack hits.
@export var weak_point_radius := 2.2
@export var weak_point_multiplier := 2

@export_group("Landing")
## Lands on planet missions (never where there is no terrain).
@export var can_land := true
## Seconds in CHASE before it looks for a landing spot (random in this range).
@export var land_interval := Vector2(10.0, 20.0)
## Seconds it stays landed unless shot or out of sight first (random in this range).
@export var landed_time := Vector2(6.0, 10.0)
## On patrol, chance of landing at each roam point reached.
@export_range(0.0, 1.0) var patrol_land_chance := 0.3
## Steepest surface it lands on, in degrees.
@export var max_land_slope_deg := 10.0
## Room the feet need: four more rays this far around the spot must hit within
## land_probe_tolerance of its height, which also keeps it off roof edges.
@export var land_probe_radius := 3.0
@export var land_probe_tolerance := 0.5
## Spots are sampled within this distance of it (m), land_samples of them.
@export var land_search_radius := 90.0
@export var land_samples := 8
## Last stretch above the spot, flown at descent_speed.
@export var approach_height := 6.0
@export var descent_speed := 8.0
## Crouch before lifting off; it can't dodge until airborne.
@export var takeoff_time := 0.5
@export var climb_speed := 15.0
## From its origin down to the soles of its feet (m).
@export var foot_height := 3.5

var mode := Mode.HOVER
var weapon := Weapon.READY

var _hover_velocity := Vector3.ZERO
var _hover_point := Vector3.ZERO
var _face_point := Vector3.ZERO
var _mode_time := 0.0
var _weapon_time := 0.0
## The ring point, relative to the quarry.
var _ring_direction := Vector3.FORWARD
var _ring_distance := 150.0
var _next_dash := 0.0
var _dash_target := Vector3.ZERO
var _dash_top_speed := 0.0
var _dash_timeout := 2.0
## When this dash swerves (seconds into it; negative = it doesn't).
var _swerve_at := -1.0
## Phases of the hover jitter's three waves, so troopers don't jitter in step.
var _jitter_phase := Vector3.ZERO
var _burst_ready_in := 0.0
var _shots_left := 0
var _dodge_cooldown_left := 0.0
var _land_timer := 0.0
var _landed_left := 0.0
## Where the soles go when landed, and the height it flies there at.
var _land_spot := Vector3.ZERO
var _travel_height := 0.0
var _grounded := false
var _scan_angle := 0.0
var _lean := Vector2.ZERO
## Optional glow at the muzzle, shown during the wind-up.
@onready var _charge := get_node_or_null("Model/Charge") as Node3D
@onready var _backpack_point := get_node_or_null("Model/BackpackPoint") as Node3D
## The animated model (Model/Trooper), if this scene has one. Its markers
## replace Model/MuzzleL, MuzzleR, BackpackPoint and SmokePoint, so they follow
## the chest and arm as it aims.
@onready var _body := get_node_or_null("Model/Trooper") as TrooperModel


func _ready() -> void:
	super()
	# Upright, facing where it was spawned facing: it only ever turns about
	# the vertical.
	var forward := -global_basis.z
	forward.y = 0.0
	if forward.length_squared() > 0.001:
		global_basis = Basis.looking_at(forward.normalized())
	_hover_point = global_position
	_face_point = global_position - global_basis.z * 100.0
	_burst_ready_in = randf_range(0.0, burst_cooldown)
	_jitter_phase = Vector3(randf(), randf(), randf()) * TAU
	if _body:
		_use_model_markers()
	if _charge:
		_charge.hide()


func _use_model_markers() -> void:
	var left := _body.marker(&"MuzzleTipL")
	var right := _body.marker(&"MuzzleTipR")
	if left and right:
		_cannons = [left, right]
		if _charge:
			_charge.reparent(left.get_parent(), false)
			_charge.position = (left.position + right.position) * 0.5 + Vector3(0.0, 0.0, -0.3)
	var backpack := _body.marker(&"BackpackPoint")
	if backpack:
		_backpack_point = backpack
	var smoke := _body.marker(&"SmokePoint")
	if smoke and _reaction:
		_reaction.smoke_point = smoke


func take_hit(damage: int, at: Vector3) -> void:
	if health <= 0:
		return
	if _backpack_point and at.distance_to(_backpack_point.global_position) <= weak_point_radius:
		damage *= weak_point_multiplier
	if health - damage <= 0:
		# The wreck takes its velocity: a hovering trooper barely moves, so give it
		# a shove back (and down, if airborne), away from the shot. A landed one
		# isn't pushed down, so its death clip plays out before it falls flat.
		var away := (global_position - at).normalized()
		away = Vector3(away.x, 0.0, away.z).normalized() * 8.0 if away.is_normalized() else Vector3.ZERO
		velocity += away + (Vector3.ZERO if _grounded else Vector3.DOWN * 6.0)
	super(damage, at)


func notify_shot(from: Vector3) -> void:
	_threat_origin = from
	if _locked():
		return
	if _grounded:
		_take_off()
	elif mode != Mode.DASH and _dodge_cooldown_left <= 0.0 and randf() < dodge_chance:
		_dodge(from)
		return
	if state != State.CHASE:
		# They know roughly where the fire came from.
		last_known_position = from
		_last_known_velocity = Vector3.ZERO
		_enter_state(State.SEEK)


func notify_attacker(shooter: Node3D) -> void:
	_last_attacker = shooter
	_hits_by[shooter] = _clock
	_call_for_help(shooter)
	# Mid-burst or mid-dodge it carries on; the dodge looks for them after.
	if _locked() or mode == Mode.DASH or (state == State.CHASE and quarry == shooter):
		return
	if _can_retaliate():
		quarry = shooter as Fighter
		_remember_quarry()
		_enter_state(State.CHASE)


## Hangar launches are for fighters: a trooper just starts hovering.
func begin_launch(_duration: float) -> void:
	pass


func _enter_state(new_state: State) -> void:
	super(new_state)
	match new_state:
		State.CHASE:
			_pick_ring()
			_next_dash = randf_range(dash_interval.x, dash_interval.y)
			_land_timer = randf_range(land_interval.x, land_interval.y)
	# A burst only carries on at the same quarry.
	if new_state != State.CHASE:
		_set_weapon(Weapon.READY)
	# The body carries on with a landing already under way, and a dash; an
	# approach to land starts over from hovering.
	if mode == Mode.APPROACH:
		_set_mode(Mode.HOVER)
	if new_state == State.SEEK and mode == Mode.LANDED:
		_take_off()  # searching means moving


#region Pilot interface

func _think(delta: float) -> void:
	_clock += delta
	_state_time += delta
	_mode_time += delta
	_weapon_time += delta
	_burst_ready_in -= delta
	_dodge_cooldown_left -= delta
	# What move_and_slide() left of last frame's velocity (it stops at walls).
	_hover_velocity = velocity
	_update_state(delta)
	_update_mode(delta)
	_update_weapon()
	_move(delta)
	_stick = _turn_stick(_face_point)


func _aim(_delta: float) -> void:
	_firing = weapon == Weapon.BURST and _quarry_valid()
	if weapon != Weapon.READY and _quarry_valid():
		aim_point = _lead_point(quarry)
		if aim_scatter > 0.0:
			aim_point += Vector3(randf_range(-1, 1), randf_range(-1, 1), randf_range(-1, 1)) * aim_scatter
	else:
		aim_point = global_position - global_basis.z * aim_distance


func _get_target_speed() -> float:
	return 0.0


func _velocity_offset() -> Vector3:
	return _hover_velocity


func _visual_turn_rates() -> Vector2:
	return Vector2.ZERO

#endregion


## No bumping off and slowing down like a fighter: the hover spring pulls it
## back to its point, and move_and_slide() already stopped it at the surface.
func _handle_collisions() -> void:
	pass


## Leans the model into its movement instead of banking.
func _update_model(delta: float) -> void:
	var local := global_basis.inverse() * _hover_velocity
	var k := deg_to_rad(lean_angle_deg) / maxf(dash_speed, 1.0)
	var target := Vector2(local.z * k, -local.x * k)
	_lean = _lean.lerp(target, 1.0 - exp(-6.0 * delta))
	_model.rotation.x = _lean.x
	_model.rotation.z = _lean.y
	if _charge:
		_charge.visible = weapon == Weapon.WINDUP
		if _charge.visible:
			_charge.scale = Vector3.ONE * clampf(_weapon_time / maxf(windup_time, 0.01), 0.2, 1.0)
	if _body:
		_body.aim(aim_point, weapon != Weapon.READY)
		_body.set_thrust(_thrust())


## Heel flame strength for the current mode (see TrooperModel.set_thrust()).
func _thrust() -> float:
	match mode:
		Mode.LANDED:
			return 0.0
		Mode.TAKEOFF:
			return 2.0 if _mode_time >= takeoff_time else 0.4
		Mode.DESCEND:
			return 0.7
		Mode.DASH:
			return 1.6
	return 1.0 + _hover_velocity.length() / maxf(hover_max_speed, 1.0)


func _fire() -> void:
	super()
	if _body:
		_body.recoil()
	_shots_left -= 1
	if _shots_left <= 0:
		_burst_ready_in = burst_cooldown
		_set_weapon(Weapon.READY)


## Starts a wind-up when a burst is ready, and the burst after it.
func _update_weapon() -> void:
	match weapon:
		Weapon.READY:
			if (mode == Mode.HOVER or mode == Mode.DASH or mode == Mode.LANDED) and _burst_ready():
				_set_weapon(Weapon.WINDUP)
		Weapon.WINDUP:
			if not _quarry_valid():
				_set_weapon(Weapon.READY)
			elif _weapon_time >= windup_time:
				_shots_left = burst_count
				_set_weapon(Weapon.BURST)
	if weapon != Weapon.READY:
		_face_quarry()


func _set_weapon(new_phase: Weapon) -> void:
	weapon = new_phase
	_weapon_time = 0.0


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
				_enter_state(State.PATROL)
			elif _has_line_of_sight(chase_tracking_distance):
				_unseen_time = 0.0
				_remember_quarry()
			else:
				_unseen_time += delta
				if _unseen_time > lose_sight_time:
					_enter_state(State.SEEK)
		State.EVADE:
			if mode == Mode.DASH:
				return
			# Dodged: look back for whoever shot us (as EnemyFighter does after
			# evading), else carry on with the one we were after.
			var player := _player()
			if _can_retaliate():
				quarry = _last_attacker
			elif not (_quarry_valid() and _sees(quarry, chase_tracking_distance)):
				if player and _sees(player, detection_distance):
					quarry = player
				else:
					_enter_state(State.SEEK)
					return
			_remember_quarry()
			_enter_state(State.CHASE)


## Picks the hover point and facing for this frame, and moves between modes.
func _update_mode(delta: float) -> void:
	match mode:
		Mode.HOVER:
			if state == State.CHASE and _quarry_valid():
				_chase_hover(delta)
			else:
				_roam_hover(delta)
		Mode.DASH:
			if _quarry_valid() and state == State.CHASE:
				_face_point = quarry.global_position
			var remaining := global_position.distance_to(_dash_target)
			if (remaining < 1.5 and _hover_velocity.length() < 6.0) or _mode_time > _dash_timeout:
				_end_dash()
			elif _swerve_at >= 0.0 and _mode_time >= _swerve_at:
				# Off in a new direction, without slowing down first.
				_swerve_at = -1.0
				_aim_dash(_dash_direction())
				if _body:
					_body.play(&"dash", true)
		Mode.APPROACH:
			if _flat_distance(_land_spot) > 4.0:
				_face_point = Vector3(_land_spot.x, global_position.y, _land_spot.z)
			var above := _land_spot + Vector3.UP * (foot_height + approach_height)
			if _flat_distance(_land_spot) > 1.5:
				_hover_point = Vector3(_land_spot.x, _travel_height, _land_spot.z)
			else:
				_hover_point = above  # straight down: the column above the spot is clear
				if global_position.y - above.y < 1.0:
					_set_mode(Mode.DESCEND)
			if _mode_time > 20.0:
				_set_mode(Mode.HOVER)  # couldn't get there
		Mode.DESCEND:
			if _mode_time > approach_height / maxf(descent_speed, 0.1) * 2.0 + 1.0:
				_set_mode(Mode.HOVER)  # something in the way
			elif global_position.y - foot_height <= _land_spot.y + 0.05:
				_grounded = true
				_landed_left = randf_range(landed_time.x, landed_time.y)
				_set_mode(Mode.LANDED)
		Mode.LANDED:
			_landed_left -= delta
			if state == State.CHASE and _quarry_valid():
				_face_quarry()
				var to := quarry.global_position - global_position
				var overhead := rad_to_deg(atan2(to.y, Vector2(to.x, to.z).length())) > aim_pitch_limits_deg.y
				if _landed_left <= 0.0 or overhead or to.length() > attack_range + 150.0 \
						or not _sees(quarry, chase_tracking_distance):
					_take_off()
			else:
				_scan_angle += delta * 0.6
				_face_point = global_position + Vector3(sin(_scan_angle), 0.0, cos(_scan_angle)) * 50.0
				if _landed_left <= 0.0:
					_take_off()
		Mode.TAKEOFF:
			if _mode_time >= takeoff_time:
				var floor_height := _terrain.clearance_height(global_position.x, global_position.z) \
					if _terrain else -INF
				if global_position.y >= floor_height + hover_altitude:
					_grounded = false
					_hover_point = global_position
					_set_mode(Mode.HOVER)


## Holding its ring around the quarry, jittering about it: dashes and
## (sometimes) lands.
func _chase_hover(delta: float) -> void:
	_face_point = quarry.global_position
	var t := _clock * TAU * hover_jitter_rate
	var jitter := Vector3(sin(t + _jitter_phase.x), 0.6 * sin(t * 1.37 + _jitter_phase.y),
		sin(t * 0.73 + _jitter_phase.z)) * hover_jitter
	_hover_point = _sanitize(quarry.global_position + _ring_direction * _ring_distance + jitter, hover_altitude)
	_next_dash -= delta
	if _next_dash <= 0.0:
		_start_dash(_dash_direction())
		return
	_land_timer -= delta
	if _land_timer <= 0.0:
		_land_timer = 3.0  # try again soon if there is nowhere to land
		if _find_landing_spot():
			_set_mode(Mode.APPROACH)


## Drifting between roam points on patrol, or round the search area; landing
## at some of them on patrol.
func _roam_hover(delta: float) -> void:
	_roam_time += delta
	var center := patrol_center if state == State.PATROL else _search_center
	var roam_radius := patrol_radius if state == State.PATROL else search_radius
	if global_position.distance_to(_roam_point) < 10.0 or _roam_time > 15.0:
		if state == State.PATROL and randf() < patrol_land_chance and _find_landing_spot():
			_set_mode(Mode.APPROACH)
			return
		_pick_roam_point(center, roam_radius)
	_hover_point = _roam_point
	if _flat_distance(_roam_point) > 5.0:
		_face_point = _roam_point


## Sets the hover velocity for this frame from the mode.
func _move(delta: float) -> void:
	match mode:
		Mode.DASH:
			var to := _dash_target - global_position
			var distance := to.length()
			var wanted := minf(_dash_top_speed, sqrt(2.0 * brake_deceleration * distance))
			var target := to / distance * wanted if distance > 0.01 else Vector3.ZERO
			var rate := dash_acceleration if target.length() > _hover_velocity.length() else brake_deceleration
			_hover_velocity = _hover_velocity.move_toward(target, rate * delta)
		Mode.LANDED:
			_hover_velocity = Vector3.ZERO
			global_position = _land_spot + Vector3.UP * (foot_height + 0.05)
		Mode.DESCEND:
			var gap := global_position.y - foot_height - _land_spot.y
			_hover_velocity = Vector3.DOWN * minf(descent_speed, maxf(gap, 0.0) / delta)
		Mode.TAKEOFF:
			_hover_velocity = Vector3.UP * climb_speed if _mode_time >= takeoff_time else Vector3.ZERO
		_:
			var top := hover_max_speed if state == State.CHASE or mode == Mode.APPROACH else patrol_hover_speed
			_spring(delta, top)


## Critically damped spring towards _hover_point.
func _spring(delta: float, top_speed: float) -> void:
	var accel := (_hover_point - global_position) * hover_spring - _hover_velocity * 2.0 * sqrt(hover_spring)
	_hover_velocity = (_hover_velocity + accel.limit_length(hover_acceleration) * delta).limit_length(top_speed)


## Stick that turns the body (yaw only) towards `point`.
func _turn_stick(point: Vector3) -> Vector2:
	var local := global_basis.inverse() * (point - global_position)
	if Vector2(local.x, local.z).length_squared() < 0.01:
		return Vector2.ZERO
	var error := atan2(local.x, -local.z)
	return Vector2(clampf(error * 3.0, -1.0, 1.0), 0.0)


func _face_quarry() -> void:
	if _quarry_valid():
		_face_point = quarry.global_position


## Wind-up, burst and take-off can't be interrupted by a dodge or a change of target.
func _locked() -> bool:
	return weapon != Weapon.READY or mode == Mode.TAKEOFF


## Ready to start a burst at the quarry: cooled down, in range and sight, and
## within reach of the arm.
func _burst_ready() -> bool:
	if _burst_ready_in > 0.0 or state != State.CHASE or not _quarry_valid():
		return false
	var target := quarry.global_position
	if global_position.distance_to(target) > attack_range or not _in_arc(target):
		return false
	return _sees(quarry, attack_range)


## True if the arm can point at `point` (aim_yaw_limit_deg, aim_pitch_limits_deg).
func _in_arc(point: Vector3) -> bool:
	var local := global_basis.inverse() * (point - global_position)
	var yaw := rad_to_deg(absf(atan2(local.x, -local.z)))
	var pitch := rad_to_deg(atan2(local.y, Vector2(local.x, local.z).length()))
	return yaw <= aim_yaw_limit_deg and pitch >= aim_pitch_limits_deg.x and pitch <= aim_pitch_limits_deg.y


func _set_mode(new_mode: Mode) -> void:
	var old := mode
	mode = new_mode
	_mode_time = 0.0
	if _body:
		_animate(old, new_mode)


## Starts the body clip for a change of mode (the upper body's aiming is set
## every frame in _update_model()).
func _animate(old: Mode, new_mode: Mode) -> void:
	match new_mode:
		Mode.DASH:
			_body.play(&"dash", true)
		Mode.HOVER, Mode.APPROACH:
			_body.play(&"brake" if old == Mode.DASH else &"hover_idle", old == Mode.DASH)
		Mode.DESCEND:
			_body.play(&"land", true)
		Mode.LANDED:
			if old != Mode.DESCEND:
				_body.play(&"landed_idle")
		Mode.TAKEOFF:
			_body.play(&"take_off", true)


## A new ring point round the quarry: behind it (away from its heading), give
## or take 60°, a little above or below.
func _pick_ring() -> void:
	if not _quarry_valid():
		return
	var back := quarry.global_basis.z
	back.y = 0.0
	back = back.normalized() if back.length_squared() > 0.01 else Vector3.BACK
	back = back.rotated(Vector3.UP, deg_to_rad(randf_range(-60.0, 60.0)))
	_ring_direction = (back + Vector3.UP * randf_range(-0.2, 0.4)).normalized()
	_ring_distance = randf_range(engage_distance.x, engage_distance.y)


## A random dash direction: mostly sideways, up or down. In or out depends on
## where it is: never towards the target while within the ring, back in
## towards it from beyond the ring, away from it inside the ring.
func _dash_direction() -> Vector3:
	var toward := -global_basis.z
	var distance := engage_distance.y
	if _quarry_valid():
		toward = global_position.direction_to(quarry.global_position)
		distance = global_position.distance_to(quarry.global_position)
	var side := toward.cross(Vector3.UP)
	side = side.normalized() if side.length_squared() > 0.01 else global_basis.x
	var radial := randf_range(-0.5, 0.0)
	if distance > engage_distance.y:
		radial = randf_range(0.3, 0.9)
	elif distance < engage_distance.x:
		radial = randf_range(-0.9, -0.3)
	var direction := side * (1.0 if randf() < 0.5 else -1.0) * randf_range(0.3, 1.0) \
		+ Vector3.UP * randf_range(-0.8, 0.8) + toward * radial
	if radial <= 0.0:
		var closing := direction.dot(toward)
		if closing > 0.0:
			direction -= toward * closing
	return direction.normalized() if direction.length_squared() > 0.01 else side


func _start_dash(direction: Vector3) -> void:
	_dash_top_speed = dash_speed * randf_range(dash_speed_min_factor, 1.0)
	var length := _aim_dash(direction)
	# Time to get there at its top speed and brake, with room to spare.
	_dash_timeout = length / maxf(_dash_top_speed, 1.0) * 1.6 + 0.6
	_swerve_at = _dash_timeout / 1.6 * randf_range(0.25, 0.7) if randf() < dash_swerve_chance else -1.0
	_set_mode(Mode.DASH)


## Sets the dash's end point, dash_distance along `direction`; returns its length.
func _aim_dash(direction: Vector3) -> float:
	var target := global_position + direction * randf_range(dash_distance.x, dash_distance.y)
	if _boundary:
		target = _boundary.clamp_inside(target, patrol_boundary_margin)
	_dash_target = _clear_of_obstacles(target)
	return global_position.distance_to(_dash_target)


## Dash away from a shot (EVADE until the dash ends).
func _dodge(from: Vector3) -> void:
	_dodge_cooldown_left = dodge_cooldown
	var away := from.direction_to(global_position)
	var side := away.cross(Vector3.UP)
	side = side.normalized() if side.length_squared() > 0.01 else global_basis.x
	var direction := (away * 0.5 + side * (1.0 if randf() < 0.5 else -1.0) + Vector3.UP * randf_range(-0.4, 0.4))
	_enter_state(State.EVADE)
	_start_dash(direction.normalized())


func _end_dash() -> void:
	_hover_point = global_position
	if state == State.CHASE and _quarry_valid():
		# Hold where the dash left us (on the ring), rather than spring back.
		var offset := global_position - quarry.global_position
		_ring_direction = offset.normalized()
		_ring_distance = clampf(offset.length(), engage_distance.x, engage_distance.y)
	if randf() < dash_chain_chance:
		_next_dash = randf_range(dash_chain_pause.x, dash_chain_pause.y)
	else:
		_next_dash = randf_range(dash_interval.x, dash_interval.y)
	_set_mode(Mode.HOVER)


func _take_off() -> void:
	if mode == Mode.TAKEOFF:
		return
	if not _grounded:
		_set_mode(Mode.HOVER)
		return
	_set_mode(Mode.TAKEOFF)


## `point` clear of obstacles, inside the boundary and `altitude` above the ground.
func _sanitize(point: Vector3, altitude: float) -> Vector3:
	if _boundary:
		point = _boundary.clamp_inside(point, patrol_boundary_margin)
	return _above_ground(_clear_of_obstacles(point), altitude)


func _flat_distance(point: Vector3) -> float:
	return Vector2(point.x - global_position.x, point.z - global_position.z).length()


#region Landing

## Looks for somewhere to land within land_search_radius: land_samples rays
## straight down, which hit the real surface (ground or a roof: the World layer
## holds the terrain and the map props' collision, where the terrain's
## per-cell clearance_height() can't tell where a roof is). A roof wins over
## the ground, then the nearest. Sets _land_spot and _travel_height; returns
## whether it found one.
func _find_landing_spot() -> bool:
	if not can_land or _terrain == null:
		return false
	var space := get_world_3d().direct_space_state
	var found := false
	var best_roof := false
	var best_distance := INF
	for i in land_samples:
		var angle := TAU * (i + randf()) / land_samples
		var point := global_position + Vector3(cos(angle), 0.0, sin(angle)) * randf_range(0.2, 1.0) * land_search_radius
		if _boundary and _boundary.clamp_inside(point, patrol_boundary_margin).distance_to(point) > 0.1:
			continue
		var ground := _terrain.height_at(point.x, point.z)
		if ground == -INF:
			continue
		# Flown to at this height, then straight down: high enough to clear
		# everything on the way there, and the ray down from it proves the
		# column above the spot is clear.
		var travel := maxf(global_position.y, _path_clearance(point) + foot_height + 4.0)
		var hit := _ray_down(space, point, travel + foot_height, ground - 2.0)
		if hit.is_empty() or not _flat_spot(space, hit, travel + foot_height, ground):
			continue
		var spot: Vector3 = hit.position
		var water := _terrain.water_level_at(spot.x, spot.z)
		if water != -INF and spot.y < water + 0.5:
			continue  # the sea, a lake or a river (frozen ones too)
		if _blocked_by_obstacle(spot + Vector3.UP * foot_height):
			continue
		var roof := spot.y > ground + 1.0
		var distance := global_position.distance_to(spot)
		if found and (best_roof and not roof or (roof == best_roof and distance >= best_distance)):
			continue
		found = true
		best_roof = roof
		best_distance = distance
		_land_spot = spot
		_travel_height = travel
	return found


## The highest clearance_height() between us and `point` (samples along the way).
func _path_clearance(point: Vector3) -> float:
	var highest := -INF
	for i in 7:
		var p := global_position.lerp(point, i / 6.0)
		highest = maxf(highest, _terrain.clearance_height(p.x, p.z))
	return highest


func _ray_down(space: PhysicsDirectSpaceState3D, point: Vector3, from_y: float, to_y: float) -> Dictionary:
	var query := PhysicsRayQueryParameters3D.create(Vector3(point.x, from_y, point.z),
		Vector3(point.x, to_y, point.z), LAYER_WORLD)
	query.exclude = [get_rid()]
	return space.intersect_ray(query)


## True if the surface `hit` is level enough and has room for both feet: four
## more rays land_probe_radius around it hit within land_probe_tolerance of it.
func _flat_spot(space: PhysicsDirectSpaceState3D, hit: Dictionary, from_y: float, ground: float) -> bool:
	var normal: Vector3 = hit.normal
	if rad_to_deg(normal.angle_to(Vector3.UP)) > max_land_slope_deg:
		return false
	var spot: Vector3 = hit.position
	for offset: Vector3 in [Vector3.RIGHT, Vector3.LEFT, Vector3.FORWARD, Vector3.BACK]:
		var probe := _ray_down(space, spot + offset * land_probe_radius, from_y, ground - 2.0)
		if probe.is_empty() or absf((probe.position as Vector3).y - spot.y) > land_probe_tolerance:
			return false
	return true


## True if `point` is inside an AI obstacle (a station sphere, a hull box...).
func _blocked_by_obstacle(point: Vector3) -> bool:
	for node in get_tree().get_nodes_in_group("obstacles"):
		if node == self or node is Fighter:
			continue
		var box := node as ObstacleBox
		if box:
			if box.contains(point, avoid_margin):
				return true
			continue
		var obstacle := node as Node3D
		if obstacle and point.distance_to(obstacle.global_position) < radius_of(obstacle) + avoid_margin:
			return true
	return false

#endregion
