class_name FighterModel
extends Node3D
## On the imported enemy fighter model (models/enemy_fighter/, built by
## source/build_enemy_fighter.py): swaps its materials for cel-shaded ones and
## paints the markings and lights in this fighter type's colours, so one model
## serves every type (the elite in enemy_fighter.tscn, the light fighter
## overrides the colours in light_fighter.tscn). The editor shows the
## imported originals.

## Painted markings: pincer tips and bands, wing stripes, wingtip plates,
## dorsal fin (material Fighter_Accent).
@export var accent_color := Color(0.5, 0.16, 0.46)
## The eye and the running lights on the pincer tips, wing edges and tip plates
## (material Fighter_Lights). Bright enough to bloom, so fighters stand out
## against space even far off.
@export var light_color := Color(1.0, 0.15, 0.1)
@export var light_energy := 10.0

const ACCENT_MATERIAL := "Fighter_Accent"
const LIGHTS_MATERIAL := "Fighter_Lights"

## Painted materials already made, by colour, shared by every fighter of a type.
static var _painted := {}


func _ready() -> void:
	ToonMaterial.convert_tree(self)
	_paint(self, _accent_material(), _lights_material())


func _paint(node: Node, accent: Material, lights: Material) -> void:
	for child in node.get_children():
		if child is MeshInstance3D:
			var mesh := (child as MeshInstance3D).mesh
			for surface in mesh.get_surface_count():
				var source := mesh.surface_get_material(surface)
				if source == null:
					continue
				if source.resource_name == ACCENT_MATERIAL:
					(child as MeshInstance3D).set_surface_override_material(surface, accent)
				elif source.resource_name == LIGHTS_MATERIAL:
					(child as MeshInstance3D).set_surface_override_material(surface, lights)
		_paint(child, accent, lights)


func _accent_material() -> ShaderMaterial:
	var key := "accent %s" % accent_color
	if not _painted.has(key):
		var material := ShaderMaterial.new()
		material.shader = ToonMaterial.SHADER
		material.set_shader_parameter("albedo", accent_color)
		_painted[key] = material
	return _painted[key]


func _lights_material() -> ShaderMaterial:
	var key := "lights %s %s" % [light_color, light_energy]
	if not _painted.has(key):
		var material := ShaderMaterial.new()
		material.shader = ToonMaterial.SHADER
		material.set_shader_parameter("albedo", light_color)
		material.set_shader_parameter("emission", light_color)
		material.set_shader_parameter("emission_energy", light_energy)
		_painted[key] = material
	return _painted[key]
