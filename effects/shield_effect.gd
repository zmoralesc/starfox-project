class_name ShieldEffect
extends MeshInstance3D
## Bluish energy-shield bubble around a ship. Hidden until something calls
## flash(), collapse() or shimmer(); then it glows and fades out.
## Uses effects/shield.gdshader on a unit sphere scaled to fit the ship.

@export var hit_duration := 0.6
@export var collapse_duration := 1.2
@export var shimmer_duration := 0.9

var _material: ShaderMaterial
var _time := 0.0
var _duration := 1.0
var _strength := 0.0


func _ready() -> void:
	# Per-instance copy: every ship built from ship.tscn shares the original.
	_material = (material_override as ShaderMaterial).duplicate()
	material_override = _material
	cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	visible = false


## A shot absorbed at `world_point`: bright spot plus a ripple spreading out.
func flash(world_point: Vector3, strength := 1.0) -> void:
	_play(strength, hit_duration, 0.0)
	var local := global_transform.affine_inverse() * world_point
	_material.set_shader_parameter("hit_direction", local.normalized() if local.length() > 0.001 else Vector3.FORWARD)


## Shields knocked out: the whole bubble flares and fades.
func collapse() -> void:
	_play(1.6, collapse_duration, 1.0)


## Shields back online: a soft shimmer over the whole bubble.
func shimmer() -> void:
	_play(0.7, shimmer_duration, 1.0)


func _play(strength: float, duration: float, coverage: float) -> void:
	_strength = strength
	_duration = duration
	_time = 0.0
	_material.set_shader_parameter("coverage", coverage)
	_apply(0.0)
	visible = true


func _process(delta: float) -> void:
	if not visible:
		return
	_time += delta
	var progress := _time / _duration
	if progress >= 1.0:
		visible = false
		return
	_apply(progress)


func _apply(progress: float) -> void:
	_material.set_shader_parameter("intensity", _strength * pow(1.0 - progress, 2.0))
	_material.set_shader_parameter("ripple", progress)
