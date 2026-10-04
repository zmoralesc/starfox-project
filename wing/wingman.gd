class_name Wingman
extends AIPilot
## AI wingman. Carries out the order WingCommand gives it:
## - Form Up: hold a formation slot and engage whatever the leader is shooting.
## - Attack: peel off and go after one target until it's destroyed, then
##   return to the standing order.
## - Cover Me: WingCommand sends it after enemies attacking the leader; between
##   threats it waits in formation.
## - Weapons Free: roam near the leader and attack enemy fighters found along
##   the way, preferring ones no other wingman is on. Never breaks off a
##   target, but heads back towards the leader between kills.
##
## `order` is what the player told it to do; `state` is what it's physically
## doing right now (flying in formation, or attacking something).

signal order_changed

enum State { FOLLOW, ATTACK }
enum Order { FORM_UP, ATTACK, COVER_ME, WEAPONS_FREE }
## Stages of the somersault rejoin: looping up and over, flying back past the
## leader, pulling through the rest of the loop, rolling upright if needed.
enum Stunt { NONE, PULL_UP, BACK, PULL_THROUGH, ROLL_OUT }

@export var leader: Ship
## Formation slot in the leader's local space (-Z is forward, +X is right).
@export var slot_offset := Vector3(-10.0, -1.5, 2.0)

@export_group("Role")
## Who flies this ship (name, colours, lines) is the Pilot resource in the
## `speaker` export (Comms group), one file per character in comms/speakers/.
## What's set here is this ship's place in the wing.
##
## Position in the wing (0, 1, 2...). Sets the HUD order and who yields to
## whom when several wingmen attack the same target.
@export var wing_index := 0
## Which way to break off attack runs: -1 left, 1 right, 0 straight up.
@export_range(-1.0, 1.0) var break_side := -1.0

@export_group("Formation")
## Steer towards a point this far ahead of the slot, for smooth corrections.
@export var formation_lookahead := 30.0
## Extra speed per unit the wingman is behind its slot.
@export var catch_up_gain := 1.5
## Joining from behind, close in no faster than lets us brake at this rate
## (m/s²) to match the leader's speed exactly at the slot, instead of arriving
## fast and stopping hard. Also caps formation flight's pull towards the slot.
## Lower = gentler arrival, slower join.
@export var arrival_deceleration := 30.0
## Closing on the slot this much faster (m/s) than arrival_deceleration could
## stop us in time: don't brake hard. Slow down at arrival_deceleration, sail
## past the slot and drift back into it (or turn back, if we end up far ahead).
@export var overshoot_margin := 5.0
## Ahead of the slot (along the leader's heading) and farther than this from
## it, too far for formation flight to pull us in: somersault back behind the
## slot and rejoin from there (see the Somersault group) instead of loitering
## ahead for the leader to catch up (which never happens if the leader flies
## as slowly as we can).
@export var rejoin_turn_distance := 70.0
## Behind the slot but facing away from the leader's heading: turn round
## towards a point this far out on the slot's side (above, for a centre slot),
## so the turn never swings across the leader's path.
@export var rejoin_turn_out := 60.0
## Joining from behind, come up this far out to the side of the slot (above
## it for a centre slot)...
@export var join_approach_offset := 12.0
## ...closing in sideways over the last this-many metres, so the approach
## never runs past the leader.
@export var rejoin_behind_distance := 40.0
## In formation, only turn towards the leader's target if it's within this cone.
@export var follow_fire_cone_deg := 15.0
## In formation, only fire with the leader when within this distance of the slot...
@export var formation_fire_distance := 10.0
## ...and pointing within this many degrees of the leader's heading.
@export var formation_fire_angle_deg := 20.0
## On planet missions the slot never goes lower than this above the ground or
## water (flying low pushes the slots below you up), and a wingman holding
## formation keeps only this much ground clearance instead of ground_clearance.
@export var formation_ground_clearance := 6.0
## Near the slot, check this many seconds of flight ahead for ground (instead
## of ground_lookahead_time). The slot is also raised over the ground this far
## ahead of it, so it starts climbing before a rise.
@export var formation_ground_lookahead := 1.0

@export_group("Somersault")
## Rejoining from far ahead (see rejoin_turn_distance), the wingman loops up
## and over like a Star Fox U-turn, flies back over the formation upside down
## and pulls through the second half of the loop to come out behind its slot,
## facing the leader's way. Facing away from the leader already, it turns
## back normally and pulls up through the second half (then rolls upright).
## The loops cheat: tighter and quicker than the ship could normally fly.
##
## Speed through the loops (m/s). Lower = a tighter loop.
@export var somersault_speed := 40.0
## Pitch rate (rad/s) at full stick while looping, instead of pitch_rate.
@export var somersault_pitch_rate := 3.0
## Speeding up and slowing down while somersaulting (m/s²), at least.
@export var somersault_acceleration := 60.0
## Time the pull through so we come out this far behind the slot.
@export var somersault_exit_behind := 20.0
## Flying back past the leader, keep at least this far off its flight line.
@export var somersault_pass_clearance := 20.0

@export_group("Cover me")
## On Cover Me, wait this much farther behind the leader than the normal slot
## (keeping its sideways and vertical offset), and don't fire with the leader.
## The trade: less firepower up front, but a covering wingman sits where
## enemies tailing the leader show up, ready to chase them off.
@export var cover_trail_distance := 35.0

@export_group("Formation flight")
## Near its slot, the wingman switches to formation flight: it turns and rolls
## with the leader almost instantly and moves with the slot, sliding or braking
## a little if needed, so the formation stays tight through hard turns and the
## leader never sweeps through a wingman. Turn off to fly like other AI ships.
@export var formation_flight := true
## Formation flight is fully on within this distance of the slot...
@export var assist_full_range := 25.0
## ...and fades out completely by this distance.
@export var assist_fade_range := 70.0
## How quickly formation flight engages or lets go (fraction per second), so
## joining the formation looks like a quick settle rather than a snap.
@export var assist_blend_speed := 2.5
## How tightly the heading follows the leader's (per second; higher = tighter).
@export var formation_turn_sharpness := 10.0
## Correction speed towards the slot per metre of error.
@export var slot_spring := 2.0
## Cap on the extra (sideways or braking) speed formation flight may add.
@export var max_slot_correction := 25.0
## How quickly the pull towards the slot may build up or change (m/s per
## second), so formation flight eases in rather than yanking the wingman.
@export var slot_pull_rate := 45.0
## When not shooting at something, point the nose this far (0..1) towards the
## direction of travel instead of straight at the follow goal. Hides most of
## the sideways slide while the formation swings through rolls and turns.
@export var velocity_heading_blend := 0.5

@export_group("Camera fade")
## Half-size of the box around the ship (local space) used to tell when the
## camera is inside or touching it. A little larger than the hull collision box
## so wingtips and engines count.
@export var camera_fade_extents := Vector3(3.4, 1.0, 3.6)
## Start fading when the camera is this close to that box...
@export var camera_fade_distance := 3.0
## ...down to this much transparency (0 = solid, 1 = invisible) once inside it.
@export_range(0.0, 1.0) var camera_fade_max := 0.8

@export_group("Shared target")
## When several wingmen chase the same fighter, each one after the first (by
## wing_index) sits this much farther back, so they don't settle into one spot.
@export var pursuit_stagger := 30.0
## If one still ends up closer than this to a lower-ranked wingman on the
## same target...
@export var crowd_distance := 10.0
## ...for this many seconds, it peels off and comes back in from another angle.
@export var crowd_time := 0.6

@export_group("Weapons free")
## On Weapons Free, try to stay within this distance of the leader: roam
## points are picked inside it, and a wingman outside it heads back. An
## engagement already under way is never broken off to come back, though.
@export var free_leash := 325.0
## Roam points are picked within this distance of the leader (mostly ahead).
@export var free_roam_radius := 208.0
## Pick a new roam point after this many seconds, or on reaching the old one.
@export var free_roam_time := 6.0
## Only pick up enemies this close to us...
@export var free_detect_range := 400.0
## ...and this close to the leader, so we don't wander off after far-away ones.
@export var free_engage_radius := 450.0
## After shooting down an enemy fighter, wait a random time in this range
## (seconds, min..max) before picking a new target, roaming meanwhile.
@export var free_kill_cooldown := Vector2(2.0, 3.5)

## What the player told this wingman to do.
var order := Order.FORM_UP
## The order to go back to when an Attack order's target is gone
## (Form Up, Cover Me or Weapons Free).
var standing_order := Order.FORM_UP
var state := State.FOLLOW
var target: Node3D

## Who flies this ship: the `speaker` export, when it's a Pilot (null for a
## plain CommsSpeaker or none).
var pilot: Pilot:
	get:
		return speaker as Pilot
## Name on the HUD and in order feedback: the speaker's name, or the node's.
var call_sign: String:
	get:
		return speaker.display_name if speaker else String(name)
## Accent panel colour, also this wingman's HUD colour (from the pilot).
var accent_color: Color:
	get:
		return pilot.accent_color if pilot else DEFAULT_ACCENT

var _crowded_for := 0.0
## Weapons Free: seconds left before looking for a new target after a kill.
var _free_cooldown := 0.0

## 0 = normal flight, 1 = full formation flight.
var _assist := 0.0
var _slot := Vector3.ZERO
var _slot_velocity := Vector3.ZERO
## Formation flight's pull towards the slot (on top of _slot_velocity). Its
## size is capped by _arrival_speed() and it changes no faster than
## slot_pull_rate, so the pull eases in rather than yanking.
var _slot_pull := Vector3.ZERO
## The leader's angular velocity (world space), from its rotation last frame.
var _leader_spin := Vector3.ZERO
var _prev_leader_basis := Basis.IDENTITY
var _tracking_started := false
## Where formation flight points the nose (the follow goal).
var _formation_goal := Vector3.ZERO
## Somersaulting back to rejoin the formation from behind (see the Somersault
## group), and for how long we've been in the current stage.
var _stunt := Stunt.NONE
var _stunt_time := 0.0
## Half rolling onto our back before the pull through (see _somersault_goal),
## and which way to roll for that or for rolling upright again.
var _rolling := false
var _roll_direction := 1.0
## Arrived too fast to stop at the slot gently: sailing past it while slowing
## down (see overshoot_margin).
var _overshooting := false
## Set while obstacle avoidance is steering us; formation flight lets go then.
var _avoiding := false
## Current camera fade (see _process) and the model meshes it applies to.
var _camera_fade := 0.0
var _fade_meshes: Array[MeshInstance3D] = []
## Weapons Free roaming: current roam point (in the leader's local space, so it
## stays near the leader as it flies) and time left before picking another.
var _roam_offset := Vector3.ZERO
var _roam_time_left := 0.0
## 0 = normal slot, 1 = trailing Cover Me slot (slides between them).
var _cover_amount := 0.0
## How fast the ship actually turned last frame (pitch, yaw in rad/s), stick
## and formation flight together. The model banks with this.
var _turn_rates := Vector2.ZERO

## Seconds to slide between the normal slot and the Cover Me slot.
const COVER_SLIDE_TIME := 1.5
## Formation flight fades in as our heading comes within acos(0.3) ≈ 73° of
## the leader's and is fully available within acos(0.8) ≈ 37°. Holding
## formation, the heading stays within about 20°.
const ASSIST_MIN_ALIGNMENT := 0.3
const ASSIST_FULL_ALIGNMENT := 0.8
## Accent colour when the speaker isn't a Pilot.
const DEFAULT_ACCENT := Color(0.95, 0.7, 0.15)


func _ready() -> void:
	super()
	add_to_group("wingmen")
	# Move after the leader so formation follows this frame's position.
	process_physics_priority = 5
	_paint_accent()
	_collect_meshes(_model)


## Fades the ship out when the camera is about to pass through it (mostly the
## trailing wingman, whose slot sits just behind the chase camera), so it
## never fills the screen with the inside of a hull.
func _process(_delta: float) -> void:
	var camera := get_viewport().get_camera_3d()
	var fade := 0.0
	if camera:
		var local := global_transform.affine_inverse() * camera.global_position
		var outside := (local.abs() - camera_fade_extents).max(Vector3.ZERO)
		fade = (1.0 - smoothstep(0.0, camera_fade_distance, outside.length())) * camera_fade_max
	if not is_equal_approx(fade, _camera_fade):
		_camera_fade = fade
		for mesh in _fade_meshes:
			mesh.transparency = fade


func _collect_meshes(node: Node) -> void:
	for child in node.get_children():
		if child is MeshInstance3D and child.name != "Shield":
			_fade_meshes.append(child)
		_collect_meshes(child)


#region Orders

## Order: attack `new_target`, then return to the standing order.
func assign_attack(new_target: Node3D) -> void:
	if not is_instance_valid(new_target):
		return
	order = Order.ATTACK
	command_attack(new_target)
	order_changed.emit()


## Order: fly in formation (and become the standing order).
func assign_form_up() -> void:
	order = Order.FORM_UP
	standing_order = Order.FORM_UP
	command_follow()
	order_changed.emit()


## Order: cover the leader (and become the standing order). WingCommand picks
## the threats to engage; until then the wingman waits in formation.
func assign_cover_me() -> void:
	order = Order.COVER_ME
	standing_order = Order.COVER_ME
	command_follow()
	order_changed.emit()


## Order: roam near the leader and attack enemies found along the way (and
## become the standing order).
func assign_weapons_free() -> void:
	order = Order.WEAPONS_FREE
	standing_order = Order.WEAPONS_FREE
	command_follow()
	_roam_time_left = 0.0
	order_changed.emit()


## Short label for the current order, for the HUD.
func order_label() -> String:
	match order:
		Order.ATTACK:
			return "ATTACK"
		Order.COVER_ME:
			return "COVER ME"
		Order.WEAPONS_FREE:
			return "WPNS FREE"
	return "FORM UP"


## True once a target no longer needs attacking: freed (fighters, rocks) or
## wrecked but still in the scene (destroyer parts).
static func target_gone(node) -> bool:  # untyped: may be a freed object
	return not is_instance_valid(node) or node.get("is_destroyed") == true


## Short HUD name for something a wingman can attack.
static func target_label(node: Node) -> String:
	if node is EnemyFighter:
		return "FIGHTER"
	if node is DestroyerPart:
		return (node as DestroyerPart).display_name
	if node is Asteroid:
		return "ASTEROID"
	return "TARGET"

#endregion


## Low-level: start an attack run on `new_target` (no change of order). Used
## by assign_attack and by Cover Me to send a covering wingman after a threat.
## `split`: peel off to the side first so wingmen sent together fan out. Cover
## Me skips it: the threat is usually behind, and the split flies the wrong way.
func command_attack(new_target: Node3D, split := true) -> void:
	if not is_instance_valid(new_target):
		return
	target = new_target
	state = State.ATTACK
	if not split:
		_begin_attack()
		return
	# Peel off towards our break side first so the wingmen come in from
	# different angles (straight up for the one with no side).
	var lift := 10.0 + 40.0 * (1.0 - absf(_side()))
	var split_point := global_position + global_basis.x * _side() * 70.0 \
		- global_basis.z * 40.0 + global_basis.y * lift
	_fly_to_then_attack(split_point, 1.5)


## Low-level: return to the formation slot (no change of order).
func command_follow() -> void:
	target = null
	state = State.FOLLOW


func _decide(delta: float) -> Vector3:
	_free_cooldown -= delta
	if leader == null:
		return super(delta)
	_track_leader(delta)
	if state == State.ATTACK and target_gone(target):
		command_follow()
		if order == Order.ATTACK:
			# Attack order done: back to what we were doing before it.
			order = standing_order
			order_changed.emit()
	if state == State.ATTACK:
		_stunt = Stunt.NONE
		_overshooting = false
		_check_crowding(delta)
		return _attack_goal(target, _side())
	if order == Order.WEAPONS_FREE:
		_stunt = Stunt.NONE
		_overshooting = false
		return _free_goal(delta)
	return _follow_goal()


#region Weapons free

## Weapons Free with no target: look for one, otherwise roam around the leader.
func _free_goal(delta: float) -> Vector3:
	var pick := _pick_free_target()
	if pick:
		command_attack(pick)
		return _attack_goal(target, _side())

	_engage = null
	_level_up = Vector3.UP
	if _too_far_from_leader():
		# Head back towards the leader (a little ahead of it), and pick a fresh
		# roam point once we're back in range.
		_roam_time_left = 0.0
		_target_speed = max_speed
		return leader.global_position - leader.global_basis.z * 60.0

	var roam_point := leader.global_transform * _roam_offset
	_roam_time_left -= delta
	if _roam_time_left <= 0.0 or global_position.distance_to(roam_point) < 40.0:
		_roam_offset = _new_roam_offset()
		_roam_time_left = free_roam_time
		roam_point = leader.global_transform * _roam_offset
	_target_speed = maxf(cruise_speed, leader.speed)
	return _steer_clear_of_leader(_clear_of_obstacles(roam_point))


## The leader isn't an obstacle for the AI, so a roam route can run straight
## through it. If the leader is on our path, aim beside it instead.
func _steer_clear_of_leader(goal: Vector3) -> Vector3:
	const CLEARANCE := 25.0
	var forward := -global_basis.z
	var rel := leader.global_position - global_position
	var ahead := rel.dot(forward)
	if ahead < 0.0 or ahead > global_position.distance_to(goal):
		return goal
	var miss := rel - forward * ahead
	if miss.length() >= CLEARANCE:
		return goal
	var push := -miss.normalized() if miss.length() > 0.1 else global_basis.y
	return global_position + forward * ahead + push * CLEARANCE * 1.5


## A random spot around the leader (its local space), mostly ahead of it so
## the player sees the wing at work, and never right on top of it.
func _new_roam_offset() -> Vector3:
	var r := free_roam_radius
	var offset := Vector3(randf_range(-1.0, 1.0) * r, randf_range(-0.35, 0.35) * r, randf_range(-1.0, 0.25) * r)
	if offset.length() < 60.0:
		offset = offset.normalized() * 60.0 if offset.length() > 0.1 else Vector3(0.0, 0.0, -60.0)
	return offset


func _too_far_from_leader() -> bool:
	return global_position.distance_to(leader.global_position) > free_leash


## The nearest enemy fighter we can see that's near the leader, preferring
## ones no other wingman is already attacking.
func _pick_free_target() -> Node3D:
	if _free_cooldown > 0.0:
		return null
	var best: Node3D
	var best_score := INF
	for node in get_tree().get_nodes_in_group("enemies"):
		var enemy := node as Node3D
		if enemy == null or target_gone(enemy) or enemy.is_queued_for_deletion():
			continue
		if enemy.global_position.distance_to(leader.global_position) > free_engage_radius:
			continue
		var distance := global_position.distance_to(enemy.global_position)
		if distance > free_detect_range:
			continue
		# Any untaken enemy beats any taken one; then the nearest wins.
		var score := distance + 10000.0 * _wingmen_attacking(enemy)
		if score < best_score:
			best = enemy
			best_score = score
	return best


## How many other wingmen are attacking `node` right now.
func _wingmen_attacking(node: Node3D) -> int:
	var count := 0
	for other: Wingman in get_tree().get_nodes_in_group("wingmen"):
		if other != self and other.state == State.ATTACK and other.target == node:
			count += 1
	return count

#endregion


#region Formation flight

## Follows the slot's motion and the leader's rotation, and decides how much
## formation flight applies this frame.
func _track_leader(delta: float) -> void:
	# Slide to or from the trailing Cover Me slot over a second or two, rather
	# than jumping (a jump would read as the slot moving at thousands of m/s).
	var cover_wanted := 1.0 if standing_order == Order.COVER_ME else 0.0
	_cover_amount = move_toward(_cover_amount, cover_wanted, delta / COVER_SLIDE_TIME)
	var slot := slot_position()
	var leader_basis := leader.global_basis
	if _tracking_started and delta > 0.0:
		_slot_velocity = (slot - _slot) / delta
		var turn := (leader_basis * _prev_leader_basis.inverse()).get_rotation_quaternion()
		var angle := turn.get_angle()
		_leader_spin = turn.get_axis() * (angle / delta) if angle > 0.0001 else Vector3.ZERO
	_slot = slot
	var error := _approach_point(slot) - global_position
	var wanted_pull := (error * slot_spring).limit_length(_arrival_speed(error.length()))
	if _assist <= 0.0:
		# Formation flight off: match the pull to how we're actually moving
		# relative to the slot, so engaging it changes nothing at first.
		_slot_pull = velocity - _slot_velocity
	_slot_pull = _slot_pull.move_toward(wanted_pull, slot_pull_rate * delta)
	_prev_leader_basis = leader_basis
	_tracking_started = true

	var wanted := 0.0
	if formation_flight and state == State.FOLLOW and order != Order.WEAPONS_FREE and not leader.is_dead:
		var distance := global_position.distance_to(slot)
		wanted = 1.0 - smoothstep(assist_full_range, assist_fade_range, distance)
		# Not while pointing the wrong way (still finishing a turn back towards
		# the formation): normal flight turns us round first, then formation
		# flight fades in as our nose comes round to the leader's heading.
		var alignment := (-global_basis.z).dot(-leader_basis.z)
		wanted *= smoothstep(ASSIST_MIN_ALIGNMENT, ASSIST_FULL_ALIGNMENT, alignment)
	# Dodging a rock, pulling off a surface or somersaulting to rejoin from
	# ahead: normal flight takes over at once, instead of formation flight
	# dragging us along the slot.
	# Given an order: let go at once, or the slot keeps tugging us back mid-peel.
	if state != State.FOLLOW:
		_assist = 0.0
	elif _avoiding or _recover_time > 0.0 or _stunt != Stunt.NONE or _overshooting:
		_assist = move_toward(_assist, 0.0, 4.0 * assist_blend_speed * delta)
	else:
		_assist = move_toward(_assist, wanted, assist_blend_speed * delta)


## Speed formation flight wants along our nose: keep pace with the slot,
## plus the spring towards it.
func _formation_velocity() -> Vector3:
	return _slot_velocity + _slot_pull


## Fastest we may close on a point `distance` away and still match the
## leader's speed there, braking at arrival_deceleration (v² = 2·a·d).
func _arrival_speed(distance: float) -> float:
	return sqrt(2.0 * arrival_deceleration * maxf(distance, 0.0))


## Formation flight: after the normal stick-driven turn, swing the heading
## towards the follow goal with the leader's roll, anticipating the leader's
## current turn so we don't trail it.
func _update_rotation(delta: float) -> void:
	var before := global_basis
	super(delta)
	_formation_turn(delta)
	# Formation flight turns the ship directly rather than through the stick,
	# so the model banks with how fast we actually turned (local pitch / yaw).
	if delta > 0.0:
		var turn := (before.inverse() * global_basis).get_euler()
		_turn_rates = Vector2(turn.x, turn.y) / delta


func _visual_turn_rates() -> Vector2:
	if leader == null or _assist <= 0.0:
		return _turn_rates
	# In formation, bank exactly as much as the leader for the same turn:
	# _update_model() scales by our own (higher) turn rates, so rescale to the
	# leader's. Blends back to our own scale as formation flight lets go.
	var rate_scale := Vector2(pitch_rate / leader.pitch_rate, yaw_rate / leader.yaw_rate)
	return _turn_rates * Vector2.ONE.lerp(rate_scale, _assist)


func _formation_turn(delta: float) -> void:
	if _assist <= 0.0 or leader == null:
		return
	var to_goal := _formation_goal - global_position
	var up := leader.global_basis.y
	if to_goal.length_squared() < 1.0 or absf(to_goal.normalized().dot(up)) > 0.98:
		return
	var direction := to_goal.normalized()
	var travel := _formation_velocity()
	if not is_instance_valid(_engage) and travel.length() > 1.0:
		direction = direction.lerp(travel.normalized(), velocity_heading_blend).normalized()
	if absf(direction.dot(up)) > 0.98:
		return
	var desired := Basis.looking_at(direction, up)
	var spin := _leader_spin.length()
	if spin > 0.0001:
		desired = Basis(_leader_spin / spin, spin / formation_turn_sharpness) * desired
	var weight := 1.0 - exp(-formation_turn_sharpness * _assist * delta)
	var blended := global_basis.get_rotation_quaternion().slerp(desired.get_rotation_quaternion(), weight)
	global_basis = Basis(blended).orthonormalized()


func _avoid_obstacles(goal: Vector3) -> Vector3:
	var result := super(goal)
	_avoiding = not result.is_equal_approx(goal)
	return result


func _velocity_offset() -> Vector3:
	if _assist <= 0.0:
		return Vector3.ZERO
	var offset := _formation_velocity() - (-global_basis.z * speed)
	return offset.limit_length(max_slot_correction) * _assist

#endregion


## The formation slot right now: the normal slot, or on Cover Me, the same slot
## cover_trail_distance farther back (sliding between the two).
func current_slot_offset() -> Vector3:
	return slot_offset + Vector3(0.0, 0.0, cover_trail_distance * _cover_amount)


## Where the formation slot is in the world right now: current_slot_offset()
## around the leader, raised to formation_ground_clearance over any terrain.
func slot_position() -> Vector3:
	var slot := leader.global_transform * current_slot_offset()
	if _terrain == null:
		return slot
	# Raise it over the ground under it and a little ahead of it, so the slot
	# (and the wingman, which moves with it) starts climbing before a rise.
	var ahead := slot + leader.velocity * formation_ground_lookahead
	var ground := maxf(_terrain.surface_height(slot.x, slot.z), _terrain.surface_height(ahead.x, ahead.z))
	slot.y = maxf(slot.y, ground + formation_ground_clearance)
	return slot


## Away from the leader on our slot's side: sideways for a side slot, up for a
## centre one.
func _outward() -> Vector3:
	return leader.global_basis.x * signf(slot_offset.x) if absf(slot_offset.x) > 0.5 else leader.global_basis.y


## Where to head for while joining from behind: beside the slot, out by
## join_approach_offset, closing in to the slot itself over the last
## rejoin_behind_distance. Keeps the approach out of the leader's path (a
## straight line to Slippy's slot, above and ahead, runs right past it). At or
## ahead of the slot, just the slot.
func _approach_point(slot: Vector3) -> Vector3:
	var behind := (slot - global_position).dot(-leader.global_basis.z)
	if behind <= 0.0:
		return slot
	return slot + _outward() * join_approach_offset * clampf(behind / rejoin_behind_distance, 0.0, 1.0)


func _ground_clearance() -> float:
	# Holding formation, the raised slot keeps us off the ground and we may
	# follow the leader down low; elsewhere, the normal safety margin.
	return formation_ground_clearance if _near_slot() else ground_clearance


func _ground_lookahead() -> float:
	# Near the slot we copy the leader's flight path, so only look ahead far
	# enough to catch real trouble. The full look-ahead would see every rise
	# the leader is about to climb over and pull us out of formation.
	return formation_ground_lookahead if _near_slot() else ground_lookahead_time


## Following the formation and close enough to the slot for formation flight
## (decided by distance, not by _assist: _assist drops while avoiding the
## ground, which would otherwise raise the clearance and keep us avoiding).
func _near_slot() -> bool:
	return state == State.FOLLOW and order != Order.WEAPONS_FREE and leader != null \
		and global_position.distance_to(_slot) < assist_fade_range


## True when holding the formation slot closely and facing the same way as
## the leader.
func is_in_formation() -> bool:
	if state != State.FOLLOW or leader == null or order == Order.WEAPONS_FREE:
		return false
	var slot := slot_position()
	if global_position.distance_to(slot) > formation_fire_distance:
		return false
	var heading_error := (-global_basis.z).angle_to(-leader.global_basis.z)
	return rad_to_deg(heading_error) <= formation_fire_angle_deg


## Wingmen fire along with the leader only on Form Up, and only from a proper
## formation position. Covering wingmen hold their fire for threats.
func _joins_leader_fire() -> bool:
	return order == Order.FORM_UP and is_in_formation()


func _wants_idle_fire() -> bool:
	# Leader is shooting at nothing in particular: fire along with them.
	return leader != null and leader.is_firing and _joins_leader_fire()


func _follow_goal() -> Vector3:
	var leader_basis := leader.global_basis
	var forward := -leader_basis.z
	var slot := slot_position()
	_level_up = leader_basis.y
	_engage = null

	var behind := (slot - global_position).dot(forward)
	_target_speed = leader.speed + behind * catch_up_gain
	if behind > 0.0:
		# Never faster than we can shed by the slot at arrival_deceleration.
		_target_speed = minf(_target_speed, leader.speed + _arrival_speed(behind))
	var goal := _approach_point(slot) + forward * formation_lookahead
	# Closing faster than we can stop at the slot gently: sail past it instead
	# of braking hard, until we're no faster than a gentle arrival allows (once
	# past the slot, that means slower than the leader, drifting back).
	var closing := (velocity - _slot_velocity).dot(forward)
	var distance := global_position.distance_to(slot)
	# Closing speed that brakes to a stop relative to the slot right at it,
	# from either side (negative = drifting back towards it from ahead).
	var wanted_closing := _arrival_speed(behind) if behind > 0.0 else -_arrival_speed(-behind)
	# Only when arriving: holding the slot, braking or turning hard can briefly
	# look like closing fast, and must not drop formation flight.
	if _stunt == Stunt.NONE and closing > maxf(wanted_closing, 0.0) + overshoot_margin \
			and distance > assist_full_range:
		_overshooting = true
	elif _overshooting:
		var on_profile := closing <= wanted_closing + 1.0
		var settled := distance < assist_full_range and closing <= 0.0
		# At min speed, ahead and not drifting back: the leader is too slow for
		# us to fall back to it this way; the normal logic waits or turns back.
		var stuck := behind < 0.0 and speed <= min_speed + 0.5 and closing > -1.0
		if (behind > 0.0 and on_profile) or settled or stuck:
			_overshooting = false
	# Far ahead of the slot: somersault back behind it, then the normal goal
	# brings us into the formation. Not while still sailing past at speed:
	# slow down first.
	if _stunt == Stunt.NONE and behind < -20.0 and distance > rejoin_turn_distance and not _overshooting:
		var facing := (-global_basis.z).dot(forward)
		_set_stunt(Stunt.PULL_UP if facing > ASSIST_MIN_ALIGNMENT else Stunt.BACK)
	if _overshooting:
		# Straight on in the slot's lane, never changing speed faster than
		# arrival_deceleration: past the slot and slow down, then drift back.
		goal = slot + forward * (maxf(-behind, 0.0) + formation_lookahead)
		_target_speed = move_toward(speed, _slot_velocity.dot(forward) + wanted_closing,
			arrival_deceleration * get_physics_process_delta_time())
	elif _stunt != Stunt.NONE:
		goal = _somersault_goal(behind)
	elif behind < -20.0:
		# Just ahead, within formation flight's reach: fly parallel in the
		# slot's lane and let the leader catch up rather than U-turn.
		goal = slot + forward * (-behind + 100.0)
	elif (-global_basis.z).dot(forward) < ASSIST_MIN_ALIGNMENT:
		# Behind the slot but facing away (just turned back to rejoin): turn
		# round on our slot's outer side. Turning the other way swings us
		# across the leader's path.
		goal = global_position + _outward() * rejoin_turn_out + forward * formation_lookahead


	# Help with the leader's target, but only from a proper formation position.
	var leader_target := leader.fire_target
	if is_instance_valid(leader_target) and _joins_leader_fire():
		var lead := _lead_point(leader_target)
		var to_target := lead - global_position
		if to_target.length() < attack_range \
				and rad_to_deg(forward.angle_to(to_target)) < follow_fire_cone_deg:
			_engage = leader_target
			goal = lead
	_formation_goal = goal
	if _assist > 0.0 and not _overshooting:
		_target_speed = lerpf(_target_speed, _formation_velocity().dot(-global_basis.z), _assist)
	return goal


#region Somersault

func _set_stunt(stunt: Stunt) -> void:
	_stunt = stunt
	_stunt_time = 0.0
	_rolling = false
	if stunt == Stunt.ROLL_OUT:
		_roll_direction = _continue_roll()


## Goal and speed for the current stage of the somersault rejoin. `behind`:
## how far the slot is ahead of us along the leader's heading.
func _somersault_goal(behind: float) -> Vector3:
	_stunt_time += get_physics_process_delta_time()
	var forward := -leader.global_basis.z
	var up := leader.global_basis.y
	var heading := (-global_basis.z).dot(forward)
	var upright := global_basis.y.dot(up) >= 0.0
	# A half loop takes this long; meanwhile the slot moves on by this much.
	var half_loop := PI / somersault_pitch_rate
	var slot_travel := leader.speed * half_loop
	# Over the top and heading back...
	if _stunt == Stunt.PULL_UP and ((heading < -0.7 and not upright) or _stunt_time > 2.0 * half_loop):
		_set_stunt(Stunt.BACK)
	# ...back far enough that the second half (which brings us down by one
	# loop's height while the slot moves on) comes out just behind the slot.
	# Straight away if it already would: one whole loop. Upside down only, so
	# the second half always pulls down out of the lane above the formation.
	# Also wait until we're most of the way up to the lane (see below): a short
	# trip back may not have climbed there yet, and pulling through too low
	# brings us out under the slot, then up past the leader.
	var loop_height := 2.0 * somersault_speed / somersault_pitch_rate
	var approach := slot_position() + _outward() * join_approach_offset
	var high_enough := (global_position - approach).dot(up) >= 0.75 * loop_height
	if _stunt == Stunt.BACK and heading < -0.7 and not upright \
			and behind + slot_travel >= somersault_exit_behind \
			and (high_enough or behind > somersault_exit_behind + rejoin_behind_distance):
		_set_stunt(Stunt.PULL_THROUGH)
	if _stunt == Stunt.PULL_THROUGH and (heading > 0.8 or _stunt_time > 2.0 * half_loop):
		_set_stunt(Stunt.ROLL_OUT if not upright else Stunt.NONE)
	if _stunt == Stunt.ROLL_OUT and (global_basis.y.dot(up) > 0.5 or _stunt_time > 2.5):
		_set_stunt(Stunt.NONE)

	# Keep whichever way up we are (upside down after the first half): wings
	# level, so the loops stay in the leader's vertical plane.
	_level_up = up if upright else -up
	_target_speed = somersault_speed
	var was_rolling := _rolling
	# Turned back the right way up (we were facing away to begin with): half
	# roll onto our back for the pull through, as in a split-S.
	_rolling = _stunt == Stunt.BACK and heading < -0.3 and global_basis.y.dot(up) > -0.5
	if _rolling and not was_rolling:
		_roll_direction = _continue_roll()
	match _stunt:
		Stunt.PULL_UP, Stunt.PULL_THROUGH:
			# Full stick back: towards our own canopy.
			return global_position + global_basis.y * 100.0
		Stunt.BACK:
			if heading < -0.7:
				# Fast down the formation, slowing to somersault_speed by the
				# pull through (we cover about speed / closing speed of the
				# remaining distance; the slot covers the rest).
				var remaining := maxf(somersault_exit_behind - slot_travel - behind, 0.0)
				var ground := remaining * speed / maxf(speed + leader.speed, 1.0)
				_target_speed = sqrt(somersault_speed * somersault_speed + 2.0 * somersault_acceleration * ground)
			# Parallel to the leader's flight line, in a lane one loop's height
			# (2·speed / pitch rate) above where the normal join starts (beside
			# the slot, see _approach_point), so the pull through drops us
			# right into it. At least somersault_pass_clearance off the
			# leader's line.
			var along := (global_position - leader.global_position).dot(forward)
			var lane := approach - leader.global_position
			lane = lane - forward * lane.dot(forward) + up * loop_height
			if lane.length() < somersault_pass_clearance:
				var away := lane.normalized() if lane.length() > 1.0 else _outward()
				lane = away * somersault_pass_clearance
			return leader.global_position + lane + forward * (along - 100.0)
		Stunt.ROLL_OUT:
			_target_speed = leader.speed
			return global_position + forward * 100.0
	# Done: carry on with the normal join from behind.
	return global_position + forward * 100.0


func _get_pitch_rate() -> float:
	if _stunt == Stunt.PULL_UP or _stunt == Stunt.PULL_THROUGH:
		return somersault_pitch_rate
	return pitch_rate


func _get_acceleration(fast: bool) -> float:
	var normal := super(fast)
	return maxf(normal, somersault_acceleration) if _stunt != Stunt.NONE else normal


func _get_roll() -> float:
	return _roll_direction if _rolling or _stunt == Stunt.ROLL_OUT else 0.0


## Roll direction (Fighter: positive rolls left) that keeps tilting us the way
## we already are, the shorter way to flip over.
func _continue_roll() -> float:
	var right_wing_up := global_basis.x.dot(leader.global_basis.y) > 0.0
	var upright := global_basis.y.dot(leader.global_basis.y) >= 0.0
	return 1.0 if right_wing_up == upright else -1.0

#endregion


## Other wingmen attacking the same target with a lower wing_index than ours.
## We give way to them: hang back farther, and peel off if we bunch up.
func _seniors_on_target() -> Array[Wingman]:
	var result: Array[Wingman] = []
	for node in get_tree().get_nodes_in_group("wingmen"):
		var other := node as Wingman
		if other and other != self and other.wing_index < wing_index \
				and other.state == State.ATTACK and other.target == target:
			result.append(other)
	return result


func _pursuit_offset() -> float:
	return pursuit_stagger * _seniors_on_target().size()


## Wingmen on one target tend to fly the same path. If we bunch up with one
## who outranks us, we break away to our side and start a fresh run.
func _check_crowding(delta: float) -> void:
	var crowded := false
	if _phase == AttackPhase.APPROACH:
		for other in _seniors_on_target():
			if global_position.distance_to(other.global_position) < crowd_distance:
				crowded = true
	if not crowded:
		_crowded_for = 0.0
		return
	_crowded_for += delta
	if _crowded_for >= crowd_time:
		_crowded_for = 0.0
		var away := (global_basis.x * _side() + Vector3.UP * 0.4 - global_basis.z * 0.6).normalized()
		_fly_to_then_attack(_clear_of_obstacles(global_position + away * 120.0), 2.5)


func _side() -> float:
	return break_side


## Paints this wingman's accent parts in its own colour (each ShipModel has
## its own accent material, so this doesn't recolour the other ships).
func _paint_accent() -> void:
	for child in _model.get_children():
		if child is ShipModel:
			(child as ShipModel).set_accent(accent_color)


## Called by a laser this wingman fired when it destroys `victim`. Only enemy
## fighters count: rocks and destroyer parts get no celebration or cooldown.
func notify_kill(victim: Node) -> void:
	if not victim is EnemyFighter:
		return
	if order == Order.WEAPONS_FREE:
		# Break off and roam for a moment before picking the next target.
		_free_cooldown = randf_range(free_kill_cooldown.x, free_kill_cooldown.y)
	if order == Order.FORM_UP or pilot == null or pilot.celebrations.is_empty() \
			or randf() > pilot.celebration_chance:
		return
	var comms := Comms.find(get_tree())
	if comms:
		comms.say(pilot, pilot.celebrations[randi() % pilot.celebrations.size()])


