class_name Terrain
extends Node3D
## Procedural ground for planet missions: rolling hills, clusters of ridged
## mountains away from the centre, lakes wherever the ground dips below sea
## level, and a ring of tall mountains around the edge as the arena's
## boundary. Built in code from seeded noise (same layout every run) as a
## smooth-shaded mesh, coloured per pixel by effects/terrain.gdshader (sand,
## grass, rock, snow by height and steepness), with matching collision on the
## World layer. A flat water plane
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
## Material for the ground (effects/terrain.gdshader; one is made if unset).
## Terrain hands it the colours and heights below and the map's paint; the
## look (patches, ragged edges, rock facets, textures) is tuned on it.
@export var material: Material
@export var sand_color := Color(0.86, 0.79, 0.55)
@export var grass_color := Color(0.42, 0.66, 0.3)
@export var grass_dark_color := Color(0.3, 0.52, 0.24)
@export var rock_color := Color(0.5, 0.47, 0.44)
@export var snow_color := Color(0.94, 0.96, 1.0)
## Cells the map marks as paved (towns, the base apron).
@export var paved_color := Color(0.55, 0.55, 0.58)
## Ground less than this far above sea level is sand (beaches and lake beds).
@export var sand_height := 6.0
## Ground higher than this above sea level is snow (unless too steep).
@export var snow_height := 260.0
## Ground steeper than this (normal's up component below it) are bare rock.
@export_range(0.0, 1.0) var rock_slope := 0.78

@export_group("Water and far ground")
## Material for the lake surface (effects/water.gdshader).
@export var water_material: Material
## Its render priority: between the ink outline quad (-100) and other
## see-through things (0). See water.gdshader.
@export_range(-128, 127) var water_render_priority := -50
## Water reaches the horizon instead of stopping at the map's edge (for a map
## with a coast: sea beyond it rather than the far ground).
@export var water_to_horizon := false
## Colour of the flat ground beyond the map's edge.
@export var far_ground_color := Color(0.3, 0.5, 0.25)
## How far the far ground extends, in metres.
@export var far_ground_size := 30000.0
## The water shader colours by depth, but only near land: from this far out
## (m) the sea floor it sees fades to `open_sea_depth`, fully at the second
## value. Otherwise a map's artificial edge (Corneria's border sinks in a
## straight ramp to -6 m) draws straight depth bands kilometres long.
@export var water_depth_fade := Vector2(150.0, 600.0)
## Depth the water shader assumes for open sea (and beyond the map).
@export var open_sea_depth := 100.0

@export_group("Backdrop")
## Scenery beyond the map's edge, so the land seems to go on instead of ending
## in a straight line: a coarse ring of ground around the map, carrying on its
## edge heights and turning into mountains further out (open sea where the
## edge is sea). Only to look at: no collision, out of the player's reach.
@export var backdrop := false
## How far it reaches past the map's edge, in metres (keep it past the camera's
## far plane, seen from the play boundary).
@export var backdrop_reach := 5500.0
## It starts this far inside the map's edge (rounded to whole cells), where the
## map's border starts sinking toward the far ground, and covers that border.
@export var backdrop_inset := 150.0
## Width of its first ring of triangles, in metres...
@export var backdrop_first_step := 50.0
## ...each further ring this much wider than the last (coarser further out).
@export var backdrop_step_growth := 1.2
## The edge's own shape (smoothed over this many metres along the edge) gives
## way to the backdrop's mountains over this distance past the edge.
@export var backdrop_blend := 1500.0
## The edge's heights are averaged over this many metres along it before
## they're carried outward, so their small bumps don't streak outward.
@export var backdrop_smoothing := 400.0
## Height of the backdrop's valleys above sea level...
@export var backdrop_base := 40.0
## ...and how much higher its ridges rise.
@export var backdrop_height := 600.0
## Rough width of a backdrop mountain, in metres.
@export var backdrop_scale := 2200.0
## Only the noise's crests above this (0..1) rise into ridges; lower = more and
## broader mountains, fewer valleys.
@export_range(0.0, 0.95) var backdrop_crest := 0.5
## Where the edge (smoothed) is higher than this above sea level, the backdrop
## beyond it is land; elsewhere it's sea floor.
@export var backdrop_land_height := 20.0
## The share of land along the edge is averaged over this many metres, so
## land meets sea over a wide stretch of the backdrop, not in a straight cliff...
@export var backdrop_coast_smoothing := 3000.0
## ...and noise of this strength (share of land, 0..1) makes that coastline wander.
@export var backdrop_coast_wobble := 0.35

## Grid points per side, the grid spacing, and the heights (row-major, z rows).
var _points := 0
var _cell := 1.0
var _heights := PackedFloat32Array()

var _hill_noise := FastNoiseLite.new()
var _mountain_noise := FastNoiseLite.new()
var _region_noise := FastNoiseLite.new()


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
	if material == null:
		material = ShaderMaterial.new()
		material.shader = preload("res://effects/terrain.gdshader")
	_feed_ground(material)
	_build_chunks(body)
	_build_water(body)
	_build_far_ground(body)
	if backdrop:
		_build_backdrop()


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


## Height of the water's surface at x/z (the sea, or a map's raised lake or
## river), or -INF where the ground is at or above it (dry land).
func water_level_at(x: float, z: float) -> float:
	var surface := surface_height(x, z)
	return surface if height_at(x, z) < surface - 0.05 else -INF


## True if `point` lies on the water's surface (within `tolerance` metres), e.g.
## where a bolt hit: the splash goes there instead of the impact flash.
func is_water_surface(point: Vector3, tolerance := 0.5) -> bool:
	return absf(point.y - water_level_at(point.x, point.z)) < tolerance


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
	var side := cells_per_chunk + 1
	var normals := _grid_normals()
	for cz in chunks:
		for cx in chunks:
			# One vertex per grid point, shared by the triangles around it, so
			# the normals (and the light bands) are smooth across the land.
			var vertices := PackedVector3Array()
			var chunk_normals := PackedVector3Array()
			for j in side:
				for i in side:
					var gi := cx * cells_per_chunk + i
					var gj := cz * cells_per_chunk + j
					vertices.append(_point(gi, gj))
					chunk_normals.append(normals[gj * _points + gi])
			var indices := PackedInt32Array()
			var faces := PackedVector3Array()
			for j in cells_per_chunk:
				for i in cells_per_chunk:
					var k00 := j * side + i
					var k01 := k00 + side
					# Split along the (0,0)-(1,1) diagonal, matching height_at(),
					# wound clockwise seen from above (Godot's front face).
					for k: int in [k00, k00 + 1, k01 + 1, k00, k01 + 1, k01]:
						indices.append(k)
						faces.append(vertices[k])
			var arrays := []
			arrays.resize(Mesh.ARRAY_MAX)
			arrays[Mesh.ARRAY_VERTEX] = vertices
			arrays[Mesh.ARRAY_NORMAL] = chunk_normals
			arrays[Mesh.ARRAY_INDEX] = indices
			var mesh := ArrayMesh.new()
			mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
			var mesh_instance := MeshInstance3D.new()
			mesh_instance.mesh = mesh
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


## The ground's normal at each grid point (row-major, like the heights), from
## the slope to its neighbours on either side (one side at the map's edge).
func _grid_normals() -> PackedVector3Array:
	var normals := PackedVector3Array()
	normals.resize(_points * _points)
	for j in _points:
		for i in _points:
			normals[j * _points + i] = _grid_normal(i, j)
	return normals


## The ground's normal at one grid point (see _grid_normals()).
func _grid_normal(i: int, j: int) -> Vector3:
	var last := _points - 1
	var i0 := maxi(i - 1, 0)
	var i1 := mini(i + 1, last)
	var j0 := maxi(j - 1, 0)
	var j1 := mini(j + 1, last)
	var slope_x := (_height(i1, j) - _height(i0, j)) / ((i1 - i0) * _cell)
	var slope_z := (_height(i, j1) - _height(i, j0)) / ((j1 - j0) * _cell)
	return Vector3(-slope_x, 1.0, -slope_z).normalized()


## Gives the ground material (effects/terrain.gdshader) the colours and heights
## exported here, and the map's paved cells as a texture.
func _feed_ground(ground: Material) -> void:
	var shader_material := ground as ShaderMaterial
	if shader_material == null:
		return
	var values := {
		"sand_color": sand_color, "grass_color": grass_color, "grass_dark_color": grass_dark_color,
		"rock_color": rock_color, "snow_color": snow_color, "paved_color": paved_color,
		"sea_level": sea_level, "sand_height": sand_height, "snow_height": snow_height,
		"rock_slope": rock_slope,
	}
	for key: String in values:
		shader_material.set_shader_parameter(key, values[key])
	shader_material.set_shader_parameter("has_paint", map != null)
	if map == null:
		return
	var cells := _points - 1
	var paved := PackedByteArray()
	paved.resize(cells * cells)
	for k in cells * cells:
		paved[k] = 255 if map.paint[k] == TerrainMap.PAINT_PAVED else 0
	var image := Image.create_from_data(cells, cells, false, Image.FORMAT_R8, paved)
	var half := size * 0.5
	shader_material.set_shader_parameter("paint_map", ImageTexture.create_from_image(image))
	shader_material.set_shader_parameter("paint_grid", Vector4(-half, -half, _cell, cells))


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
	_feed_water(water_material)
	if water_material:
		# The water draws in the transparent pass (no ink outlines; see
		# water.gdshader): before the other see-through things, which it would
		# otherwise cover when its huge plane sorts nearer than them.
		water_material.render_priority = water_render_priority
	# Splash rings and wakes, drawn by the water shader (shared with the map's
	# lakes and rivers).
	if water_material is ShaderMaterial:
		var marks := WaterMarks.new()
		marks.name = "WaterMarks"
		marks.material = water_material
		add_child(marks)


## Gives the water shader (effects/water.gdshader) the ground heights, so it can
## colour the water by depth and put foam on the shores. The material is shared
## with the map's lakes and rivers (MapProps), so they get it too.
func _feed_water(water: Material) -> void:
	var shader_material := water as ShaderMaterial
	if shader_material == null:
		return
	var image := Image.create_from_data(_points, _points, false, Image.FORMAT_RF, _sea_floor().to_byte_array())
	# Half floats: linear filtering of full floats isn't supported everywhere.
	image.convert(Image.FORMAT_RH)
	var half := size * 0.5
	shader_material.set_shader_parameter("ground_heights", ImageTexture.create_from_image(image))
	shader_material.set_shader_parameter("ground_grid", Vector4(-half, -half, _cell, _points))
	shader_material.set_shader_parameter("has_ground", true)
	shader_material.set_shader_parameter("open_depth", open_sea_depth)


## The ground heights as the water shader should see them: as they are near
## land, sinking to open_sea_depth further out (water_depth_fade), so depth
## bands follow the coasts. Distance to land per grid point comes from a
## two-pass chamfer distance transform (straight steps 1, diagonal √2 cells).
func _sea_floor() -> PackedFloat32Array:
	var diagonal := sqrt(2.0)
	var n := _points
	var far := float(n * 2)
	var dist := PackedFloat32Array()
	dist.resize(n * n)
	for k in n * n:
		dist[k] = 0.0 if _heights[k] > sea_level else far
	# Forward pass (from the top left), then backward (from the bottom right).
	for j in n:
		for i in n:
			var k := j * n + i
			var d := dist[k]
			if i > 0:
				d = minf(d, dist[k - 1] + 1.0)
			if j > 0:
				d = minf(d, dist[k - n] + 1.0)
				if i > 0:
					d = minf(d, dist[k - n - 1] + diagonal)
				if i < n - 1:
					d = minf(d, dist[k - n + 1] + diagonal)
			dist[k] = d
	for j in range(n - 1, -1, -1):
		for i in range(n - 1, -1, -1):
			var k := j * n + i
			var d := dist[k]
			if i < n - 1:
				d = minf(d, dist[k + 1] + 1.0)
			if j < n - 1:
				d = minf(d, dist[k + n] + 1.0)
				if i < n - 1:
					d = minf(d, dist[k + n + 1] + diagonal)
				if i > 0:
					d = minf(d, dist[k + n - 1] + diagonal)
			dist[k] = d
	var floor_heights := _heights.duplicate()
	var open_floor := sea_level - open_sea_depth
	for k in n * n:
		var fade := smoothstep(water_depth_fade.x, water_depth_fade.y, dist[k] * _cell)
		floor_heights[k] = lerpf(_heights[k], minf(_heights[k], open_floor), fade)
	return floor_heights


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


## The scenery beyond the map's edge (see `backdrop`). Rings of vertices round
## squares centred on the map: the first lies on the map's own grid line
## `backdrop_inset` in from the edge, sharing its vertices, so the seam is exact
## and the map's sinking border passes under the backdrop; the rest lie on
## ever bigger squares, the same number of vertices on each. One mesh per side,
## so each is culled on its own; no collision.
func _build_backdrop() -> void:
	var cells := _points - 1
	var inset := clampi(int(round(backdrop_inset / _cell)), 0, cells / 2 - 1)
	var per_side := cells - 2 * inset
	var around := 4 * per_side
	var inner_half := size * 0.5 - inset * _cell

	# The map's heights along the first ring, as they are and smoothed.
	var rim := PackedFloat32Array()
	rim.resize(around)
	for p in around:
		var g := _rim_grid_point(p, per_side, inset)
		rim[p] = _height(g.x, g.y)
	var radius := maxi(int(round(backdrop_smoothing * 0.5 / _cell)), 1)
	var smooth := _blur_loop(_blur_loop(rim, radius), radius)
	# How much of the edge around each point is land (0..1).
	var land_rim := PackedFloat32Array()
	land_rim.resize(around)
	for p in around:
		land_rim[p] = 1.0 if smooth[p] > sea_level + backdrop_land_height else 0.0
	var coast_radius := maxi(int(round(backdrop_coast_smoothing * 0.5 / _cell)), 1)
	var land_share := _blur_loop(_blur_loop(land_rim, coast_radius), coast_radius)

	# Ring distances past the first ring, coarser further out.
	var distances := PackedFloat32Array([0.0])
	var step := backdrop_first_step
	while distances[-1] < backdrop_reach + inset * _cell:
		distances.append(distances[-1] + step)
		step *= backdrop_step_growth
	var rings := distances.size()

	var noise := FastNoiseLite.new()
	noise.seed = terrain_seed + 3
	noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	noise.frequency = 1.0 / backdrop_scale
	noise.fractal_type = FastNoiseLite.FRACTAL_FBM
	noise.fractal_octaves = 3
	var coast_noise := FastNoiseLite.new()
	coast_noise.seed = terrain_seed + 4
	coast_noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	coast_noise.frequency = 1.0 / backdrop_scale
	coast_noise.fractal_type = FastNoiseLite.FRACTAL_FBM
	coast_noise.fractal_octaves = 2

	var vertices := PackedVector3Array()
	vertices.resize(rings * around)
	for r in rings:
		var d := distances[r]
		for p in around:
			var flat := _ring_point(p, per_side, inner_half + d)
			var height := rim[p]
			if r > 0:
				# The edge carried outward (smoothed after a while)...
				var edge := lerpf(rim[p], smooth[p], smoothstep(0.0, backdrop_smoothing, d))
				# ...becoming mountains where the edge is land, sea floor where it's sea.
				var crest := 1.0 - absf(noise.get_noise_2d(flat.x, flat.y))
				var ridge := smoothstep(backdrop_crest, 1.0, crest)
				var mountains := sea_level + backdrop_base + backdrop_height * ridge
				var coast := land_share[p] + coast_noise.get_noise_2d(flat.x, flat.y) * backdrop_coast_wobble
				var land := smoothstep(0.3, 0.7, coast)
				var far := lerpf(minf(smooth[p], sea_level - 10.0), mountains, land)
				height = lerpf(edge, far, smoothstep(0.0, backdrop_blend, d))
			vertices[r * around + p] = Vector3(flat.x, height, flat.y)

	# Two triangles per quad between rings, wound so they face up; area-weighted
	# smooth normals from all of them.
	var triangles := PackedInt32Array()
	var normals := PackedVector3Array()
	normals.resize(vertices.size())
	for r in rings - 1:
		for p in around:
			var a := r * around + p
			var b := r * around + (p + 1) % around
			var c := b + around
			var e := a + around
			for tri: PackedInt32Array in [PackedInt32Array([a, b, c]), PackedInt32Array([a, c, e])]:
				# Godot's front face is clockwise seen from above, where
				# (1 - 0) x (2 - 0) points down.
				var down := (vertices[tri[1]] - vertices[tri[0]]).cross(vertices[tri[2]] - vertices[tri[0]])
				if down.y > 0.0:
					down = -down
					tri = PackedInt32Array([tri[0], tri[2], tri[1]])
				for k in tri:
					normals[k] -= down
				triangles.append_array(tri)
	for k in normals.size():
		normals[k] = normals[k].normalized()
	# On the seam, the map's own normals, so the light bands carry across it.
	for p in around:
		var g := _rim_grid_point(p, per_side, inset)
		normals[p] = _grid_normal(g.x, g.y)

	# Split into one mesh per side (each quad belongs to the side its first
	# vertex is on), dropping triangles wholly under the sea.
	var meshes: Array[SurfaceTool] = []
	for side in 4:
		var tool := SurfaceTool.new()
		tool.begin(Mesh.PRIMITIVE_TRIANGLES)
		meshes.append(tool)
	var under := sea_level - 2.0
	for t in range(0, triangles.size(), 3):
		var tri := triangles.slice(t, t + 3)
		if vertices[tri[0]].y < under and vertices[tri[1]].y < under and vertices[tri[2]].y < under:
			continue
		var tool := meshes[(triangles[t] % around) / per_side]
		for k in tri:
			tool.set_normal(normals[k])
			tool.add_vertex(vertices[k])
	for side in 4:
		meshes[side].index()
		var mesh_instance := MeshInstance3D.new()
		mesh_instance.name = "Backdrop%d" % side
		mesh_instance.mesh = meshes[side].commit()
		mesh_instance.material_override = material
		mesh_instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(mesh_instance)


## The grid point (i, j) under vertex `p` of the backdrop's first ring, going
## round the square: north side west to east, then east, south, west.
func _rim_grid_point(p: int, per_side: int, inset: int) -> Vector2i:
	var k := p % per_side
	var far := _points - 1 - inset
	match p / per_side:
		0:
			return Vector2i(inset + k, inset)
		1:
			return Vector2i(far, inset + k)
		2:
			return Vector2i(far - k, far)
	return Vector2i(inset, far - k)


## Vertex `p` of a backdrop ring on the square of half-width `half` (x, z),
## in the same order as _rim_grid_point().
func _ring_point(p: int, per_side: int, half: float) -> Vector2:
	var corners := [Vector2(-half, -half), Vector2(half, -half), Vector2(half, half), Vector2(-half, half)]
	var side := p / per_side
	var u := float(p % per_side) / per_side
	return (corners[side] as Vector2).lerp(corners[(side + 1) % 4], u)


## `values` averaged over `radius` neighbours either side, wrapping round.
func _blur_loop(values: PackedFloat32Array, radius: int) -> PackedFloat32Array:
	var n := values.size()
	var blurred := PackedFloat32Array()
	blurred.resize(n)
	var sum := 0.0
	for k in range(-radius, radius + 1):
		sum += values[posmod(k, n)]
	for i in n:
		blurred[i] = sum / (2 * radius + 1)
		sum += values[posmod(i + radius + 1, n)] - values[posmod(i - radius, n)]
	return blurred


## A thin solid box whose top is at `top`.
func _slab(extent: Vector2, top: float) -> CollisionShape3D:
	var box := BoxShape3D.new()
	box.size = Vector3(extent.x, 2.0, extent.y)
	var collision := CollisionShape3D.new()
	collision.shape = box
	collision.position.y = top - 1.0
	return collision
