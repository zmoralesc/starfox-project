class_name WaterMarks
extends Node
## Foam drawn on the water by things happening on it: rings where bolts
## splashed (add_ring(), from WaterSplash) and the wakes of ships skimming
## the surface (track(), from WaterWake). Keeps them in fixed-size lists and
## hands them to the water shader (effects/water.gdshader, its `marks`
## uniforms) every frame, which draws the foam per pixel.
##
## Terrain adds one when it has a water material (the sea's, shared with a
## map's lakes and rivers, so they get marks too). Find it with find().
## Pauses with the game (its clock stops, so the foam holds still).

## Sizes of the shader's arrays (`rings[32]`, `wake[192]`); change both together.
const MAX_RINGS := 32
const MAX_WAKE_POINTS := 192

## Seconds a ring lasts and a wake point lasts: match the shader's ring_life
## and wake_life (used here to drop old ones).
@export var ring_life := 1.2
@export var wake_life := 3.5
## A wake trail gets a point every this many metres; up to this many points
## per trail (older ones are dropped), and up to this many trails at once.
@export var wake_spacing := 10.0
@export var wake_points_per_trail := 24
@export var max_trails := 8
## Below this strength a ship leaves no wake (its trail ends there).
@export var wake_min_strength := 0.02

var material: ShaderMaterial

var _time := 0.0
## Rings: Vector4(x, z, start time, size), oldest first.
var _rings: Array[Vector4] = []
## Trails, oldest first: {ship: instance id, points: Array[Vector4] (x, z,
## time, strength), head: Vector4 or null (the ship's current spot, not yet a
## point), last: time it was last updated, live: whether it's still being
## laid}. A ship that leaves the water and comes back starts a new one, so its
## old wake fades out on its own.
var _trails: Array[Dictionary] = []
## The trail each ship is laying now, by instance id.
var _live := {}


## The level's WaterMarks, or null (no water, or space).
static func find(tree: SceneTree) -> WaterMarks:
	return tree.get_first_node_in_group("water_marks") as WaterMarks


func _enter_tree() -> void:
	add_to_group("water_marks")


## A ring of foam spreading from `at` (on the water), `size` times the
## shader's ring_radius.
func add_ring(at: Vector3, size := 1.0) -> void:
	_rings.append(Vector4(at.x, at.z, _time, size))
	if _rings.size() > MAX_RINGS:
		_rings.pop_front()


## Lays `ship`'s wake: call every physics frame it's over water with its
## position and strength (0..1). A strength under wake_min_strength ends the
## trail; the next strong one starts a new one.
func track(ship: Object, at: Vector3, strength: float) -> void:
	var key := ship.get_instance_id()
	var trail: Dictionary = _live.get(key, {})
	if strength < wake_min_strength:
		if not trail.is_empty():
			_end_trail(trail)
		return
	if trail.is_empty():
		if _trails.size() >= max_trails:
			return
		trail = {ship = key, points = [] as Array[Vector4], head = null, last = _time, live = true}
		_trails.append(trail)
		_live[key] = trail
	var point := Vector4(at.x, at.z, _time, strength)
	var points: Array[Vector4] = trail.points
	if points.is_empty() or Vector2(at.x, at.z).distance_to(Vector2(points[-1].x, points[-1].y)) >= wake_spacing:
		points.append(point)
		if points.size() > wake_points_per_trail:
			points.pop_front()
		trail.head = null
	else:
		trail.head = point
	trail.last = _time


func _end_trail(trail: Dictionary) -> void:
	if trail.head != null:
		(trail.points as Array[Vector4]).append(trail.head)
		trail.head = null
	trail.live = false
	_live.erase(trail.ship)


func _process(delta: float) -> void:
	_time += delta
	if material == null:
		return
	while not _rings.is_empty() and _time - _rings[0].z > ring_life:
		_rings.pop_front()
	_push_rings()
	_push_wake()
	material.set_shader_parameter("marks_time", _time)


func _push_rings() -> void:
	var data := PackedVector4Array()
	var box := Rect2()
	for ring in _rings:
		data.append(ring)
		box = Rect2(ring.x, ring.y, 0.0, 0.0) if data.size() == 1 else box.expand(Vector2(ring.x, ring.y))
	data.resize(MAX_RINGS)
	material.set_shader_parameter("rings", data)
	material.set_shader_parameter("ring_count", _rings.size())
	material.set_shader_parameter("ring_bounds", Vector4(box.position.x, box.position.y, box.end.x, box.end.y))


## All trails in one list, oldest point first in each; the first point of
## each trail gets a negative strength (the shader's "new trail" mark).
func _push_wake() -> void:
	var data := PackedVector4Array()
	var box := Rect2()
	for trail: Dictionary in _trails.duplicate():
		var points: Array[Vector4] = trail.points
		# Ships gone or off the water stop updating: end their trails, and drop
		# them once aged out.
		if trail.live and _time - trail.last > 0.5:
			_end_trail(trail)
		if not trail.live and (points.is_empty() or _time - points[-1].z > wake_life):
			_trails.erase(trail)
			continue
		while points.size() > 1 and _time - points[1].z > wake_life:
			points.pop_front()
		var all := points.duplicate()
		if trail.head != null:
			all.append(trail.head)
		if all.size() < 2 or data.size() + all.size() > MAX_WAKE_POINTS:
			continue
		for i in all.size():
			var p: Vector4 = all[i]
			if i == 0:
				p.w = -maxf(p.w, 0.001)
			data.append(p)
			box = Rect2(p.x, p.y, 0.0, 0.0) if data.size() == 1 else box.expand(Vector2(p.x, p.y))
	var count := data.size()
	data.resize(MAX_WAKE_POINTS)
	material.set_shader_parameter("wake", data)
	material.set_shader_parameter("wake_count", count)
	material.set_shader_parameter("wake_bounds", Vector4(box.position.x, box.position.y, box.end.x, box.end.y))
