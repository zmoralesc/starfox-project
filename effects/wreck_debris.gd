class_name WreckDebris
extends Node3D
## A smoking piece thrown out when a Wreck blows up: a small dark chunk that
## tumbles away, slowing down, trailing its own thin plume, then burns out
## (shrinks away) after a second or two. Its smoke stays behind and fades.
## Purely visual: no collision body, no groups, nothing can shoot it. Made by
## Wreck._throw_debris(), which also builds its smoke (Wreck._make_smoke()) so
## the trails match the wreck's.

## Dark grey toon chunk, shared by every piece.
const CHUNK_COLOR := Color(0.16, 0.15, 0.15)

static var _chunk_mesh: BoxMesh

var velocity := Vector3.ZERO
## Fraction of its speed it loses per second (exponential).
var drag := 0.8
## Downward acceleration (planets only; Wreck passes its own).
var gravity := 0.0
## Seconds it flies, the last `burn_out` of them shrinking away.
var lifetime := 1.5
var burn_out := 0.35
## What stops it: the World layer (terrain, asteroids, hulls).
var crash_mask := Fighter.LAYER_WORLD

var _spin := Vector3.ZERO
var _age := 0.0
var _size := 1.0
var _chunk: MeshInstance3D
## A sibling, like the wreck's: it stays behind to fade when the piece is gone.
var _smoke: GPUParticles3D
var _smoke_lifetime := 1.0


## A piece `size` metres across at `at`, flying at `start_velocity`, trailing
## `smoke` (added to `parent` here; its puffs last `smoke_lifetime` seconds).
static func spawn(parent: Node, at: Vector3, start_velocity: Vector3, size: float,
		smoke: GPUParticles3D, smoke_lifetime: float) -> WreckDebris:
	var piece := WreckDebris.new()
	piece.velocity = start_velocity
	piece._size = size
	piece._smoke = smoke
	piece._smoke_lifetime = smoke_lifetime
	parent.add_child(piece)
	piece.global_position = at
	parent.add_child(smoke)
	smoke.global_position = at
	return piece


func _ready() -> void:
	if _chunk_mesh == null:
		_chunk_mesh = BoxMesh.new()
		var material := ShaderMaterial.new()
		material.shader = ToonMaterial.SHADER
		material.set_shader_parameter("albedo", CHUNK_COLOR)
		_chunk_mesh.material = material
	_chunk = MeshInstance3D.new()
	_chunk.mesh = _chunk_mesh
	# Flat and uneven, like a torn-off panel.
	_chunk.scale = Vector3(randf_range(0.8, 1.2), randf_range(0.25, 0.45), randf_range(0.6, 1.0)) * _size
	_chunk.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_chunk)
	rotation = Vector3(randf(), randf(), randf()) * TAU
	# Loose pieces can tumble every which way (unlike the wreck, which rolls).
	_spin = Vector3(randf_range(-1, 1), randf_range(-1, 1), randf_range(-1, 1)) * 6.0


func _physics_process(delta: float) -> void:
	_age += delta
	velocity *= exp(-drag * delta)
	velocity += Vector3.DOWN * gravity * delta
	var from := global_position
	var to := from + velocity * delta
	var hit := get_world_3d().direct_space_state.intersect_ray(
		PhysicsRayQueryParameters3D.create(from, to, crash_mask))
	if not hit.is_empty():
		_finish(hit.position)
		return
	global_position = to
	_smoke.global_position = to
	rotate_x(_spin.x * delta)
	rotate_y(_spin.y * delta)
	rotate_z(_spin.z * delta)
	var left := lifetime - _age
	if left <= 0.0:
		_finish(to)
	elif left < burn_out:
		scale = Vector3.ONE * maxf(left / burn_out, 0.01)


## Gone: the trail stops where it ended and fades on its own.
func _finish(at: Vector3) -> void:
	_smoke.global_position = at
	_smoke.emitting = false
	var smoke := _smoke
	get_tree().create_timer(_smoke_lifetime, false).timeout.connect(smoke.queue_free)
	queue_free()
