class_name MapProps
extends Node3D
## On an imported map props model (models/corneria/corneria_props.glb, built by
## source/build_corneria.py): draws the map's kit pieces where its `layout`
## places them, cel-shades everything (ToonMaterial), gives the water surfaces
## the level's water material, and makes the solid parts collide on the World
## layer, so you crash into buildings, bolts hit them and they block the AI's
## line of sight. The editor shows only the imported part (see below).
##
## The props come in two parts. Kit pieces placed whole (towers, houses, trees,
## streets) are MultiMesh instances of one mesh each from `kit`, grouped by
## `tile_size` squares so what's off screen is culled. The rest (pieces cut down
## or reshaped as they were placed, and what the build script makes itself:
## water, roads, ramps) is the imported model's own geometry, one mesh per
## group per tile, named "<group>__<i>_<j>".
##
## The AI doesn't use this collision to steer: it flies over the structure
## heights the map export rasterised (Terrain.clearance_height()).

## Where the kit pieces stand (models/corneria/corneria_layout.tres).
@export var layout: PropLayout
## The kit pieces: a scene with one mesh per piece, named as in `layout`
## (models/corneria/corneria_kit.glb).
@export var kit: PackedScene
## Side of the squares instances are grouped by (one MultiMesh per piece per
## square), in metres. Smaller culls more finely but costs more draw calls.
@export var tile_size := 500.0
## Replaces the materials named `water_material_name` (the plateau lake and river).
@export var water_material: Material
@export var water_material_name := "Corneria_Water"
## Groups that get collision. Leave out the flat ones that lie on the ground
## (roads, streets) and the ones you should fly through (trees).
@export var solid_groups: PackedStringArray = ["City", "Town", "Base", "Arches", "RiverBridge", "SeaStacks", "Water"]
## Materials (by name) drawn without ink outlines: the foliage (trees, and the
## green tufts on the sea stacks), whose thousands of small cones were a tangle
## of lines. See effects/toon_unlined.gdshader.
@export var unlined_materials: PackedStringArray = ["Corneria_Tree", "Corneria_TreeLight", "Corneria_Trunk"]

@export_group("Draw distance")
## How far away each group is still drawn (group name: metres; 0 or absent =
## as far as the camera sees). Measured from the camera to each tile's centre,
## so a tile's pieces appear and vanish together.
@export var group_draw_distance: Dictionary[String, float] = {}
## The same for single kit pieces (kit mesh name: metres), over their group's.
## A name also covers the pieces it begins (its variants: "Kit_Tree_Pine" is
## also "Kit_Tree_Pine_B"); the longest match wins.
@export var piece_draw_distance: Dictionary[String, float] = {}
## Metres either side of a draw distance where it doesn't flicker on and off.
@export var draw_distance_margin := 60.0

## The physics body holding the instances' collision (no node: thousands of
## shapes, added straight to the physics server).
var _instance_body := RID()


func _ready() -> void:
	ToonMaterial.convert_tree(self, unlined_materials)
	_add_shadow_casters(self)
	if water_material:
		_paint_water(self)
	_collide_imported()
	_draw_distance_imported()
	if layout and kit:
		_build_instances()


func _exit_tree() -> void:
	if _instance_body.is_valid():
		PhysicsServer3D.free_rid(_instance_body)
		_instance_body = RID()


## The group a node belongs to, by its name ("City__3_5" is in City).
static func group_of(node_name: String) -> String:
	return node_name.get_slice("__", 0)


## Trimesh collision for the imported geometry of the solid groups.
func _collide_imported() -> void:
	var body := StaticBody3D.new()
	body.name = "Collision"
	body.collision_layer = Fighter.LAYER_WORLD
	body.collision_mask = 0
	add_child(body)
	for node in find_children("*", "MeshInstance3D", true, false):
		var mesh := node as MeshInstance3D
		if mesh.get_parent() != self or not group_of(mesh.name) in solid_groups:
			continue
		var shape := mesh.mesh.create_trimesh_shape()
		# Some props are single sheets (the lake, the river): solid from both sides.
		shape.backface_collision = true
		var collision := CollisionShape3D.new()
		collision.name = mesh.name
		collision.shape = shape
		body.add_child(collision)
		collision.global_transform = mesh.global_transform


func _draw_distance_imported() -> void:
	for child in get_children():
		if child is MeshInstance3D:
			_set_draw_distance(child, group_draw_distance.get(group_of(child.name), 0.0))


## A kit piece's draw distance: piece_draw_distance's longest key it begins
## with, or `fallback` (its group's).
func _piece_distance(piece_name: String, fallback: float) -> float:
	var best := ""
	for key: String in piece_draw_distance:
		if piece_name.begins_with(key) and key.length() > best.length():
			best = key
	return piece_draw_distance[best] if best else fallback


func _set_draw_distance(node: GeometryInstance3D, distance: float) -> void:
	if distance <= 0.0:
		return
	node.visibility_range_end = distance
	node.visibility_range_end_margin = draw_distance_margin


## One MultiMeshInstance3D per kit piece per tile, with its collision.
func _build_instances() -> void:
	var source := kit.instantiate()
	# Per piece: its toon-shaded mesh, the shadow stand-in for its unlined
	# surfaces (or null), and its collision shape (made when first needed).
	var meshes: Array[Mesh] = []
	var shadow_meshes: Array[Mesh] = []
	var shapes: Array[Shape3D] = []
	for piece_name in layout.pieces:
		var node := source.find_child(piece_name, true, false) as MeshInstance3D
		if node == null:
			push_warning("MapProps: kit has no mesh named %s" % piece_name)
			meshes.append(null)
			shadow_meshes.append(null)
		else:
			meshes.append(_toon_mesh(node.mesh))
			shadow_meshes.append(_unlined_surfaces(node.mesh))
		shapes.append(null)
	source.free()

	# Placed pieces by tile and piece.
	var tiles := {}
	for k in layout.count():
		var origin := Vector3(layout.transforms[k * 12 + 9], 0.0, layout.transforms[k * 12 + 11])
		var key := Vector3i(floori(origin.x / tile_size), floori(origin.z / tile_size), layout.piece[k])
		if not tiles.has(key):
			tiles[key] = PackedInt32Array()
		tiles[key].append(k)

	var root := Node3D.new()
	root.name = "Instances"
	add_child(root)
	for key: Vector3i in tiles:
		var mesh := meshes[key.z]
		if mesh == null:
			continue
		var placed: PackedInt32Array = tiles[key]
		var piece_name: String = layout.pieces[key.z]
		var group_name: String = layout.groups[layout.group[placed[0]]]
		var instance := _multimesh(mesh, placed)
		instance.name = "%s__%d_%d" % [piece_name, key.x, key.y]
		var distance := _piece_distance(piece_name, group_draw_distance.get(group_name, 0.0))
		_set_draw_distance(instance, distance)
		root.add_child(instance)
		if shadow_meshes[key.z]:
			var caster := _multimesh(shadow_meshes[key.z], placed)
			caster.name = instance.name + "Shadow"
			caster.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
			_set_draw_distance(caster, distance)
			root.add_child(caster)

	# Collision: each piece's shape, shared by all its instances in the solid
	# groups, added at each one's transform (Jolt scales concave shapes, unevenly too).
	_instance_body = PhysicsServer3D.body_create()
	PhysicsServer3D.body_set_mode(_instance_body, PhysicsServer3D.BODY_MODE_STATIC)
	PhysicsServer3D.body_set_collision_layer(_instance_body, Fighter.LAYER_WORLD)
	PhysicsServer3D.body_set_collision_mask(_instance_body, 0)
	# Hits report this node as the collider.
	PhysicsServer3D.body_attach_object_instance_id(_instance_body, get_instance_id())
	PhysicsServer3D.body_set_state(_instance_body, PhysicsServer3D.BODY_STATE_TRANSFORM, global_transform)
	for k in layout.count():
		if not layout.groups[layout.group[k]] in solid_groups or meshes[layout.piece[k]] == null:
			continue
		var p: int = layout.piece[k]
		if shapes[p] == null:
			var shape := meshes[p].create_trimesh_shape()
			shape.backface_collision = true
			shapes[p] = shape
		PhysicsServer3D.body_add_shape(_instance_body, shapes[p].get_rid(), layout.transform_of(k))
	# The server holds the shapes by RID only: keep the resources alive.
	set_meta(&"instance_shapes", shapes)
	PhysicsServer3D.body_set_space(_instance_body, get_world_3d().space)


## A MultiMeshInstance3D drawing `mesh` at the layout's placed pieces `placed`.
func _multimesh(mesh: Mesh, placed: PackedInt32Array) -> MultiMeshInstance3D:
	var multimesh := MultiMesh.new()
	multimesh.transform_format = MultiMesh.TRANSFORM_3D
	multimesh.mesh = mesh
	multimesh.instance_count = placed.size()
	for n in placed.size():
		multimesh.set_instance_transform(n, layout.transform_of(placed[n]))
	var instance := MultiMeshInstance3D.new()
	instance.multimesh = multimesh
	return instance


## A copy of a kit mesh with toon materials for instances (normals corrected
## for uneven scale: toon_instanced.gdshader).
func _toon_mesh(source: Mesh) -> Mesh:
	var mesh := source.duplicate() as Mesh
	for surface in mesh.get_surface_count():
		var material := mesh.surface_get_material(surface) as BaseMaterial3D
		var toon := ToonMaterial.from_material(material, material != null and material.resource_name in unlined_materials, true)
		if toon:
			mesh.surface_set_material(surface, toon)
	return mesh


## Just the unlined surfaces of a kit mesh (for a shadow stand-in), or null.
func _unlined_surfaces(source: Mesh) -> Mesh:
	var shadow_mesh := ArrayMesh.new()
	for surface in source.get_surface_count():
		var material := source.surface_get_material(surface)
		if material and material.resource_name in unlined_materials:
			shadow_mesh.add_surface_from_arrays(source.surface_get_primitive_type(surface),
					source.surface_get_arrays(surface))
	return shadow_mesh if shadow_mesh.get_surface_count() > 0 else null


## Unlined surfaces are drawn in the transparent pass, which casts no shadows,
## so each mesh with some gets a stand-in: just those surfaces, drawn only into
## the shadow maps (which InkOutline doesn't read).
func _add_shadow_casters(root: Node) -> void:
	for node in root.find_children("*", "MeshInstance3D", true, false):
		var source := node as MeshInstance3D
		var shadow_mesh := _unlined_surfaces(source.mesh)
		if shadow_mesh == null:
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
