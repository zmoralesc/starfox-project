class_name Wreck
extends Node3D
## What's left of a destroyed fighter: it keeps flying (and tumbling), dark and
## trailing smoke, until it hits something solid, gets shot, or `lifetime` runs
## out, then explodes a second time and disappears. Its smoke fades out on its own.
##
## The fighter itself is already gone (scored, `destroyed` emitted, freed) by
## the time the wreck flies; EnemyFighter.take_hit() hands over its Model and
## Hurtbox with spawn(). The wreck has no collision body and isn't in any
## group, so it can't damage or block anything, and the AI, radar and orders
## don't see it. Friendly bolts can hit its hurtbox (take_hit), which sets off
## the second explosion; enemy bolts can't (their mask leaves out hurtboxes).

## Size for aim assist and wingmen joining your fire (Fighter.radius_of).
@export var radius := 3.0
## The crosshair turns red over it, to show it can be shot.
@export var highlight_on_crosshair := true
## The Attack order (and Weapons Free) never pick it: it's already dead.
@export var attack_target := false

@export_group("Flight")
## Seconds before it explodes if it hasn't hit anything.
@export var lifetime := 3.0
## Out of control, it rolls about its nose-to-tail axis (only: spinning on
## every axis looked wrong for a ship), at a random rate in this range
## (radians per second), either way round.
@export var roll_rate := Vector2(1.5, 3.5)
## Downward acceleration on planet missions (where there is a `terrain`
## group), so wrecks fall and crash. Space has none. 0 = keep flying level.
@export var planet_gravity := 15.0
## What it crashes into: World (terrain, asteroids, station, destroyer hulls),
## Friendly and Enemy ships. Crashing deals no damage.
@export_flags_3d_physics var crash_mask := Fighter.LAYER_WORLD | Fighter.LAYER_FRIENDLY | Fighter.LAYER_ENEMY

@export_group("Smoke")
## Puffs per second along the trail.
@export var smoke_rate := 26.0
## Seconds each puff lasts, so also how long the plume hangs on after the wreck explodes.
@export var smoke_puff_lifetime := 2.5
## Puff size when it appears and when it's grown fully (metres).
@export var smoke_start_size := 3.0
@export var smoke_end_size := 11.0
## The puffs are the explosions' (explosion_puff.gdshader), with this style's
## fire and smoke colours, so trail and explosions match.
@export var smoke_style: ExplosionStyle = preload("res://effects/explosions/fighter.tres")
## Fraction of a puff's life it burns before it's all smoke: only the newest
## stretch of the trail, right behind the wreck, is on fire.
@export_range(0.01, 1.0) var smoke_burn := 0.12
## Fraction of a puff's life after which it starts breaking up.
@export_range(0.0, 1.0) var smoke_dissolve_from := 0.4

@export_group("Final explosion")
## Style and fireball radius (m) of the second explosion.
@export var explosion: ExplosionStyle = preload("res://effects/explosions/fighter.tres")
@export var explosion_size := 6.0

@export_group("Debris")
## How many smoking pieces (WreckDebris) the second explosion throws out
## (random in this range, inclusive).
@export var debris_count := Vector2i(3, 5)
## Their speed away from the blast, on top of the wreck's own (m/s, random in
## this range).
@export var debris_speed := Vector2(18.0, 35.0)
## Seconds each piece keeps flying before it burns out (random in this range).
@export var debris_lifetime := Vector2(1.0, 2.0)
## How fast they slow down (fraction of their speed lost per second, roughly).
@export var debris_drag := 0.8
## Piece size (metres across).
@export var debris_size := 0.7
## Their trails: a thinner, shorter-lived version of the wreck's plume.
@export var debris_smoke_rate := 30.0
@export var debris_smoke_lifetime := 1.2
@export var debris_smoke_start_size := 0.8
@export var debris_smoke_end_size := 3.5

## The fighters' running lights go out (material name, see FighterModel).
const LIGHTS_MATERIAL := "Fighter_Lights"
const DEAD_LIGHTS_COLOR := Color(0.06, 0.05, 0.05)

static var _dead_lights: ShaderMaterial

## Public for _lead_point() (wingmen joining your fire lead it like a ship).
var velocity := Vector3.ZERO
## True once it has exploded (read by the crosshair and Wingman.target_gone()).
var is_destroyed := false

var _roll := 0.0
var _age := 0.0
var _gravity := 0.0
var _sound: AudioStream
## A sibling, not a child: it follows the wreck while it flies and stays behind
## to fade when the wreck is freed.
var _smoke: GPUParticles3D
var _exclude: Array[RID] = []


## Turns `model` (a dying fighter's Model node) into a wreck flying at
## `start_velocity`, taking over the fighter's hurtbox (if it has one) so it's
## exactly as easy to hit. Both are moved out of `fighter`, so the fighter can
## be freed straight after. `sound` plays at the second explosion.
static func spawn(scene: PackedScene, parent: Node, fighter: CollisionObject3D, model: Node3D,
		start_velocity: Vector3, sound: AudioStream) -> void:
	var wreck := scene.instantiate() as Wreck
	parent.add_child(wreck)
	wreck.global_transform = model.global_transform
	model.reparent(wreck)
	var hurtbox := fighter.get_node_or_null("Hurtbox") as Hurtbox
	if hurtbox:
		hurtbox.reparent(wreck)
		hurtbox.target = wreck
	# The fighter's body stays in the physics world until it's freed: don't crash into it.
	wreck._exclude = [fighter.get_rid()]
	wreck._start(model, start_velocity, sound)


func _start(model: Node3D, start_velocity: Vector3, sound: AudioStream) -> void:
	velocity = start_velocity
	_sound = sound
	_roll = randf_range(roll_rate.x, roll_rate.y) * (1.0 if randf() < 0.5 else -1.0)
	if get_tree().get_first_node_in_group("terrain"):
		_gravity = planet_gravity
	# The engine is dead: no glow, no running lights.
	var glow := model.get_node_or_null("Glow") as Node3D
	if glow:
		glow.hide()
	_douse_lights(model)
	_smoke = _make_smoke(smoke_rate, smoke_puff_lifetime, smoke_start_size, smoke_end_size)
	get_parent().add_child(_smoke)
	_smoke.global_position = global_position
	_align_with_velocity()


## A friendly bolt hit it: blow it up now (any damage will do; no score, the
## kill already counted).
func take_hit(_damage: int, at: Vector3) -> void:
	if is_destroyed:
		return  # several bolts can land in one frame
	_explode(at)


func _physics_process(delta: float) -> void:
	_age += delta
	velocity += Vector3.DOWN * _gravity * delta
	var from := global_position
	var to := from + velocity * delta
	var query := PhysicsRayQueryParameters3D.create(from, to, crash_mask)
	# A ship flying at us can cover the ray's start between two frames; count
	# that as a hit too (the ray only spans our own movement).
	query.hit_from_inside = true
	query.exclude = _exclude
	var hit := get_world_3d().direct_space_state.intersect_ray(query)
	if not hit.is_empty():
		_explode(hit.position)
		return
	global_position = to
	_smoke.global_position = to
	_align_with_velocity()
	# Local Z runs along the fighter (the wreck took its model's transform).
	rotate_object_local(Vector3.BACK, _roll * delta)
	if _age >= lifetime:
		_explode(global_position)


## Aligns the wreck's nose (-basis.z) with its flight direction while preserving roll.
func _align_with_velocity() -> void:
	if velocity.length_squared() > 0.001:
		var heading := velocity.normalized()
		var current_forward := -global_basis.z
		if not current_forward.is_equal_approx(heading):
			var q := Quaternion(current_forward, heading)
			global_basis = (Basis(q) * global_basis).orthonormalized()


func _explode(at: Vector3) -> void:
	is_destroyed = true
	var parent := get_parent()
	Explosion.spawn(parent, at, explosion, explosion_size, velocity)
	if _sound:
		SoundFX.play_at(parent, _sound, at, 0.0, randf_range(0.8, 0.95))
	# The plume thins out on its own after the wreck is gone.
	_smoke.global_position = at
	_smoke.emitting = false
	get_tree().create_timer(smoke_puff_lifetime, false).timeout.connect(_smoke.queue_free)
	_throw_debris(at)
	queue_free()


## A few smoking pieces flying out of the blast, carried on with the wreck's
## velocity, so the kill lingers for a moment after the last explosion.
func _throw_debris(at: Vector3) -> void:
	var parent := get_parent()
	for i in randi_range(debris_count.x, debris_count.y):
		var out := Vector3(randf_range(-1, 1), randf_range(-1, 1), randf_range(-1, 1)).normalized()
		var smoke := _make_smoke(debris_smoke_rate, debris_smoke_lifetime,
			debris_smoke_start_size, debris_smoke_end_size)
		var piece := WreckDebris.spawn(parent, at, velocity + out * randf_range(debris_speed.x, debris_speed.y),
			debris_size, smoke, debris_smoke_lifetime)
		piece.lifetime = randf_range(debris_lifetime.x, debris_lifetime.y)
		piece.drag = debris_drag
		piece.gravity = _gravity


func _douse_lights(node: Node) -> void:
	if _dead_lights == null:
		_dead_lights = ShaderMaterial.new()
		_dead_lights.shader = ToonMaterial.SHADER
		_dead_lights.set_shader_parameter("albedo", DEAD_LIGHTS_COLOR)
	for child in node.get_children():
		if child is MeshInstance3D:
			var mesh := (child as MeshInstance3D).mesh
			for surface in mesh.get_surface_count():
				var source := mesh.surface_get_material(surface)
				if source and source.resource_name == LIGHTS_MATERIAL:
					(child as MeshInstance3D).set_surface_override_material(surface, _dead_lights)
		_douse_lights(child)


## The wreck's own plume, or a debris trail (see Explosion.trail()).
func _make_smoke(rate: float, puff_lifetime: float, start_size: float, end_size: float) -> GPUParticles3D:
	return Explosion.trail(smoke_style, rate, puff_lifetime, start_size, end_size, smoke_burn, smoke_dissolve_from)
