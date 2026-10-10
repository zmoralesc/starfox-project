class_name MuzzleFlash
extends Node3D
## A brief flash at a gun muzzle when a bolt is fired. Bolts cover about 10 m
## per frame, so without it the eye never sees where a shot came from.
##
## Parented to the muzzle, so it rides along with the ship instead of being
## left behind in the ~1 m the ship moves each frame. Drawn by
## muzzle_flash.gdshader on a camera-facing quad (core, plume along the
## barrel, star of spikes), plus a small light on the hull.

const DURATION := 0.07
const SHADER := preload("res://effects/muzzle_flash.gdshader")

## Shared by every flash (built on first use): the colour and timing are
## per-instance shader uniforms.
static var _mesh: QuadMesh


static func spawn(muzzle: Node3D, color: Color, size := 1.0) -> void:
	var fx := MuzzleFlash.new()
	muzzle.add_child(fx)
	fx._play(color, size)


## Fires one microscopic flash in front of the camera, so its shader is
## compiled before the first real shot (see Explosion.prewarm()).
static func prewarm(parent: Node) -> void:
	var camera := parent.get_viewport().get_camera_3d()
	var anchor := Node3D.new()
	parent.add_child(anchor)
	if camera:
		anchor.global_position = camera.global_position - camera.global_basis.z * 3.0
	spawn(anchor, Color.WHITE, 0.001)
	anchor.get_tree().create_timer(DURATION * 2.0, false).timeout.connect(anchor.queue_free)


func _play(color: Color, size: float) -> void:
	if _mesh == null:
		var material := ShaderMaterial.new()
		material.shader = SHADER
		_mesh = QuadMesh.new()
		_mesh.material = material

	var flash := MeshInstance3D.new()
	flash.mesh = _mesh
	flash.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	# The vertex shader turns and grows the quad: never cull it.
	flash.extra_cull_margin = 10.0
	flash.scale = Vector3.ONE * size
	flash.set_instance_shader_parameter("color", color)
	flash.set_instance_shader_parameter("seed", randf() * 100.0)
	flash.set_instance_shader_parameter("age", 0.0)
	add_child(flash)

	# Lights up the nearby hull for an instant.
	var light := OmniLight3D.new()
	light.light_color = color
	light.light_energy = 3.0
	light.omni_range = 4.0 * size
	light.shadow_enabled = false
	add_child(light)

	var tween := create_tween().set_parallel()
	tween.tween_method(func(t: float) -> void: flash.set_instance_shader_parameter("age", t),
		0.0, 1.0, DURATION)
	tween.tween_property(light, "light_energy", 0.0, DURATION)
	tween.chain().tween_callback(queue_free)
