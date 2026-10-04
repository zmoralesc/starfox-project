class_name Destroyer
extends AnimatableBody3D
## Capital ship. Fades in at the edge of the zone, crawls towards the middle
## and launches fighter squadrons from its two hangars.
##
## It's built from DestroyerPart children: one bridge, three thrusters, hull
## turrets and two hangar doors. Destroying the bridge AND every thruster kills
## it. Turrets and doors just stop working when destroyed. Losing thrusters
## slows it down.
##
## The hull itself (this body) is on the World layer: it stops all shots,
## blocks line of sight and is solid. A grid of ObstacleProxy spheres filling
## hull_outline lets the AI steer around it.
##
## The model is built in Blender by models/destroyer/source/build_destroyer.py
## (one .glb for the hull, one per part type); its materials are cel-shaded at
## load (ToonMaterial).

signal destroyed

@export_group("Hull shape")
## The hull's outline seen from above, as (x, z) points in this node's space
## (-Z is the bow), matching the model. Avoidance spheres fill it and death
## explosions are scattered inside it. Gaps in the outline (between the prongs)
## stay open.
@export var hull_outline := PackedVector2Array()
## Height of the avoidance spheres' centres, and their radius...
@export var proxy_height := -2.0
@export var proxy_radius := 16.0
## ...and their spacing across (x) and along (z) the hull.
@export var proxy_spacing := Vector2(20.0, 25.0)
## Extra spheres for parts that stand out of the hull outline (the bridge
## tower, hangar housings): local position in xyz, radius in w.
@export var extra_proxies: Array[Vector4] = []

@export_group("Behaviour")
@export var cruise_speed := 8.0
## Stops this far from its destination (the middle of the zone).
@export var stop_distance := 200.0
@export var fade_in_time := 4.0
@export var fade_out_time := 1.5
@export var launch_interval := 40.0
## Delay between finishing the fade-in and the first launch.
@export var first_launch_delay := 15.0
@export var squadron_size := 3
@export var fighter_scene: PackedScene = preload("res://enemies/enemy_fighter.tscn")
@export var kill_score := 10
## Played with the explosions along the hull as it dies, and for the final blast.
@export var explosion_sound: AudioStream = preload("res://audio/sfx/explosion_medium.mp3")

## Set by the EnemySpawner; used for the global fighter limit.
var spawner: EnemySpawner
var bridge: DestroyerPart
var thrusters: Array[DestroyerPart] = []
var turrets: Array[DestroyerTurret] = []
var hangars: Array[DestroyerHangar] = []
## Seconds since arrive() was called. Read by the HUD for the warning.
var age := 0.0

var _destination := Vector3.ZERO
var _active := false
var _dying := false
var _launch_timer := 0.0
var _next_hangar := 0
var _proxies: Array[ObstacleProxy] = []
## hull_outline's bounding rectangle (x, z).
var _hull_bounds := Rect2()
var _meshes: Array[GeometryInstance3D] = []
var _lights: Dictionary = {}  # Light3D -> full energy


func _ready() -> void:
	add_to_group("destroyer")
	# We move and turn it ourselves; with sync on, the physics server would
	# overwrite transforms set outside the physics step (e.g. in arrive()).
	sync_to_physics = false
	for part in all_parts():
		part.destroyer = self
		part.destroyed.connect(_on_part_destroyed)
		match part.kind:
			DestroyerPart.Kind.BRIDGE:
				bridge = part
			DestroyerPart.Kind.THRUSTER:
				thrusters.append(part)
			DestroyerPart.Kind.TURRET:
				turrets.append(part as DestroyerTurret)
			DestroyerPart.Kind.HANGAR:
				hangars.append(part as DestroyerHangar)
	_hull_bounds = Rect2(hull_outline[0], Vector2.ZERO) if not hull_outline.is_empty() else Rect2()
	for point in hull_outline:
		_hull_bounds = _hull_bounds.expand(point)
	_build_obstacle_proxies()
	# Cel-shade the imported models' materials to match the rest of the game.
	ToonMaterial.convert_tree(self)
	_collect_visuals(self)
	_set_visibility(0.0)


## Start the approach towards `destination`, fading in on the way.
func arrive(destination: Vector3) -> void:
	_destination = destination
	var flat := destination - global_position
	flat.y = 0.0
	if flat.length() > 1.0:
		look_at(global_position + flat, Vector3.UP)
	age = 0.0
	var tween := create_tween()
	tween.tween_method(_set_visibility, 0.0, 1.0, fade_in_time)
	tween.tween_callback(_activate)


## Turrets fire, hangars launch and parts take damage only while this is true.
func is_vulnerable() -> bool:
	return _active and not _dying


func all_parts() -> Array[DestroyerPart]:
	var parts: Array[DestroyerPart] = []
	_find_parts(self, parts)
	return parts


func intact_count(parts: Array) -> int:
	return parts.filter(func(p: DestroyerPart) -> bool: return not p.is_destroyed).size()


func _activate() -> void:
	_active = true
	_launch_timer = first_launch_delay


func _physics_process(delta: float) -> void:
	age += delta
	if _dying:
		return
	var to_destination := _destination - global_position
	to_destination.y = 0.0
	var remaining := to_destination.length() - stop_distance
	if remaining > 0.0:
		# Fewer working thrusters, slower ship (but it never quite stops).
		var thrust := float(intact_count(thrusters)) / maxf(thrusters.size(), 1)
		var step := minf(cruise_speed * (0.25 + 0.75 * thrust) * delta, remaining)
		global_position += -global_basis.z * step
		_smash_asteroids()
	if _active:
		_update_launches(delta)


func _update_launches(delta: float) -> void:
	_launch_timer -= delta
	if _launch_timer > 0.0:
		return
	if _try_launch():
		_launch_timer = launch_interval
	else:
		_launch_timer = 5.0  # no room or no hangar ready: check again soon


## Launch one squadron from the next working hangar, within the fighter limit.
func _try_launch() -> bool:
	var room := spawner.fighter_room() if spawner else squadron_size
	var count := mini(squadron_size, room)
	if count <= 0:
		return false
	for i in hangars.size():
		var hangar := hangars[(_next_hangar + i) % hangars.size()]
		if hangar.can_launch():
			_next_hangar = (_next_hangar + i + 1) % hangars.size()
			hangar.launch(count, fighter_scene, spawner)
			return true
	return false


func _on_part_destroyed() -> void:
	if _dying or bridge == null:
		return
	if bridge.is_destroyed and intact_count(thrusters) == 0:
		_die()


func _die() -> void:
	_dying = true
	get_tree().call_group("hud", "add_score", kill_score)
	# A chain of explosions along the hull, a final blast, then fade away.
	for i in 14:
		var spot := _random_hull_point()
		var local := Vector3(spot.x, randf_range(0.0, 30.0), spot.y)
		Impact.spawn(get_tree().current_scene, global_transform * local, Color(1.0, 0.55, 0.2), randf_range(22.0, 45.0))
		# Every other blast, lower and slower than a fighter's: it's a big ship.
		if i % 2 == 0:
			SoundFX.play_at(get_tree().current_scene, explosion_sound, global_transform * local, 0.0, randf_range(0.6, 0.8))
		await get_tree().create_timer(0.22, false).timeout
		if not is_inside_tree():
			return
	Impact.spawn(get_tree().current_scene, global_transform * Vector3(0, 15, 45), Color(1.0, 0.75, 0.4), 105.0)
	SoundFX.play_at(get_tree().current_scene, explosion_sound, global_transform * Vector3(0, 15, 45), 4.0, 0.5)
	var tween := create_tween()
	tween.tween_method(_set_visibility, 1.0, 0.0, fade_out_time)
	await tween.finished
	destroyed.emit()
	queue_free()


## A random (x, z) point on the hull, inside hull_outline (in from its edges
## a little, so blasts sit on the hull rather than beside it).
func _random_hull_point() -> Vector2:
	var inner := Rect2(_hull_bounds.get_center() - _hull_bounds.size * 0.4, _hull_bounds.size * 0.8)
	for attempt in 30:
		var point := Vector2(randf_range(inner.position.x, inner.end.x), randf_range(inner.position.y, inner.end.y))
		if Geometry2D.is_point_in_polygon(point, hull_outline):
			return point
	return _hull_bounds.get_center()


## Asteroids in the way get smashed (no score for the player).
func _smash_asteroids() -> void:
	# Only rocks within reach of the hull are worth checking against every sphere.
	var reach := _hull_bounds.size.length() * 0.5 + 20.0
	for node in get_tree().get_nodes_in_group("obstacles"):
		var asteroid := node as Asteroid
		if asteroid == null or asteroid.health <= 0:
			continue
		if global_position.distance_to(asteroid.global_position) > reach + asteroid.radius:
			continue
		for proxy in _proxies:
			if proxy.global_position.distance_to(asteroid.global_position) < proxy.radius + asteroid.radius * 0.85:
				asteroid.shatter()
				break


## Cover the hull with spheres so AI ships steer around its real shape: a grid
## over hull_outline (symmetric about the centre line), keeping only points
## inside it, plus extra_proxies and one per thruster.
func _build_obstacle_proxies() -> void:
	var z := _hull_bounds.position.y + proxy_spacing.y * 0.5
	while z <= _hull_bounds.end.y:
		var x := 0.0
		while x <= _hull_bounds.end.x:
			for side: float in ([1.0] if x == 0.0 else [1.0, -1.0]):
				if Geometry2D.is_point_in_polygon(Vector2(x * side, z), hull_outline):
					_add_proxy(Vector3(x * side, proxy_height, z), proxy_radius)
			x += proxy_spacing.x
		z += proxy_spacing.y
	for extra in extra_proxies:
		_add_proxy(Vector3(extra.x, extra.y, extra.z), extra.w)
	for thruster in thrusters:
		_add_proxy(thruster.position, thruster.radius)


func _add_proxy(local_position: Vector3, sphere_radius: float) -> void:
	var proxy := ObstacleProxy.new()
	proxy.radius = sphere_radius
	proxy.position = local_position
	add_child(proxy)
	_proxies.append(proxy)


func _find_parts(node: Node, out: Array[DestroyerPart]) -> void:
	for child in node.get_children():
		if child is DestroyerPart:
			out.append(child)
		_find_parts(child, out)


func _collect_visuals(node: Node) -> void:
	for child in node.get_children():
		if child is GeometryInstance3D:
			_meshes.append(child)
		elif child is Light3D:
			_lights[child] = (child as Light3D).light_energy
		_collect_visuals(child)


## 0 = invisible, 1 = fully solid. Used for the fade in and out.
func _set_visibility(amount: float) -> void:
	for mesh in _meshes:
		if is_instance_valid(mesh):
			mesh.transparency = 1.0 - amount
	for light: Light3D in _lights:
		if is_instance_valid(light):
			light.light_energy = _lights[light] * amount
