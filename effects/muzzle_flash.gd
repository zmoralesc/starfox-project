class_name MuzzleFlash
extends Node3D
## A brief flash at a gun muzzle when a bolt is fired. Bolts cover about 10 m
## per frame, so without it the eye never sees where a shot came from.
##
## Parented to the muzzle, so it rides along with the ship instead of being
## left behind in the ~1 m the ship moves each frame.

const DURATION := 0.07


static func spawn(muzzle: Node3D, color: Color, size := 1.0) -> void:
	var fx := MuzzleFlash.new()
	muzzle.add_child(fx)
	fx._play(color, size)


func _play(color: Color, size: float) -> void:
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	# Drawn over the ship's own hull: seen from the chase camera, the Arwing's
	# muzzles sit behind its upper fins. For 70 ms, showing through anything
	# else as well is harmless.
	material.albedo_color = color

	var mesh := SphereMesh.new()
	mesh.radius = 0.5
	mesh.height = 1.0
	mesh.radial_segments = 12
	mesh.rings = 6
	mesh.material = material

	# A blob stretched along the barrel, centred a little ahead of the muzzle.
	var flash := MeshInstance3D.new()
	flash.mesh = mesh
	flash.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	flash.scale = Vector3(1.0, 1.0, 2.5) * size
	flash.position = Vector3(0.0, 0.0, -0.6 * size)
	add_child(flash)

	# Lights up the nearby hull for an instant.
	var light := OmniLight3D.new()
	light.light_color = color
	light.light_energy = 3.0
	light.omni_range = 4.0 * size
	light.shadow_enabled = false
	add_child(light)

	var tween := create_tween().set_parallel()
	tween.tween_property(flash, "scale", flash.scale * 0.3, DURATION)
	tween.tween_property(material, "albedo_color:a", 0.0, DURATION)
	tween.tween_property(light, "light_energy", 0.0, DURATION)
	tween.chain().tween_callback(queue_free)
