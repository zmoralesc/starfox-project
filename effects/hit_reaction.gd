class_name HitReaction
extends Node
## How an enemy shows it's been hit (EnemyFighter, DestroyerPart): its model
## flashes red, flinches away from the shot and eases back, and as its health
## runs down it trails smoke, then smoke and fire. Its target calls hit() from
## take_hit() with the health it has left.
##
## Made in code by attach() (each target passes what to flash, what to flinch
## and its size); a scene can add a HitReaction child of its own to override the
## values here. The smoke emitters live in the scene, not under the target: they
## follow it, and when it's freed they stop and their puffs fade out on their own.

@export_group("Flash")
## Colour the model's toon surfaces glow (toon_surface.gdshaderinc's
## `hit_flash`), fading out over `flash_time` seconds.
@export var flash_color := Color(1.0, 0.1, 0.06)
@export var flash_time := 0.12

@export_group("Flinch")
## How far (metres) the model is knocked away from the shot, and how far it
## twists (degrees), easing back over about `flinch_time` seconds.
@export var flinch_distance := 0.8
@export var flinch_angle := 6.0
@export var flinch_time := 0.25

@export_group("Damage smoke")
## With this fraction of its health left or less it trails smoke; with
## `fire_below` or less, fire too. Light fighters (3 hits): smoke after the
## first hit, fire after the second.
@export_range(0.0, 1.0) var smoke_below := 0.7
@export_range(0.0, 1.0) var fire_below := 0.4
## Colours of the puffs (the explosions', so it all matches).
@export var smoke_style: ExplosionStyle = preload("res://effects/explosions/fighter.tres")
## Full-grown puff size per metre of the target's radius, up to `max_puff_size`
## (so a destroyer's bridge doesn't get puffs as big as a hangar).
@export var puff_size_per_radius := 1.4
@export var max_puff_size := 36.0
## Smoke: puffs a second and how long each lasts.
@export var smoke_rate := 14.0
@export var smoke_lifetime := 1.6
## Fire: short-lived burning puffs on top of the smoke, licking off the target.
@export var fire_rate := 16.0
@export var fire_lifetime := 0.5
## Smoke and fire pour out of the target's smoke point (see `smoke_point`), or,
## if it has none, the spot the first damaging shot hit, outward from its
## middle, in a cone this wide (degrees from straight out; 180 = every way,
## which a flying fighter turns into a trail), drifting off at up to
## `smoke_drift` times the puff size a second.
@export_range(0.0, 180.0) var smoke_spread := 180.0
@export var smoke_drift := 0.25

@export_group("Anchored targets")
## For targets that don't fly (destroyer parts, see attach()): their smoke
## can't trail, so it pours straight out in a narrow plume, faster and longer,
## or the hull around them hides it.
@export_range(0.0, 180.0) var anchored_spread := 30.0
@export var anchored_drift := 0.9
## Their smoke and fire last this many times longer.
@export var anchored_lifetime_scale := 1.6

## Whether the target is anchored (see the Anchored targets group).
var anchored := false

## What flashes (every toon surface under it) and what flinches (null = none).
var flash_root: Node3D
var flinch_node: Node3D
## The target's size (metres); scales the smoke.
var radius := 3.0
## Where the smoke comes out, the same every time (e.g. a fighter's engine:
## its `Model/SmokePoint` marker), puffing out along its +Y. Null = from where
## the first damaging shot hit.
var smoke_point: Node3D

var _target: Node3D
var _meshes: Array[GeometryInstance3D] = []
var _flash := 0.0
var _flinch := 0.0
var _flinch_offset := Vector3.ZERO
var _flinch_axis := Vector3.UP
## The flinching node's own transform, while it's knocked out of it.
var _rest := Transform3D.IDENTITY
var _flinching := false
var _smoke: GPUParticles3D
var _fire: GPUParticles3D
## Where the smoke comes out, in the target's space (set by the hit that starts it).
var _anchor := Vector3.ZERO


## The HitReaction of `target` (its "HitReaction" child, added if it has none),
## set up to flash `flash_root`, flinch `flinch_node` (or nothing) and size its
## smoke for `target_radius`; `is_anchored` for targets that don't fly;
## `smoke_from` = its fixed smoke point (`smoke_point`), or null.
static func attach(target: Node3D, flash: Node3D, flinch: Node3D, target_radius: float,
		is_anchored := false, smoke_from: Node3D = null) -> HitReaction:
	var reaction := target.get_node_or_null("HitReaction") as HitReaction
	if reaction == null:
		reaction = HitReaction.new()
		reaction.name = "HitReaction"
		target.add_child(reaction)
	reaction._target = target
	reaction.flash_root = flash
	reaction.flinch_node = flinch
	reaction.radius = target_radius
	reaction.anchored = is_anchored
	reaction.smoke_point = smoke_from
	return reaction


## A shot landed at `at`; `health_left` is the fraction of its health left
## (0 = destroyed: no flash or flinch then, but the fire keeps burning).
func hit(at: Vector3, health_left: float) -> void:
	if health_left > 0.0:
		_start_flash()
		_start_flinch(at)
		_apply()  # now, not on the next physics step: the frame the hit shows
	_update_smoke(at, health_left)


## Puts the model back as it was (no flash, no flinch): call before handing
## the model to something else (EnemyFighter's wreck).
func release() -> void:
	_flash = 0.0
	_flinch = 0.0
	_apply()
	flash_root = null
	flinch_node = null


func _start_flash() -> void:
	if flash_root == null:
		return
	if _meshes.is_empty():
		_collect(flash_root)
	_flash = 1.0


func _start_flinch(at: Vector3) -> void:
	if flinch_node == null or flinch_distance <= 0.0:
		return
	if not _flinching:
		_rest = flinch_node.transform
		_flinching = true
	# Away from the shot, in the flinching node's parent's space.
	var away := (_target.global_position - at).normalized()
	if not away.is_normalized():
		away = -_target.global_basis.z
	var parent_basis := (flinch_node.get_parent() as Node3D).global_basis
	_flinch_offset = parent_basis.inverse() * away * flinch_distance
	_flinch_axis = away.cross(Vector3(randf() - 0.5, randf() - 0.5, randf() - 0.5)).normalized()
	if not _flinch_axis.is_normalized():
		_flinch_axis = Vector3.UP
	_flinch_axis = parent_basis.inverse() * _flinch_axis
	_flinch = 1.0


func _collect(node: Node) -> void:
	if node is GeometryInstance3D:
		_meshes.append(node)
	for child in node.get_children():
		_collect(child)


func _update_smoke(at: Vector3, health_left: float) -> void:
	if health_left > smoke_below:
		return
	if _smoke == null and _fire == null:
		# Not quite on the surface: a bolt's hit point can be on the hurtbox,
		# which is bigger than the model.
		_anchor = _target.to_local(at) * 0.8
	var puff := minf(radius * puff_size_per_radius, max_puff_size)
	var spread := anchored_spread if anchored else smoke_spread
	var drift := puff * (anchored_drift if anchored else smoke_drift)
	var life := anchored_lifetime_scale if anchored else 1.0
	if _smoke == null:
		_smoke = _add_emitter(Explosion.trail(smoke_style, smoke_rate, smoke_lifetime * life, puff * 0.3, puff,
			0.001, 0.4, radius * 0.08, drift, spread))
	if health_left <= fire_below and _fire == null:
		_fire = _add_emitter(Explosion.trail(smoke_style, fire_rate, fire_lifetime * life, puff * 0.25, puff * 0.6,
			0.6, 0.7, radius * 0.08, drift, spread))


func _add_emitter(emitter: GPUParticles3D) -> GPUParticles3D:
	get_tree().current_scene.add_child(emitter)
	_place(emitter)
	return emitter


## At the smoke point, or else at the anchor with its +Y (the way the puffs go
## out) pointing away from the target's middle.
func _place(emitter: GPUParticles3D) -> void:
	if is_instance_valid(smoke_point):
		emitter.global_transform = smoke_point.global_transform.orthonormalized()
		return
	var at := _target.to_global(_anchor)
	var out := (at - _target.global_position).normalized()
	if not out.is_normalized():
		out = Vector3.UP
	var side := out.cross(Vector3.UP if absf(out.y) < 0.99 else Vector3.RIGHT).normalized()
	emitter.global_transform = Transform3D(Basis(side, out, side.cross(out)), at)


func _physics_process(delta: float) -> void:
	# Smoke follows the target (physics, as it moves; GPU particles space the
	# puffs along the path in between).
	for emitter in [_smoke, _fire]:
		if emitter:
			_place(emitter)
	if _flash <= 0.0 and _flinch <= 0.0:
		return
	_flash = move_toward(_flash, 0.0, delta / maxf(flash_time, 0.01))
	_flinch = move_toward(_flinch, 0.0, delta / maxf(flinch_time, 0.01))
	_apply()


func _apply() -> void:
	var flash := Color(flash_color, _flash)
	for mesh in _meshes:
		if is_instance_valid(mesh):
			mesh.set_instance_shader_parameter("hit_flash", flash)
	if flinch_node and _flinching:
		# Snaps out, eases back.
		var k := _flinch * _flinch
		flinch_node.transform = Transform3D(
			_rest.basis.rotated(_flinch_axis, deg_to_rad(flinch_angle) * k).orthonormalized(),
			_rest.origin + _flinch_offset * k)
		_flinching = _flinch > 0.0


func _exit_tree() -> void:
	# The target is going: its smoke stops and thins out on its own.
	for emitter in [_smoke, _fire]:
		if emitter and is_instance_valid(emitter):
			var e := emitter as GPUParticles3D
			if not e.is_inside_tree():
				e.queue_free()  # the whole scene is going (quit, scene change)
				continue
			e.emitting = false
			e.get_tree().create_timer(e.lifetime, false).timeout.connect(e.queue_free)
	_smoke = null
	_fire = null
