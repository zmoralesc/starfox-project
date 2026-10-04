class_name Laser
extends Node3D
## A laser bolt. Moves in a straight line and raycasts along each step so fast
## bolts never tunnel through thin objects.

@export var lifetime := 1.6
@export var damage := 1
@export var impact_color := Color(1.0, 0.35, 0.2)
## What the bolt can hit. Defaults to the world layer only (Fighter.LAYER_WORLD);
## friendly ships are on another layer, so there's no friendly fire.
@export_flags_3d_physics var collision_mask := 1
## Length of the glowing streak behind the bolt, in metres. 0 = draw the Bolt
## mesh as modelled, centred on the bolt. Otherwise the mesh is stretched out
## behind the bolt's head, growing from the muzzle over the first frames so it
## never pokes back through the ship that fired it. Close to one frame's travel
## makes a fast bolt read as a continuous streak instead of hopping dashes.
@export var trail_length := 0.0

var _velocity := Vector3.ZERO
var _origin := Vector3.ZERO
var _exclude: Array[RID] = []
var _age := 0.0
var _shooter_node: Node3D
## Distance flown so far (the trail can't be longer than this).
var _travelled := 0.0
## The Bolt mesh's modelled length, along its local Y.
var _bolt_length := 1.0

@onready var _bolt: MeshInstance3D = $Bolt


func _ready() -> void:
	if trail_length > 0.0:
		_bolt_length = _bolt.get_aabb().size.y
		_update_trail()


## Call after adding the bolt to the tree.
func launch(origin: Vector3, direction: Vector3, bolt_speed: float, shooter_node: Node3D) -> void:
	_face(direction)
	global_position = origin
	_velocity = direction * bolt_speed
	_origin = origin
	_shooter_node = shooter_node
	if shooter_node:
		_exclude.append(shooter_node.get_rid())


func _physics_process(delta: float) -> void:
	_age += delta
	if _age > lifetime:
		queue_free()
		return

	var step := _velocity * delta
	var from := global_position
	if not _cast(from, from + step):
		global_position = from + step
		_travelled += step.length()
		if trail_length > 0.0:
			_update_trail()


## Raycasts one step of movement. On a hit, applies it and frees the bolt.
func _cast(from: Vector3, to: Vector3) -> bool:
	var query := PhysicsRayQueryParameters3D.create(from, to, collision_mask, _exclude)
	# Enemy hurtboxes are areas; they're only on LAYER_HURTBOX, so bolts whose
	# mask leaves that out (enemy and turret bolts) still ignore them.
	query.collide_with_areas = true
	var hit := get_world_3d().direct_space_state.intersect_ray(query)
	if hit.is_empty():
		return false
	var target: Object = Hurtbox.resolve(hit.collider)
	# Let the target know where the shot came from (enemies use it to evade).
	if target.has_method("notify_shot"):
		target.notify_shot(_origin)
	if target.has_method("take_hit"):
		target.take_hit(damage, hit.position)
		# Tell the shooter (if it's still around) when this shot destroyed something.
		if is_instance_valid(_shooter_node) and _shooter_node.has_method("notify_kill"):
			if target.is_queued_for_deletion() or target.get("is_destroyed") == true:
				_shooter_node.notify_kill(target)
	Impact.spawn(get_parent(), hit.position, impact_color, 0.8)
	queue_free()
	return true


## Stretches the Bolt mesh behind the head: as long as trail_length, or as far
## as the bolt has flown if that's shorter.
func _update_trail() -> void:
	var length := minf(trail_length, _travelled)
	_bolt.visible = length > 0.05
	if not _bolt.visible:
		return
	# The mesh's Y axis is the bolt's length (it's rotated onto Z); the bolt
	# flies along -Z, so +Z is behind the head.
	_bolt.scale = Vector3(1.0, length / _bolt_length, 1.0)
	_bolt.position = Vector3(0.0, 0.0, length * 0.5)


func _face(direction: Vector3) -> void:
	var up := Vector3.UP if absf(direction.y) < 0.99 else Vector3.RIGHT
	global_basis = Basis.looking_at(direction, up)
