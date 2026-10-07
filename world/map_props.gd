class_name MapProps
extends Node3D
## On an imported map props model (models/corneria/corneria_props.glb, built by
## source/build_corneria.py): cel-shades its materials (ToonMaterial), gives
## the water surfaces the level's water material, and makes the solid parts
## collide on the World layer, so you crash into buildings, bolts hit them and
## they block the AI's line of sight. The editor shows the imported originals.
##
## The AI doesn't use this collision to steer: it flies over the structure
## heights the map export rasterised (Terrain.clearance_height()).

## Replaces the materials named `water_material_name` (the plateau lake and river).
@export var water_material: Material
@export var water_material_name := "Corneria_Water"
## Child meshes (by node name) that get collision. Leave out the flat ones that
## lie on the ground (roads, streets) and the ones you should fly through (trees).
@export var solid_nodes: PackedStringArray = ["City", "Town", "Base", "Arches", "RiverBridge", "SeaStacks", "Water"]
## Materials (by name) drawn without ink outlines: the foliage (trees, and the
## green tufts on the sea stacks), whose thousands of small cones were a tangle
## of lines. See effects/toon_unlined.gdshader.
@export var unlined_materials: PackedStringArray = ["Corneria_Tree", "Corneria_TreeLight", "Corneria_Trunk"]


func _ready() -> void:
	ToonMaterial.convert_tree(self, unlined_materials)
	_add_shadow_casters()
	if water_material:
		_paint_water(self)
	var body := StaticBody3D.new()
	body.name = "Collision"
	body.collision_layer = Fighter.LAYER_WORLD
	body.collision_mask = 0
	add_child(body)
	for node_name in solid_nodes:
		var mesh := find_child(node_name, true, false) as MeshInstance3D
		if mesh == null:
			push_warning("MapProps: no mesh named %s" % node_name)
			continue
		var shape := mesh.mesh.create_trimesh_shape()
		# Some props are single sheets (the lake, the river): solid from both sides.
		shape.backface_collision = true
		var collision := CollisionShape3D.new()
		collision.name = node_name
		collision.shape = shape
		body.add_child(collision)
		collision.global_transform = mesh.global_transform


## Unlined surfaces are drawn in the transparent pass, which casts no shadows,
## so each mesh with some gets a stand-in: just those surfaces, drawn only into
## the shadow maps (which InkOutline doesn't read).
func _add_shadow_casters() -> void:
	for node in find_children("*", "MeshInstance3D", true, false):
		var source := node as MeshInstance3D
		var shadow_mesh := ArrayMesh.new()
		for surface in source.mesh.get_surface_count():
			var material := source.mesh.surface_get_material(surface)
			if material and material.resource_name in unlined_materials:
				shadow_mesh.add_surface_from_arrays(source.mesh.surface_get_primitive_type(surface),
						source.mesh.surface_get_arrays(surface))
		if shadow_mesh.get_surface_count() == 0:
			continue
		var caster := MeshInstance3D.new()
		caster.name = source.name + "Shadow"
		caster.mesh = shadow_mesh
		caster.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
		source.add_child(caster)


func _paint_water(node: Node) -> void:
	for child in node.get_children():
		if child is MeshInstance3D:
			var mesh := child as MeshInstance3D
			for surface in mesh.mesh.get_surface_count():
				var source := mesh.mesh.surface_get_material(surface)
				if source and source.resource_name == water_material_name:
					mesh.set_surface_override_material(surface, water_material)
		_paint_water(child)
