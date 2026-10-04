class_name InkOutline
extends MeshInstance3D
## Screen-space ink outlines for the cel-shaded look. Add as a child of a
## Camera3D; it covers the screen with a quad running ink_outline.gdshader.

const SHADER := preload("res://effects/ink_outline.gdshader")


func _ready() -> void:
	var quad := QuadMesh.new()
	quad.size = Vector2(2.0, 2.0)
	mesh = quad
	var material := ShaderMaterial.new()
	material.shader = SHADER
	material_override = material
	cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	# The vertex shader places the quad in screen space; never cull it.
	extra_cull_margin = 16384.0
	# Draw before other transparent things, so lasers and explosions cover the lines.
	material.render_priority = -100
