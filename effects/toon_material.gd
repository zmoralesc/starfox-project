class_name ToonMaterial
extends RefCounted
## Builds cel-shaded (toon.gdshader) stand-ins for an imported model's PBR
## materials, keeping their colour, colour texture and glow. Normal, metallic
## and roughness maps are dropped on purpose: under hard light bands fine
## surface detail turns into speckled noise. Transparent materials are kept as
## imported (the toon shader is opaque).
##
## Used by GreatFox, the destroyer, the space station, the fighters and MapProps
## (which also uses the MultiMesh variants for its instanced kit). (ShipModel
## does its own flat-colour conversion for the Arwing and keeps textured parts
## as imported.)

const SHADER := preload("res://effects/toon.gdshader")
## The same look without ink outlines (see toon_unlined.gdshader).
const UNLINED_SHADER := preload("res://effects/toon_unlined.gdshader")
## Both again for MultiMesh instances (see toon_instanced.gdshader).
const INSTANCED_SHADER := preload("res://effects/toon_instanced.gdshader")
const UNLINED_INSTANCED_SHADER := preload("res://effects/toon_unlined_instanced.gdshader")

## Toon copies already made, by source material, shared by every user (each
## variant in its own cache).
static var _cache := {}
static var _unlined_cache := {}
static var _instanced_cache := {}
static var _unlined_instanced_cache := {}


## Replaces every opaque BaseMaterial3D under `root` with its toon copy
## (as a surface override, so the imported scene itself is untouched).
## Materials whose names are in `unlined` get the copy without ink outlines.
static func convert_tree(root: Node, unlined: PackedStringArray = []) -> void:
	for child in root.get_children():
		if child is MeshInstance3D:
			var mesh := child as MeshInstance3D
			for surface in mesh.mesh.get_surface_count():
				var source := mesh.get_active_material(surface) as BaseMaterial3D
				var toon := from_material(source, source != null and source.resource_name in unlined)
				if toon:
					mesh.set_surface_override_material(surface, toon)
		convert_tree(child, unlined)


## The toon material standing in for `source` (without ink outlines if
## `unlined`; for MultiMesh instances if `instanced`), or null to keep `source`.
static func from_material(source: BaseMaterial3D, unlined := false, instanced := false) -> ShaderMaterial:
	if source == null or source.transparency != BaseMaterial3D.TRANSPARENCY_DISABLED:
		return null
	var cache: Dictionary
	var shader: Shader
	if instanced:
		cache = _unlined_instanced_cache if unlined else _instanced_cache
		shader = UNLINED_INSTANCED_SHADER if unlined else INSTANCED_SHADER
	else:
		cache = _unlined_cache if unlined else _cache
		shader = UNLINED_SHADER if unlined else SHADER
	if cache.has(source):
		return cache[source]
	var material := ShaderMaterial.new()
	material.shader = shader
	material.set_shader_parameter("albedo", source.albedo_color)
	if source.albedo_texture:
		material.set_shader_parameter("albedo_texture", source.albedo_texture)
	if source.emission_enabled:
		material.set_shader_parameter("emission", source.emission)
		material.set_shader_parameter("emission_energy", source.emission_energy_multiplier)
		if source.emission_texture:
			material.set_shader_parameter("emission_texture", source.emission_texture)
	cache[source] = material
	return material
