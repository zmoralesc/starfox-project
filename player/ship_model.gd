class_name ShipModel
extends Node3D
## Art for the player's and wingmen's fighter: put on the root of an instanced
## imported model (the Arwing, models/arwing_assault/). On load it swaps the
## model's flat-colour PBR materials for the project's cel shader so it matches
## everything else, and paints a band across the fins in the ship's own colour
## (Fox yellow, each wingman its HUD colour via set_accent()): see
## player/arwing_band.gdshader.
##
## Textured, emissive and transparent materials are kept as imported: the toon
## shader has no texture or emission inputs.

const TOON := preload("res://effects/toon.gdshader")
const BAND := preload("res://player/arwing_band.gdshader")

## Colour of the band (the pilot's colour).
@export var accent_color := Color(0.95, 0.78, 0.12)

@export_group("Band")
## Paint the pilot band at all. Off, the fins keep their plain colour and the
## overhead HUD markers are the only way to tell the ships apart.
@export var show_band := false
## Imported materials the band is painted across (on the Arwing, the blue fins
## and the panels set into them). They keep their own colour elsewhere.
@export var band_materials := PackedStringArray(["Material.002", "Material.004"])
## The band is a shell this far (m) from band_hub, a point at the root of the
## right-hand fins (in the ship's Model space; mirrored for the left), so it
## crosses every fin blade at the same distance out. The blade tips are about
## 3.3 m from the hub.
@export var band_hub := Vector3(1.0, 0.3, -0.1)
@export var band_radius := 2.3
## Width of the band, and of the pinstripe along each of its edges (m).
@export var band_width := 0.4
@export var pinstripe_width := 0.06
## Pinstripe colour: keeps the band readable when it is close to the fins'
## own blue (Falco).
@export var pinstripe_color := Color(0.95, 0.95, 0.95)

## Toon copies of the imported materials, shared by every ship using them.
static var _shared := {}
## This ship's band materials, one per mesh (not shared: each ship has its own
## colour, and each mesh its own transform to the ship).
var _bands: Array[ShaderMaterial] = []


func _ready() -> void:
	_convert(self)
	set_accent(accent_color)


## Paints the band in `color`.
func set_accent(color: Color) -> void:
	accent_color = color
	for band in _bands:
		band.set_shader_parameter("band_color", color)


func _convert(node: Node) -> void:
	for child in node.get_children():
		if child is MeshInstance3D:
			var mesh := child as MeshInstance3D
			for surface in mesh.mesh.get_surface_count():
				var toon := _toon_for(mesh.get_active_material(surface) as BaseMaterial3D, mesh)
				if toon:
					mesh.set_surface_override_material(surface, toon)
		_convert(child)


## The toon material standing in for `source` on `mesh`, or null to keep `source`.
func _toon_for(source: BaseMaterial3D, mesh: MeshInstance3D) -> ShaderMaterial:
	if source == null or source.albedo_texture or source.emission_enabled \
			or source.transparency != BaseMaterial3D.TRANSPARENCY_DISABLED:
		return null
	if show_band and source.resource_name in band_materials:
		return _make_band(source.albedo_color, mesh)
	if not _shared.has(source):
		_shared[source] = _make_toon(source.albedo_color)
	return _shared[source]


## A band material for `mesh`, on a base of `color`.
func _make_band(color: Color, mesh: MeshInstance3D) -> ShaderMaterial:
	var material := ShaderMaterial.new()
	material.shader = BAND
	material.set_shader_parameter("albedo", color)
	material.set_shader_parameter("band_color", accent_color)
	material.set_shader_parameter("pinstripe_color", pinstripe_color)
	# Model space is our parent's (where band_hub is measured). The model's
	# parts don't move relative to the ship, so this is set once.
	var ship_space := get_parent_node_3d().global_transform.affine_inverse() * mesh.global_transform
	material.set_shader_parameter("to_ship", Projection(ship_space))
	material.set_shader_parameter("band_hub", band_hub)
	material.set_shader_parameter("band_radius", band_radius)
	material.set_shader_parameter("band_width", band_width)
	material.set_shader_parameter("pinstripe_width", pinstripe_width)
	_bands.append(material)
	return material


func _make_toon(color: Color) -> ShaderMaterial:
	var material := ShaderMaterial.new()
	material.shader = TOON
	material.set_shader_parameter("albedo", color)
	return material
