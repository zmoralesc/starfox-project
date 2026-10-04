class_name ShipModel
extends Node3D
## Art for the player's and wingmen's fighter: put on the root of an instanced
## imported model (the Arwing, models/arwing_assault/). On load it swaps the
## model's flat-colour PBR materials for the project's cel shader so it matches
## everything else, and paints one of them, the accent, in the ship's own
## colour (Fox yellow, each wingman its HUD colour via set_accent()).
##
## Textured, emissive and transparent materials are kept as imported: the toon
## shader has no texture or emission inputs.

const TOON := preload("res://effects/toon.gdshader")

## Imported material painted in accent_color (on the Arwing, the panels set
## into the blue fins).
@export var accent_material := "Material.004"
## Colour of the accent parts.
@export var accent_color := Color(0.95, 0.78, 0.12)

## Toon copies of the imported materials, shared by every ship using them.
static var _shared := {}
## This ship's own accent material (not shared, so each ship can be painted).
var _accent: ShaderMaterial


func _ready() -> void:
	_convert(self)
	set_accent(accent_color)


## Paints the accent parts in `color`.
func set_accent(color: Color) -> void:
	accent_color = color
	if _accent:
		_accent.set_shader_parameter("albedo", color)


func _convert(node: Node) -> void:
	for child in node.get_children():
		if child is MeshInstance3D:
			var mesh := child as MeshInstance3D
			for surface in mesh.mesh.get_surface_count():
				var toon := _toon_for(mesh.get_active_material(surface) as BaseMaterial3D)
				if toon:
					mesh.set_surface_override_material(surface, toon)
		_convert(child)


## The toon material standing in for `source`, or null to keep `source`.
func _toon_for(source: BaseMaterial3D) -> ShaderMaterial:
	if source == null or source.albedo_texture or source.emission_enabled \
			or source.transparency != BaseMaterial3D.TRANSPARENCY_DISABLED:
		return null
	if source.resource_name == accent_material:
		if _accent == null:
			_accent = _make_toon(accent_color)
		return _accent
	if not _shared.has(source):
		_shared[source] = _make_toon(source.albedo_color)
	return _shared[source]


func _make_toon(color: Color) -> ShaderMaterial:
	var material := ShaderMaterial.new()
	material.shader = TOON
	material.set_shader_parameter("albedo", color)
	return material
