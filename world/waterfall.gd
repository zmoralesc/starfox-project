@tool
class_name Waterfall
extends Node3D
## The Corneria waterfall: a sheet of water pouring off a cliff, built here and
## animated by its shader (effects/waterfall.gdshader), with mist billowing up
## at its foot and foam rings spreading on the water below. Scenery: no
## collision, so bolts and ships pass through it.
##
## The node sits on the lip, on the river's surface, the water flowing along
## its local +Z and dropping `drop` metres. Its place comes from the map script
## (models/corneria/source/build_corneria.py writes models/corneria/waterfall.txt
## on export): paste that transform here when the river or cliff moves. The
## sheet shows in the editor; the mist and rings only in the game.

const GRAVITY := 9.8

@export_group("Shape")
## Width at the lip and at the foot (metres).
@export var width_top := 80.0:
	set(value):
		width_top = value
		_rebuild()
@export var width_bottom := 88.0:
	set(value):
		width_bottom = value
		_rebuild()
## How far it falls: from the lip to a little under the water at the foot.
@export var drop := 125.0:
	set(value):
		drop = value
		_rebuild()
## How far out from the lip it lands. The sheet follows the arc water thrown
## off the lip at that speed would: steep at first, bowing outwards.
@export var reach := 32.0:
	set(value):
		reach = value
		_rebuild()
## How far back up the river the sheet starts, lying on the water, so the
## river visibly speeds up and pours over rather than ending at a hard edge.
@export var run_up := 18.0:
	set(value):
		run_up = value
		_rebuild()
## How thick the water is (metres, at the middle; it tapers to nothing at the
## sides, so its cross-section is a lens): at the lip, about the river's depth
## there (so the river visibly pours over in one body), and at the foot.
@export var thickness_top := 11.0:
	set(value):
		thickness_top = value
		_rebuild()
@export var thickness_bottom := 7.0:
	set(value):
		thickness_bottom = value
		_rebuild()
## Mesh resolution: rows down the drop, columns across.
@export var rows := 48:
	set(value):
		rows = value
		_rebuild()
@export var columns := 16:
	set(value):
		columns = value
		_rebuild()
## The sheet's look (colours, streaks, gaps): a waterfall.gdshader material.
@export var material: ShaderMaterial:
	set(value):
		material = value
		if _sheet:
			_sheet.material_override = value

@export_group("Mist")
## Toon puffs billowing up where the water lands: puffs a second, how long
## each lasts, and its size from birth to full grown (metres).
@export var mist_rate := 9.0
@export var mist_lifetime := 3.5
@export var mist_size := Vector2(10.0, 32.0)
## How fast they drift off (m/s), in a cone this wide (degrees), leaning this
## far from straight up towards downstream (degrees).
@export var mist_drift := 9.0
@export var mist_spread := 45.0
@export var mist_lean := 35.0
## How far they're scattered from the foot's centre, out of the foot's half
## width (across) and in metres (along the flow).
@export_range(0.0, 1.0) var mist_scatter_across := 0.8
@export var mist_scatter_along := 10.0
@export var mist_color := Color(0.93, 0.96, 1.0)

@export_group("Foam rings")
## Foam rings (WaterMarks) spreading on the water at the foot: rings a second,
## their size (WaterMarks.add_ring()'s `size`, random between the two), and
## the area they land in, across × downstream (metres).
@export var ring_rate := 3.0
@export var ring_size := Vector2(3.0, 6.0)
@export var ring_area := Vector2(90.0, 40.0)

var _sheet: MeshInstance3D
var _mist: GPUParticles3D
var _rings_owed := 0.0


func _ready() -> void:
	_rebuild()
	if Engine.is_editor_hint():
		return
	_mist = _make_mist()
	add_child(_mist)


func _process(delta: float) -> void:
	if Engine.is_editor_hint() or ring_rate <= 0.0:
		return
	var marks := WaterMarks.find(get_tree())
	if marks == null:
		return
	_rings_owed += ring_rate * delta
	while _rings_owed >= 1.0:
		_rings_owed -= 1.0
		var local := foot() + Vector3(randf_range(-0.5, 0.5) * ring_area.x, 0.0, randf_range(0.0, ring_area.y))
		var at := to_global(local)
		var terrain := get_tree().get_first_node_in_group("terrain") as Terrain
		if terrain:
			at.y = terrain.water_level_at(at.x, at.z)
		marks.add_ring(at, randf_range(ring_size.x, ring_size.y))


## Where the water lands, in this node's space.
func foot() -> Vector3:
	return Vector3(0.0, -drop, reach)


## Builds the water's body along the arc, plus the run-up: a front surface
## (its middle on the arc) and a back one, `columns` × rows each, meeting at
## the sides, so its cross-section is a lens `thickness` deep.
func _rebuild() -> void:
	if not is_inside_tree():
		return
	if _sheet == null:
		_sheet = MeshInstance3D.new()
		_sheet.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(_sheet)
	_sheet.material_override = material
	# Thrown off the lip at `speed` m/s: z = speed × t, y = −½ g t².
	var fall_time := sqrt(2.0 * drop / GRAVITY)
	var speed := reach / fall_time
	var run_up_time := run_up / maxf(speed, 0.1)
	var run_up_rows := maxi(int(rows / 8.0), 2)
	var times: Array[float] = []
	for i in run_up_rows:
		times.append(-run_up_time * (1.0 - float(i) / run_up_rows))
	for i in rows + 1:
		# Denser at the top, where the curve bends most.
		var k := float(i) / rows
		times.append(fall_time * k * k * 0.4 + fall_time * k * 0.6)

	var surface := SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	for side: float in [1.0, -1.0]:  # front, back
		for t in times:
			var y := -0.5 * GRAVITY * t * t if t > 0.0 else 0.0
			var z := speed * t
			var fall := clampf(-y / drop, 0.0, 1.0)
			var half_width := lerpf(width_top, width_bottom, fall) * 0.5
			var half_depth := lerpf(thickness_top, thickness_bottom, fall) * 0.5
			# Across the flow, and out of the water (away from the cliff).
			var along := Vector3(0.0, -GRAVITY * maxf(t, 0.0), speed).normalized()
			var out := along.cross(Vector3.RIGHT)
			var centre := Vector3(0.0, y, z) - out * half_depth
			# The run-up fades in from nothing, over the river's own water.
			var fade := smoothstep(-run_up_time, -run_up_time * 0.4, t)
			for j in columns + 1:
				var u := float(j) / columns
				var s := u * 2.0 - 1.0
				var bulge := sqrt(maxf(1.0 - s * s, 0.0)) * half_depth * side
				# The lens's own normal: the ellipse's (s / a², bulge / b²).
				var normal := (Vector3.RIGHT * s / half_width + out * bulge / (half_depth * half_depth)).normalized()
				surface.set_uv(Vector2(u, t))
				surface.set_uv2(Vector2(fall, 0.0 if side > 0.0 else 1.0))
				surface.set_color(Color(1.0, 1.0, 1.0, fade))
				surface.set_normal(normal)
				surface.add_vertex(centre + Vector3.RIGHT * s * half_width + out * bulge)
	var stride := columns + 1
	var per_side := times.size() * stride
	for side in 2:
		for r in times.size() - 1:
			for j in columns:
				var a := side * per_side + r * stride + j
				surface.add_index(a)
				surface.add_index(a + 1)
				surface.add_index(a + stride)
				surface.add_index(a + 1)
				surface.add_index(a + stride + 1)
				surface.add_index(a + stride)
	_sheet.mesh = surface.commit()


func _make_mist() -> GPUParticles3D:
	var style := ExplosionStyle.new()
	style.smoke_color = mist_color
	var mist := Explosion.trail(style, mist_rate, mist_lifetime, mist_size.x, mist_size.y,
		0.001, 0.5, 0.0, mist_drift, mist_spread)
	# Along the whole foot, not in a ball at its middle.
	var process := mist.process_material as ParticleProcessMaterial
	process.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	process.emission_box_extents = Vector3(width_bottom * 0.5 * mist_scatter_across, mist_size.x * 0.2,
		mist_scatter_along)
	mist.name = "Mist"
	mist.position = foot()
	# On the water (the sheet's foot is under it), a little up.
	var terrain := get_tree().get_first_node_in_group("terrain") as Terrain
	if terrain:
		var at := to_global(foot())
		mist.position.y = to_local(Vector3(at.x, terrain.water_level_at(at.x, at.z), at.z)).y
	mist.position.y += mist_size.x * 0.3
	# Puffs go out along +Y: tip it downstream.
	mist.rotation = Vector3(deg_to_rad(mist_lean), 0.0, 0.0)
	# Already billowing when the level starts.
	mist.preprocess = mist_lifetime
	return mist
