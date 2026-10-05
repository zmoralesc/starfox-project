class_name Asteroid
extends StaticBody3D
## A destructible, lumpy low-poly rock. Meshes are generated once and shared.

signal destroyed

const VARIANT_COUNT := 8

static var _meshes: Array[ArrayMesh] = []

@export var radius := 10.0
## How it bursts (fireball radius = radius × explosion_scale).
@export var explosion: ExplosionStyle = preload("res://effects/explosions/asteroid.tres")
@export var explosion_scale := 0.6
## The crosshair doesn't turn red over rocks: they're everywhere in the field
## and would drown out the enemies.
@export var highlight_on_crosshair := false
## Rocks can't be picked by the Attack order (wingmen are for enemies).
@export var attack_target := false

var health := 1

var _visual: MeshInstance3D
var _spin_axis := Vector3.UP
var _spin_speed := 0.0


func _ready() -> void:
	add_to_group("targets")
	add_to_group("obstacles")
	if _meshes.is_empty():
		_build_meshes()
	health = 1 + int(radius / 4.0)

	_visual = MeshInstance3D.new()
	_visual.mesh = _meshes.pick_random()
	add_child(_visual)
	_visual.rotation = Vector3(randf(), randf(), randf()) * TAU
	_visual.scale = Vector3(randf_range(0.8, 1.2), randf_range(0.7, 1.1), randf_range(0.8, 1.25)) * radius

	var sphere := SphereShape3D.new()
	sphere.radius = radius * 0.85
	var shape := CollisionShape3D.new()
	shape.shape = sphere
	add_child(shape)

	_spin_axis = Vector3(randf_range(-1, 1), randf_range(-1, 1), randf_range(-1, 1)).normalized()
	_spin_speed = randf_range(0.05, 0.4)


func _process(delta: float) -> void:
	# Only the visual spins; the collision sphere doesn't care.
	_visual.rotate(_spin_axis, _spin_speed * delta)


func take_hit(damage: int, _at: Vector3) -> void:
	if health <= 0:
		return  # already exploding; several bolts can land in one frame
	health -= damage
	if health > 0:
		return
	get_tree().call_group("hud", "add_score", 1)
	_explode()


## Destroyed by something other than the player (e.g. rammed by a destroyer): no score.
func shatter() -> void:
	if health <= 0:
		return
	health = 0
	_explode()


func _explode() -> void:
	Explosion.spawn(get_parent(), global_position, explosion, radius * explosion_scale)
	destroyed.emit()
	queue_free()


static func _build_meshes() -> void:
	var material := ShaderMaterial.new()
	material.shader = preload("res://effects/toon.gdshader")
	material.set_shader_parameter("albedo", Color(0.42, 0.38, 0.34))
	material.set_shader_parameter("glint", 0.0)

	var sphere := SphereMesh.new()
	sphere.radius = 1.0
	sphere.height = 2.0
	sphere.radial_segments = 14
	sphere.rings = 8
	var arrays := sphere.get_mesh_arrays()
	var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]

	var noise := FastNoiseLite.new()
	noise.frequency = 1.2
	for variant in VARIANT_COUNT:
		noise.seed = variant * 97 + 13
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		st.set_smooth_group(-1)  # flat shading for a faceted rock look
		for i in indices:
			var p := verts[i]
			st.add_vertex(p * (1.0 + noise.get_noise_3dv(p) * 0.6))
		st.generate_normals()
		st.set_material(material)
		_meshes.append(st.commit())
