class_name Destroyer
extends AnimatableBody3D
## Capital ship. Comes out of a warp portal beyond the edge of the zone (or,
## with warp_in off, fades in at the edge), crawls towards the middle and
## launches fighter squadrons from its two hangars.
##
## Warp arrival: the portal (WarpPortal) opens, the bow comes through at
## warp_speed, and once the stern is out the portal shuts and the ship brakes
## to cruise speed. Until it's through, the hull behind the portal is hidden
## (a clip plane, toon_clip.gdshader) and nothing collides; its parts can be
## shot once it's through, and it becomes active (turrets, hangars, solid
## hull) when it has slowed down.
##
## It's built from DestroyerPart children: one bridge, three thrusters, hull
## turrets and two hangar doors. Destroying the bridge AND every thruster kills
## it. Turrets and doors just stop working when destroyed. Losing thrusters
## slows it down.
##
## The hull itself (this body) is on the World layer: it stops all shots,
## blocks line of sight and is solid. A grid of ObstacleProxy spheres filling
## hull_outline (and any extra_proxies or obstacle_boxes) lets the AI steer
## around it.
##
## The model is built in Blender by models/destroyer/source/build_destroyer.py
## (one .glb for the hull, one per part type); its materials are cel-shaded at
## load (ToonMaterial).

signal destroyed

const TOON := preload("res://effects/toon.gdshader")
const TOON_CLIP := preload("res://effects/toon_clip.gdshader")
## Clip-plane copies of toon materials, shared by every destroyer.
static var _clip_copies := {}
## Trimesh shapes built from hull models (hull_collision_from_model), by mesh,
## shared by every destroyer.
static var _hull_shapes := {}

@export_group("Hull shape")
## Build the hull's collision from the triangles of the `Hull` model at load,
## so it matches the model exactly (for hand-made models), in addition to any
## CollisionShape3D children.
@export var hull_collision_from_model := false
## The hull's outline seen from above, as (x, z) points in this node's space
## (-Z is the bow), matching the model. Avoidance spheres fill it and death
## explosions are scattered inside it. Gaps in the outline (between the prongs)
## stay open.
@export var hull_outline := PackedVector2Array()
## Height of the avoidance spheres' centres, and their radius (0 = no grid
## over hull_outline: only extra_proxies and the thrusters' spheres)...
@export var proxy_height := -2.0
@export var proxy_radius := 16.0
## ...and their spacing across (x) and along (z) the hull.
@export var proxy_spacing := Vector2(20.0, 25.0)
## Extra spheres for parts that stand out of the hull outline (the bridge
## tower, hangar housings): local position in xyz, radius in w.
@export var extra_proxies: Array[Vector4] = []
## Avoidance boxes (ObstacleBox) in this node's space, for hulls that spheres
## fit badly: the AI keeps box_margin (plus its own avoid_margin) from their
## faces. The thrusters keep their spheres either way.
@export var obstacle_boxes: Array[AABB] = []
@export var box_margin := 10.0

@export_group("Behaviour")
@export var cruise_speed := 8.0
## Stops this far from its destination (the middle of the zone).
@export var stop_distance := 200.0
## Fade-in when warp_in is off.
@export var fade_in_time := 4.0
@export var fade_out_time := 1.5
@export var launch_interval := 40.0
## Delay between becoming active (slowed down after the warp, or faded in)
## and the first launch.
@export var first_launch_delay := 15.0
@export var squadron_size := 3
@export var fighter_scene: PackedScene = preload("res://enemies/enemy_fighter.tscn")
@export var kill_score := 10
## Played with the explosions along the hull as it dies, and for the final blast.
@export var explosion_sound: AudioStream = preload("res://audio/sfx/explosion_medium.mp3")

@export_group("Warp in")
## Arrive through a warp portal. Off: fade in where the spawner put it.
@export var warp_in := true
## The portal opens this far (m) beyond where the spawner placed the ship (the
## edge of the zone, EnemySpawner.zone_radius), just outside the play area.
## The ship comes through and brakes inside it, on its way to stop_distance.
@export var portal_margin := 50.0
## Portal radius (m), and the height of its centre above the ship's origin
## (m): sized to the hull's cross-section.
@export var portal_radius := 230.0
@export var portal_height := 30.0
## Seconds between the portal starting to open and the bow coming through.
@export var warp_charge_time := 1.0
## Speed (m/s) coming through, kept until the stern is out.
@export var warp_speed := 100.0
## Seconds to slow from warp_speed to cruise speed once out.
@export var warp_brake_time := 5.0

@export_group("Death")
## The chain of blasts along the hull when it dies: up to this high above the
## hull's base (m)...
@export var death_blast_height := 60.0
## ...each this big (random in min..max, fireball radius in m)...
@export var death_blast_size := Vector2(44.0, 90.0)
## ...in this style.
@export var death_blast_style: ExplosionStyle = preload("res://effects/explosions/destroyer_chain.tres")
## Then one big blast here (local space) of this size.
@export var final_blast_position := Vector3(0.0, 30.0, 90.0)
@export var final_blast_size := 210.0
@export var final_blast_style: ExplosionStyle = preload("res://effects/explosions/destroyer_final.tres")

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
var _boxes: Array[ObstacleBox] = []
## hull_outline's bounding rectangle (x, z).
var _hull_bounds := Rect2()
var _meshes: Array[GeometryInstance3D] = []
var _lights: Dictionary = {}  # Light3D -> full energy

## Warp arrival: coming through the portal or braking after it.
var _warping := false
## Fully out of the portal (parts take damage from here on).
var _through := false
var _portal: WarpPortal
## The portal's plane, facing the way the ship comes out.
var _portal_plane := Plane()
var _charge_left := 0.0
var _brake_left := 0.0
## Collision layers switched off during the warp: body -> layer.
var _saved_layers := {}


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
	if hull_collision_from_model:
		_build_hull_collision()
	_build_obstacle_proxies()
	# Cel-shade the imported models' materials to match the rest of the game.
	ToonMaterial.convert_tree(self)
	_collect_visuals(self)
	_use_clip_shader()
	_set_visibility(0.0)


## Start the approach towards `destination`: through a warp portal on the far
## side of where it was placed (warp_in), or fading in where it is.
func arrive(destination: Vector3) -> void:
	_destination = destination
	_end_warp()  # in case arrive() is called again
	var flat := destination - global_position
	flat.y = 0.0
	if flat.length() > 1.0:
		look_at(global_position + flat, Vector3.UP)
	age = 0.0
	if warp_in:
		_start_warp()
		return
	var tween := create_tween()
	tween.tween_method(_set_visibility, 0.0, 1.0, fade_in_time)
	tween.tween_callback(_activate)


## Turrets fire and hangars launch only while this is true.
func is_vulnerable() -> bool:
	return _active and not _dying


## Parts take damage while this is true: once active, and already while
## braking after the warp (a head start for the player).
func is_damageable() -> bool:
	return (_active or _through) and not _dying


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
	var speed := _warp_speed(delta) if _warping else _cruise_speed()
	if remaining > 0.0:
		global_position += -global_basis.z * minf(speed * delta, remaining)
		_smash_asteroids()
	if _warping:
		_update_warp()
	if _active:
		_update_launches(delta)


## Fewer working thrusters, slower ship (but it never quite stops).
func _cruise_speed() -> float:
	var thrust := float(intact_count(thrusters)) / maxf(thrusters.size(), 1)
	return cruise_speed * (0.25 + 0.75 * thrust)


## Open the portal ahead of the bow and park the ship just behind it, hidden
## and with collision off.
func _start_warp() -> void:
	var forward := -global_basis.z
	var away := global_position - _destination
	var gate := global_position + (away.normalized() if away.length() > 1.0 else -forward) * portal_margin
	global_position = gate - forward * (_bow_extent() + 2.0)
	_portal_plane = Plane(forward, gate)
	_portal = WarpPortal.spawn(get_parent(), Transform3D(global_basis, gate + global_basis.y * portal_height),
		portal_radius)
	_warping = true
	_through = false
	_charge_left = warp_charge_time
	for body: CollisionObject3D in [self as CollisionObject3D] + all_parts():
		_saved_layers[body] = body.collision_layer
		body.collision_layer = 0
	_set_visibility(1.0)
	_set_clip(_portal_plane)
	_update_warp()


## Speed while warping in: still (the portal is opening), warp_speed until
## the stern is out, then easing down to cruise speed.
func _warp_speed(delta: float) -> float:
	if _charge_left > 0.0:
		_charge_left -= delta
		return 0.0
	if not _through:
		return warp_speed
	_brake_left -= delta
	if _brake_left <= 0.0:
		_finish_warp()
	var t := 1.0 - clampf(_brake_left / warp_brake_time, 0.0, 1.0)
	return lerpf(warp_speed, _cruise_speed(), smoothstep(0.0, 1.0, t))


## Lights come on as they pass the portal; once the stern is out the portal
## shuts, the clip plane goes and the parts become solid (and shootable).
func _update_warp() -> void:
	for light: Light3D in _lights:
		if is_instance_valid(light):
			light.light_energy = _lights[light] if _portal_plane.is_point_over(light.global_position) else 0.0
	if _through or _portal_plane.distance_to(global_position) < _stern_extent():
		return
	_through = true
	_brake_left = warp_brake_time
	if is_instance_valid(_portal):
		_portal.close()
	_set_clip(Plane())
	for part in all_parts():
		if _saved_layers.has(part):
			part.collision_layer = _saved_layers[part]
			_saved_layers.erase(part)


## Slowed down: the hull turns solid and the ship goes active.
func _finish_warp() -> void:
	_end_warp()
	_activate()


## Undo whatever the warp still has switched off (also when arrive() is called again).
func _end_warp() -> void:
	_warping = false
	if is_instance_valid(_portal):
		_portal.close()
	_portal = null
	_set_clip(Plane())
	for body: CollisionObject3D in _saved_layers:
		if is_instance_valid(body):
			body.collision_layer = _saved_layers[body]
	_saved_layers.clear()


## How far the bow and the stern (thrusters included) reach from the origin (m).
func _bow_extent() -> float:
	return -_hull_bounds.position.y


func _stern_extent() -> float:
	var stern := _hull_bounds.end.y
	for thruster in thrusters:
		stern = maxf(stern, thruster.position.z + thruster.radius)
	return stern


## Swap every toon material for its clip-plane copy (same look; the clip is
## off until _set_clip()).
func _use_clip_shader() -> void:
	for node in _meshes:
		var mesh := node as MeshInstance3D
		if mesh == null or mesh.mesh == null:
			continue
		for surface in mesh.mesh.get_surface_count():
			var material := mesh.get_active_material(surface) as ShaderMaterial
			if material == null or material.shader != TOON:
				continue
			if not _clip_copies.has(material):
				var copy := material.duplicate() as ShaderMaterial
				copy.shader = TOON_CLIP
				_clip_copies[material] = copy
			mesh.set_surface_override_material(surface, _clip_copies[material])


## Hide everything behind `plane` (an empty Plane() clips nothing).
func _set_clip(plane: Plane) -> void:
	var value := Vector4(plane.normal.x, plane.normal.y, plane.normal.z, plane.d)
	for mesh in _meshes:
		if is_instance_valid(mesh):
			mesh.set_instance_shader_parameter(&"clip_plane", value)


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
		var local := Vector3(spot.x, randf_range(0.0, death_blast_height), spot.y)
		Explosion.spawn(get_tree().current_scene, global_transform * local, death_blast_style,
			randf_range(death_blast_size.x, death_blast_size.y))
		# Every other blast, lower and slower than a fighter's: it's a big ship.
		if i % 2 == 0:
			SoundFX.play_at(get_tree().current_scene, explosion_sound, global_transform * local, 0.0, randf_range(0.6, 0.8))
		await get_tree().create_timer(0.22, false).timeout
		if not is_inside_tree():
			return
	Explosion.spawn(get_tree().current_scene, global_transform * final_blast_position, final_blast_style, final_blast_size)
	SoundFX.play_at(get_tree().current_scene, explosion_sound, global_transform * final_blast_position, 4.0, 0.5)
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
		var hit := false
		for proxy in _proxies:
			if proxy.global_position.distance_to(asteroid.global_position) < proxy.radius + asteroid.radius * 0.85:
				hit = true
				break
		for box in _boxes:
			if hit:
				break
			hit = box.contains(asteroid.global_position, asteroid.radius * 0.85)
		if hit:
			asteroid.shatter()


## Cover the hull with spheres (and boxes) so AI ships steer around its real shape: a grid
## over hull_outline (symmetric about the centre line), keeping only points
## inside it, plus extra_proxies and one per thruster; then obstacle_boxes.
func _build_obstacle_proxies() -> void:
	var z := _hull_bounds.position.y + proxy_spacing.y * 0.5
	while proxy_radius > 0.0 and z <= _hull_bounds.end.y:
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
	for aabb in obstacle_boxes:
		var box := ObstacleBox.new()
		box.size = aabb.size
		box.margin = box_margin
		box.position = aabb.get_center()
		add_child(box)
		_boxes.append(box)


## One trimesh collision shape (on this body, the World layer) per mesh in the
## `Hull` model. Trimeshes are fine here: the body only moves kinematically,
## and fighters, bolts and rays all collide with them.
func _build_hull_collision() -> void:
	var hull := get_node_or_null(^"Hull") as Node3D
	if hull == null:
		push_warning("Destroyer: hull_collision_from_model is on but there's no Hull node")
		return
	for node in hull.find_children("*", "MeshInstance3D", true, false):
		var mesh_instance := node as MeshInstance3D
		var shape: Shape3D = _hull_shapes.get(mesh_instance.mesh)
		if shape == null:
			shape = mesh_instance.mesh.create_trimesh_shape()
			_hull_shapes[mesh_instance.mesh] = shape
		var collision := CollisionShape3D.new()
		collision.shape = shape
		collision.transform = global_transform.affine_inverse() * mesh_instance.global_transform
		add_child(collision)


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
