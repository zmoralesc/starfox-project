class_name Terrain
extends Node3D
## Procedural low-poly ground for planet missions: rolling hills, clusters of
## ridged mountains away from the centre, lakes wherever the ground dips below
## sea level, and a ring of tall mountains around the edge as the arena's
## boundary. Built in code from seeded noise (same layout every run) as a
## flat-shaded mesh coloured per face (sand, grass, rock, snow by height and
## steepness), with matching collision on the World layer. A flat water plane
## at sea level fills the lakes, and a far ground plane fills the horizon
## beyond the map. Water and far ground are solid too, so you crash into them.
##
## With a `map` (a TerrainMap exported from Blender) the landscape comes from
## there instead of the noise, along with paved cells, a lake above sea level
## and the heights of the structures standing on the map.
##
## height_at() gives the ground height anywhere, exactly matching the mesh and
## its collision; surface_height() also counts the water; clearance_height()
## also counts the map's structures. Ground-aware systems (chase camera, AI,
## spawns) find the terrain through the "terrain" group.

## Noise seed: same seed, same landscape.
@export var terrain_seed := 1984
## A hand-made landscape. When set, the map's own size and heights are used and
## the Shape settings below are ignored (except `chunks` and `sea_level`).
@export var map: TerrainMap

@export_group("Shape")
## Width and depth of the map (it's square, centred on the origin).
@export var size := 4000.0
## Approximate edge length of a terrain triangle. Bigger = blockier.
@export var cell_size := 25.0
## Height of the water. Ground below it becomes lake.
@export var sea_level := 0.0
## Average ground height above sea level. Lower = more lakes.
@export var base_height := 8.0
## How far hills rise above and dip below the base height.
@export var hill_height := 70.0
## Rough width of a hill, in metres.
@export var hill_scale := 900.0
## Height of the tallest inland mountains.
@export var mountain_height := 320.0
## Rough width of a mountain range, in metres.
@export var mountain_scale := 1300.0
## No inland mountains within this distance of the centre, where missions start;
## they fade in over the next 500 m.
@export var clear_radius := 450.0
## Height of the boundary ring of mountains.
@export var ring_height := 520.0
## The ring rises from this fraction of the map's half-width...
@export_range(0.0, 1.0) var ring_start := 0.72
## ...to full height at this one, then falls back to sea level at the map edge.
@export_range(0.0, 1.0) var ring_peak := 0.9
## Terrain is built and collided in chunks this many to a side (smaller meshes
## cull better and keep collision shapes small).
@export var chunks := 8

@export_group("Colours")
## Material for the ground; uses the vertex colours (effects/toon_vertex.gdshader).
@export var material: Material
@export var sand_color := Color(0.86, 0.79, 0.55)
@export var grass_color := Color(0.42, 0.66, 0.3)
@export var grass_dark_color := Color(0.3, 0.52, 0.24)
@export var rock_color := Color(0.5, 0.47, 0.44)
@export var snow_color := Color(0.94, 0.96, 1.0)
## Cells the map marks as paved (towns, the base apron).
@export var paved_color := Color(0.55, 0.55, 0.58)
## Faces less than this far above sea level are sand (beaches and lake beds).
@export var sand_height := 6.0
## Faces higher than this above sea level are snow (unless too steep).
@export var snow_height := 260.0
## Faces steeper than this (normal's up component below it) are bare rock.
@export_range(0.0, 1.0) var rock_slope := 0.78
## Random brightness variation per face, for the low-poly look.
@export_range(0.0, 0.3) var shade_jitter := 0.05

@export_group("Water and far ground")
## Material for the lake surface (effects/water.gdshader).
@export var water_material: Material
## Water reaches the horizon instead of stopping at the map's edge (for a map
## with a coast: sea beyond it rather than the far ground).
@export var water_to_horizon := false
## Colour of the flat ground beyond the map's edge.
@export var far_ground_color := Color(0.3, 0.5, 0.25)
## How far the far ground extends, in metres.
@export var far_ground_size := 30000.0

## Grid points per side, the grid spacing, and the heights (row-major, z rows).
var _points := 0
var _cell := 1.0
var _heights := PackedFloat32Array()

var _hill_noise := FastNoiseLite.new()
var _mountain_noise := FastNoiseLite.new()
var _region_noise := FastNoiseLite.new()
var _patch_noise := FastNoiseLite.new()


func _enter_tree() -> void:
	# In _enter_tree, not _ready, so nodes earlier in the scene (the chase
	# camera) can find it in their own _ready.
	add_to_group("terrain")


func _ready() -> void:
	_setup_noise()
	if map:
		_load_map()
	else:
		_generate_heights()
	var body := StaticBody3D.new()
	body.name = "Ground"
	body.collision_layer = Fighter.LAYER_WORLD
	body.collision_mask = 0
	add_child(body)
	_build_chunks(body)
	_build_water(body)
	_build_far_ground(body)


## Ground height at a world x/z, exactly matching the mesh and collision.
## -INF outside the map (or before the terrain is built).
func height_at(x: float, z: float) -> float:
	if _heights.is_empty():
		return -INF
	var half := size * 0.5
	var gx := (x + half) / _cell
	var gz := (z + half) / _cell
	var cells := _points - 1
	if gx < 0.0 or gz < 0.0 or gx > cells or gz > cells:
		return -INF
	var i := mini(int(gx), cells - 1)
	var j := mini(int(gz), cells - 1)
	var u := gx - i
	var v := gz - j
	var h00 := _height(i, j)
	var h11 := _height(i + 1, j + 1)
	# Each cell is split along its (0,0)-(1,1) diagonal, as in _build_chunks().
	if u >= v:
		return h00 + (_height(i + 1, j) - h00) * u + (h11 - _height(i + 1, j)) * v
	return h00 + (_height(i, j + 1) - h00) * v + (h11 - _height(i, j + 1)) * u


## Height of whatever you'd hit flying straight down: ground or water.
func surface_height(x: float, z: float) -> float:
	var surface := maxf(height_at(x, z), sea_level)
	if map and _map_cell(map.paint, x, z) == TerrainMap.PAINT_HIGH_WATER:
		surface = maxf(surface, map.high_water_level)
	return surface


## Height to stay above: ground, water, or the top of any structure on the map
## (per map cell, so a whole cell counts as tall as the tallest thing on it).
## What the AI flies over; the camera uses surface_height() so it doesn't jump
## onto rooftops when you fly between buildings.
func clearance_height(x: float, z: float) -> float:
	var surface := surface_height(x, z)
	if map:
		surface = maxf(surface, _map_cell(map.structures, x, z))
	return surface


func _height(i: int, j: int) -> float:
	return _heights[j * _points + i]


## The value a per-cell map array holds for the cell under x/z; 0 outside the map.
func _map_cell(values: Variant, x: float, z: float) -> float:
	var cells := _points - 1
	var i := int(floor((x + size * 0.5) / _cell))
	var j := int(floor((z + size * 0.5) / _cell))
	if i < 0 or j < 0 or i >= cells or j >= cells:
		return 0.0
	return values[j * cells + i]


func _load_map() -> void:
	size = map.size
	_points = map.points
	_cell = size / (_points - 1)
	_heights = map.heights
	var cells := _points - 1
	if _heights.size() != _points * _points or map.paint.size() != cells * cells \
			or map.structures.size() != cells * cells:
		push_error("Terrain: map arrays don't match its %d points per side" % _points)
	if cells % chunks != 0:
		push_error("Terrain: the map's %d cells per side don't divide into %d chunks" % [cells, chunks])


func _setup_noise() -> void:
	_hill_noise.seed = terrain_seed
	_hill_noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	_hill_noise.frequency = 1.0 / hill_scale
	_hill_noise.fractal_type = FastNoiseLite.FRACTAL_FBM
	_hill_noise.fractal_octaves = 4

	_mountain_noise.seed = terrain_seed + 1
	_mountain_noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	_mountain_noise.frequency = 1.0 / mountain_scale
	_mountain_noise.fractal_type = FastNoiseLite.FRACTAL_FBM
	_mountain_noise.fractal_octaves = 4

	# Where mountain ranges are at all: large, slow regions.
	_region_noise.seed = terrain_seed + 2
	_region_noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	_region_noise.frequency = 1.0 / (mountain_scale * 1.6)
	_region_noise.fractal_type = FastNoiseLite.FRACTAL_NONE

	# Light and dark grass patches.
	_patch_noise.seed = terrain_seed + 3
	_patch_noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	_patch_noise.frequency = 1.0 / 350.0
	_patch_noise.fractal_type = FastNoiseLite.FRACTAL_NONE


func _generate_heights() -> void:
	var cells := maxi(int(round(size / cell_size)), chunks)
	cells = int(ceil(float(cells) / chunks)) * chunks  # whole cells per chunk
	_points = cells + 1
	_cell = size / cells
	var half := size * 0.5
	_heights.resize(_points * _points)
	for j in _points:
		for i in _points:
			_heights[j * _points + i] = _shape(-half + i * _cell, -half + j * _cell)


## The landscape: base height + hills + inland mountains + boundary ring,
## sinking to just below sea level at the very edge of the map.
func _shape(x: float, z: float) -> float:
	var half := size * 0.5
	var from_centre := Vector2(x, z).length()
	var hills := _hill_noise.get_noise_2d(x, z) * hill_height
	# Ridged: sharp crests where the noise crosses zero.
	var ridge := 1.0 - absf(_mountain_noise.get_noise_2d(x, z))
	ridge = ridge * ridge * ridge
	var region := smoothstep(-0.1, 0.4, _region_noise.get_noise_2d(x, z))
	var clear := smoothstep(clear_radius, clear_radius + 500.0, from_centre)
	var mountains := ridge * region * clear * mountain_height
	var ring := smoothstep(ring_start, ring_peak, from_centre / half) * ring_height * (0.7 + 0.3 * ridge)
	var height := base_height + hills + mountains + ring
	# Square edge falloff, so the map's border meets the far ground plane.
	var edge := maxf(absf(x), absf(z)) / half
	return lerpf(sea_level - 6.0, height, 1.0 - smoothstep(0.94, 1.0, edge))


func _build_chunks(body: StaticBody3D) -> void:
	var cells_per_chunk := (_points - 1) / chunks
	var rng := RandomNumberGenerator.new()
	rng.seed = terrain_seed
	for cz in chunks:
		for cx in chunks:
			var st := SurfaceTool.new()
			st.begin(Mesh.PRIMITIVE_TRIANGLES)
			var faces := PackedVector3Array()
			for j in range(cz * cells_per_chunk, (cz + 1) * cells_per_chunk):
				for i in range(cx * cells_per_chunk, (cx + 1) * cells_per_chunk):
					var p00 := _point(i, j)
					var p10 := _point(i + 1, j)
					var p01 := _point(i, j + 1)
					var p11 := _point(i + 1, j + 1)
					var paved: bool = map != null and map.paint[j * (_points - 1) + i] == TerrainMap.PAINT_PAVED
					# Split along the (0,0)-(1,1) diagonal, matching height_at().
					_add_face(st, faces, rng, p00, p10, p11, paved)
					_add_face(st, faces, rng, p00, p11, p01, paved)
			var mesh_instance := MeshInstance3D.new()
			mesh_instance.mesh = st.commit()
			mesh_instance.material_override = material
			add_child(mesh_instance)
			var shape := ConcavePolygonShape3D.new()
			shape.set_faces(faces)
			var collision := CollisionShape3D.new()
			collision.shape = shape
			body.add_child(collision)


func _point(i: int, j: int) -> Vector3:
	var half := size * 0.5
	return Vector3(-half + i * _cell, _height(i, j), -half + j * _cell)


## One flat-shaded triangle facing up, coloured by its height and steepness
## (or paved_color).
func _add_face(st: SurfaceTool, faces: PackedVector3Array, rng: RandomNumberGenerator,
		a: Vector3, b: Vector3, c: Vector3, paved := false) -> void:
	# Godot draws clockwise-wound faces (seen from the front): for an
	# upward-facing triangle, (b - a) x (c - a) must point down.
	if (b - a).cross(c - a).y > 0.0:
		var swap := b
		b = c
		c = swap
	var normal := (c - a).cross(b - a).normalized()
	var centre := (a + b + c) / 3.0
	var color := paved_color if paved else _face_color(centre, normal)
	color = color * (1.0 + rng.randf_range(-shade_jitter, shade_jitter))
	color.a = 1.0
	# Vertex colours reach the shader as-is (no sRGB conversion), so convert
	# here to match `source_color` uniforms elsewhere.
	color = color.srgb_to_linear()
	st.set_normal(normal)
	st.set_color(color)
	for p: Vector3 in [a, b, c]:
		st.add_vertex(p)
		faces.append(p)


func _face_color(centre: Vector3, normal: Vector3) -> Color:
	var above_sea := centre.y - sea_level
	if above_sea < sand_height:
		return sand_color
	if normal.y < rock_slope:
		return rock_color
	if above_sea > snow_height:
		return snow_color
	return grass_dark_color if _patch_noise.get_noise_2d(centre.x, centre.z) > 0.15 else grass_color


func _build_water(body: StaticBody3D) -> void:
	var extent := far_ground_size if water_to_horizon else size
	var plane := PlaneMesh.new()
	plane.size = Vector2(extent, extent)
	var water := MeshInstance3D.new()
	water.name = "Water"
	water.mesh = plane
	water.material_override = water_material
	water.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	water.position.y = sea_level
	add_child(water)
	body.add_child(_slab(Vector2(extent, extent), sea_level))


func _build_far_ground(body: StaticBody3D) -> void:
	var far := ShaderMaterial.new()
	far.shader = preload("res://effects/toon.gdshader")
	far.set_shader_parameter("albedo", far_ground_color)
	var plane := PlaneMesh.new()
	plane.size = Vector2(far_ground_size, far_ground_size)
	var ground := MeshInstance3D.new()
	ground.name = "FarGround"
	ground.mesh = plane
	ground.material_override = far
	ground.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	# Just under the water and the map's sunken edge, so it only shows beyond.
	ground.position.y = sea_level - 4.0
	add_child(ground)
	body.add_child(_slab(Vector2(far_ground_size, far_ground_size), sea_level - 4.0))


## A thin solid box whose top is at `top`.
func _slab(extent: Vector2, top: float) -> CollisionShape3D:
	var box := BoxShape3D.new()
	box.size = Vector3(extent.x, 2.0, extent.y)
	var collision := CollisionShape3D.new()
	collision.shape = box
	collision.position.y = top - 1.0
	return collision
