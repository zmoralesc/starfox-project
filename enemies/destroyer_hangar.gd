class_name DestroyerHangar
extends DestroyerPart
## A hangar door. The Destroyer asks it to launch squadrons: the door slides
## up, fighters fly out of the bay one by one, then it closes. Blowing the
## door off stops all launches from this side.

@export var launch_point: Marker3D
## The glowing bay behind the door (shown when open or blown off).
@export var bay_glow: Node3D
@export var open_height := 13.0
@export var door_move_time := 0.8
@export var launch_spacing := 0.7
## Seconds a launched fighter flies straight out before its AI takes over.
@export var launch_flight_time := 2.0

var is_launching := false

var _closed_y := 0.0


func _ready() -> void:
	super()
	_closed_y = position.y


func can_launch() -> bool:
	return not is_destroyed and not is_launching


func launch(count: int, fighter_scene: PackedScene, spawner: EnemySpawner) -> void:
	if not can_launch() or count <= 0:
		return
	is_launching = true
	await _move_door(_closed_y + open_height)
	for i in count:
		if not is_inside_tree() or is_destroyed or not destroyer.is_vulnerable():
			break
		_spawn_fighter(fighter_scene, spawner)
		await get_tree().create_timer(launch_spacing, false).timeout
	if not is_inside_tree():
		return
	await get_tree().create_timer(1.0, false).timeout
	if is_inside_tree() and not is_destroyed:
		await _move_door(_closed_y)
	is_launching = false


func _spawn_fighter(fighter_scene: PackedScene, spawner: EnemySpawner) -> void:
	var fighter := fighter_scene.instantiate() as EnemyFighter
	fighter.transform = launch_point.global_transform
	get_tree().current_scene.add_child(fighter)
	# Patrol out in front of the bay once launched.
	fighter.patrol_center = launch_point.global_position - launch_point.global_basis.z * 150.0
	fighter.begin_launch(launch_flight_time)
	if spawner:
		spawner.track(fighter)


func _move_door(target_y: float) -> void:
	var tween := create_tween()
	tween.tween_property(self, "position:y", target_y, door_move_time) \
		.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	await tween.finished


func _on_broken() -> void:
	# The door is blown off: hide it, let shots fly into the bay.
	for child in get_children():
		if child is MeshInstance3D:
			(child as MeshInstance3D).hide()
		elif child is CollisionShape3D:
			(child as CollisionShape3D).set_deferred("disabled", true)
	if bay_glow:
		bay_glow.show()
