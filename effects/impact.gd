class_name Impact
extends Node3D
## A short glowing flash used for laser hits and explosions.

const DURATION := 0.35


static func spawn(parent: Node, at: Vector3, color: Color, size := 1.0) -> void:
	var fx := Impact.new()
	parent.add_child(fx)
	fx.global_position = at
	fx._play(color, size)


func _play(color: Color, size: float) -> void:
	var material := StandardMaterial3D.new()
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.albedo_color = color
	material.emission_enabled = true
	material.emission = color
	material.emission_energy_multiplier = 8.0

	var mesh := SphereMesh.new()
	mesh.radius = 0.5
	mesh.height = 1.0
	mesh.radial_segments = 16
	mesh.rings = 8
	mesh.material = material

	var ball := MeshInstance3D.new()
	ball.mesh = mesh
	ball.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(ball)

	var light := OmniLight3D.new()
	light.light_color = color
	light.light_energy = 4.0
	light.omni_range = 6.0 * size
	add_child(light)

	ball.scale = Vector3.ONE * 0.2 * size
	var tween := create_tween().set_parallel()
	tween.tween_property(ball, "scale", Vector3.ONE * 2.0 * size, DURATION) \
		.set_trans(Tween.TRANS_EXPO).set_ease(Tween.EASE_OUT)
	tween.tween_property(material, "albedo_color:a", 0.0, DURATION)
	tween.tween_property(material, "emission_energy_multiplier", 0.0, DURATION)
	tween.tween_property(light, "light_energy", 0.0, DURATION)
	tween.chain().tween_callback(queue_free)
