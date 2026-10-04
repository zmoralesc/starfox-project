class_name ToonMaterial
extends RefCounted
## Builds cel-shaded (toon.gdshader) stand-ins for an imported model's PBR
## materials, keeping their colour, colour texture and glow. Normal, metallic
## and roughness maps are dropped on purpose: under hard light bands fine
## surface detail turns into speckled noise. Transparent materials are kept as
## imported (the toon shader is opaque).
##
## Used by GreatFox. (ShipModel does its own flat-colour conversion for the
## Arwing and keeps textured parts as imported.)

const SHADER := preload("res://effects/toon.gdshader")

## Toon copies already made, by source material, shared by every user.
static var _cache := {}


## Replaces every opaque BaseMaterial3D under `root` with its toon copy
## (as a surface override, so the imported scene itself is untouched).
static func convert_tree(root: Node) -> void:
	for child in root.get_children():
		if child is MeshInstance3D:
			var mesh := child as MeshInstance3D
			for surface in mesh.mesh.get_surface_count():
				var toon := from_material(mesh.get_active_material(surface) as BaseMaterial3D)
				if toon:
					mesh.set_surface_override_material(surface, toon)
		convert_tree(child)


## The toon material standing in for `source`, or null to keep `source`.
static func from_material(source: BaseMaterial3D) -> ShaderMaterial:
	if source == null or source.transparency != BaseMaterial3D.TRANSPARENCY_DISABLED:
		return null
	if _cache.has(source):
		return _cache[source]
	var material := ShaderMaterial.new()
	material.shader = SHADER
	material.set_shader_parameter("albedo", source.albedo_color)
	if source.albedo_texture:
		material.set_shader_parameter("albedo_texture", source.albedo_texture)
	if source.emission_enabled:
		material.set_shader_parameter("emission", source.emission)
		material.set_shader_parameter("emission_energy", source.emission_energy_multiplier)
		if source.emission_texture:
			material.set_shader_parameter("emission_texture", source.emission_texture)
	_cache[source] = material
	return material
