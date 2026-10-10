class_name ShieldEffect
extends MeshInstance3D
## Bluish energy-shield bubble around a ship. Hidden until something calls
## flash(), collapse() or shimmer(); then its cells light and switch off
## (see effects/shield.gdshader: an impact disc, rings racing out, a crackle
## of cells). Uses the shader on a unit sphere scaled to fit the ship.

@export var hit_duration := 0.33
@export var collapse_duration := 1.2
@export var shimmer_duration := 0.9
## Seconds the whole bubble takes to dim out after each play (on top of the
## play's duration).
@export_range(0.0, 1.0, 0.01, "suffix:s") var fade_out := 0.25

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


## A shot absorbed at `world_point`: a disc pops there, rings race out and
## the cells round it light and go out.
func flash(world_point: Vector3, strength := 1.0) -> void:
	_play(strength, hit_duration, 0.0, 0.0)
	var local := global_transform.affine_inverse() * world_point
	_material.set_shader_parameter("hit_direction", local.normalized() if local.length() > 0.001 else Vector3.FORWARD)


## Shields knocked out: the whole bubble lights and its cells drop out.
func collapse() -> void:
	_play(0.9, collapse_duration, 1.0, 0.0)


## Shields back online: the cells light up over the whole bubble.
func shimmer() -> void:
	_play(0.6, shimmer_duration, 1.0, 1.0)


func _play(strength: float, duration: float, coverage: float, fill_in: float) -> void:
	_strength = strength
	_duration = duration
	_time = 0.0
	_material.set_shader_parameter("coverage", coverage)
	_material.set_shader_parameter("fill_in", fill_in)
	_apply(0.0)
	visible = true


func _process(delta: float) -> void:
	if not visible:
		return
	_time += delta
	if _time >= _duration + fade_out:
		visible = false
		return
	_apply(_time)


func _apply(time: float) -> void:
	# Full strength through the play (the cells go out one by one), then the
	# whole thing dims over `fade_out` seconds after it so it never cuts out.
	# The fade is in seconds, not a share of the play, so a short play still
	# gets a fade the eye can follow. Squared: a quick first drop, then a long
	# dim tail. The shapes keep moving through the fade (`ripple` past 1).
	var fade := clampf((time - _duration) / fade_out, 0.0, 1.0) if fade_out > 0.0 else 0.0
	_material.set_shader_parameter("intensity", _strength * pow(1.0 - fade, 2.0))
	_material.set_shader_parameter("ripple", time / _duration)
