extends MultiMeshInstance3D
## Tiny specks that wrap around the camera and streak along the ship's velocity,
## so there's always a sense of speed even in empty space.

@export var count := 280
## Half-size of the box of dust kept around the camera.
@export var extent := 70.0
## How much the specks stretch per unit of speed.
@export var streak := 0.25

var _points := PackedVector3Array()


func _ready() -> void:
	top_level = true
	cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	custom_aabb = AABB(Vector3.ONE * -1e5, Vector3.ONE * 2e5)

	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	# Transparent so it stays out of the depth buffer and the ink outlines skip it.
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.albedo_color = Color(0.75, 0.8, 0.95)
	var mesh := BoxMesh.new()
	mesh.size = Vector3.ONE * 0.05
	mesh.material = material

	multimesh = MultiMesh.new()
	multimesh.transform_format = MultiMesh.TRANSFORM_3D
	multimesh.mesh = mesh
	multimesh.instance_count = count
	for i in count:
		_points.append((Vector3(randf(), randf(), randf()) * 2.0 - Vector3.ONE) * extent)


func _process(_delta: float) -> void:
	var cam := get_viewport().get_camera_3d()
	if cam == null:
		return

	var dust_basis := Basis.IDENTITY
	var ship := get_tree().get_first_node_in_group("player") as Ship
	if ship and ship.velocity.length() > 1.0:
		var dir := ship.velocity.normalized()
		var up := Vector3.UP if absf(dir.y) < 0.99 else Vector3.RIGHT
		dust_basis = Basis.looking_at(dir, up) * Basis.from_scale(Vector3(1.0, 1.0, 1.0 + ship.velocity.length() * streak))

	var origin := cam.global_position
	var size := extent * 2.0
	for i in count:
		var rel := _points[i] - origin
		rel = Vector3(
			fposmod(rel.x + extent, size) - extent,
			fposmod(rel.y + extent, size) - extent,
			fposmod(rel.z + extent, size) - extent)
		multimesh.set_instance_transform(i, Transform3D(dust_basis, origin + rel))
