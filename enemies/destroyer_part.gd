class_name DestroyerPart
extends StaticBody3D
## A destructible subsystem on a Destroyer: bridge, thruster, turret or hangar door.
##
## Each part is its own hit target on the Enemy layer; the hull around it is on
## the World layer and just soaks up shots. A destroyed part stays in place,
## charred, and stops being a target.

signal destroyed

enum Kind { BRIDGE, THRUSTER, TURRET, HANGAR }

const CHARRED_COLOR := Color(0.07, 0.06, 0.06)

static var _charred: ShaderMaterial

@export var kind := Kind.TURRET
@export var max_health := 10
## Used for aim assist, wingman fire tolerance and HUD markers.
@export var radius := 4.0
@export var score := 1
## How it blows up (fireball radius = radius × explosion_scale).
@export var explosion: ExplosionStyle = preload("res://effects/explosions/destroyer_part.tres")
@export var explosion_scale := 1.2
@export var display_name := "PART"
## The crosshair turns red over this part (while intact).
@export var highlight_on_crosshair := true
## The Attack order can pick this part (while intact, and only once the
## destroyer can be damaged: not while it's still warping in).
@export var attack_target := true:
	get:
		return attack_target and (destroyer == null or destroyer.is_damageable())

var health := 0
var is_destroyed := false
## Set by the Destroyer that owns this part.
var destroyer: Destroyer


func _ready() -> void:
	health = max_health
	add_to_group("targets")
	add_to_group("destroyer_parts")


func take_hit(damage: int, _at: Vector3) -> void:
	if is_destroyed or destroyer == null or not destroyer.is_damageable():
		return
	health -= damage
	if health <= 0:
		_break()


func _break() -> void:
	is_destroyed = true
	health = 0
	remove_from_group("targets")
	Explosion.spawn(get_tree().current_scene, global_position, explosion, radius * explosion_scale)
	get_tree().call_group("hud", "add_score", score)
	_on_broken()
	destroyed.emit()


## What a destroyed part looks like. Default: charred, its own lights out
## (e.g. thruster exhaust), with embers glowing.
func _on_broken() -> void:
	_char_meshes(self)
	for child in get_children():
		if child is Light3D:
			(child as Light3D).hide()
	var embers := OmniLight3D.new()
	embers.light_color = Color(1.0, 0.45, 0.15)
	embers.light_energy = 2.0
	embers.omni_range = radius * 2.5
	add_child(embers)


func _char_meshes(node: Node) -> void:
	if _charred == null:
		_charred = ShaderMaterial.new()
		_charred.shader = preload("res://effects/toon.gdshader")
		_charred.set_shader_parameter("albedo", CHARRED_COLOR)
		_charred.set_shader_parameter("glint", 0.0)
	for child in node.get_children():
		if child is MeshInstance3D:
			(child as MeshInstance3D).material_override = _charred
		_char_meshes(child)
