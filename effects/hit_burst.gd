class_name HitBurst
extends Node3D
## A bolt hitting something shootable (an enemy, a destroyer part, an asteroid,
## a wreck, the player's shields): a cartoon star burst
## (effects/hit_burst.gdshader) and a spray of sparks thrown back towards the
## shooter. Flat colours, no ink outlines. Spawned by Laser instead of its
## impact flash (which stays for hits on the ground, buildings and hulls); frees
## itself when done. Purely visual.
##
## The settings live on effects/hit_burst.tscn; Laser.hit_burst points at it.
## spawn()'s `size` scales the star and sparks, not the timing.

const SHADER := preload("res://effects/hit_burst.gdshader")

@export_group("Star")
## Star radius (metres) and how long it lasts (seconds).
@export var star_size := 2.2
@export var star_time := 0.2
@export var core_color := Color(1.0, 1.0, 0.9)
@export var mid_color := Color(1.0, 0.86, 0.22)
@export var rim_color := Color(1.0, 0.45, 0.1)

@export_group("Sparks")
## How many, how fast (m/s), how long they last, how long they are (metres),
## and the cone (degrees from straight back at the shooter) they fly out in.
@export var spark_count := 8
@export var spark_speed := Vector2(25.0, 55.0)
@export var spark_lifetime := 0.28
@export var spark_length := 2.2
@export var spark_spread := 65.0
@export var spark_color := Color(1.0, 0.9, 0.35)
## Colour they fade to by the end of their life.
@export var spark_end_color := Color(1.0, 0.4, 0.08)

## Shared by every burst of a scene (built on first use): meshes and materials.
static var _cache := {}

var _age := 0.0
var _star: MeshInstance3D
var _hidden := false


## A burst at `at`, its sparks flying out towards `back` (the way the bolt came
## from), `size` times the scene's.
static func spawn(scene: PackedScene, parent: Node, at: Vector3, back: Vector3, size := 1.0) -> HitBurst:
	var fx := scene.instantiate() as HitBurst
	parent.add_child(fx)
	fx.global_position = at
	fx._build(scene, back, size)
	return fx


## Builds one microscopic burst in front of the camera, so its shader is
## compiled before the first real hit (see Explosion.prewarm()).
static func prewarm(scene: PackedScene, parent: Node) -> void:
	var camera := parent.get_viewport().get_camera_3d()
	var at := camera.global_position - camera.global_basis.z * 3.0 if camera else Vector3.ZERO
	var fx := spawn(scene, parent, at, Vector3.UP, 0.001)
	# Its minimum on-screen size would still show it: drawn at the end of its
	# life, when the shader discards every pixel (it still runs, so compiles).
	fx._hidden = true


func _build(scene: PackedScene, back: Vector3, size: float) -> void:
	var assets := _assets(scene)
	_star = MeshInstance3D.new()
	_star.mesh = assets.star
	_star.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	# The vertex shader places the quad (and keeps it a minimum size on
	# screen): never cull it.
	_star.extra_cull_margin = 200.0
	_star.scale = Vector3.ONE * star_size * size
	_star.set_instance_shader_parameter("seed", randf() * 100.0)
	_star.set_instance_shader_parameter("age", 0.0)
	add_child(_star)

	var sparks := GPUParticles3D.new()
	sparks.draw_pass_1 = assets.spark
	sparks.process_material = assets.spark_process
	sparks.amount = spark_count
	sparks.lifetime = spark_lifetime
	sparks.one_shot = true
	sparks.explosiveness = 1.0
	sparks.randomness = 0.3
	# In this node's space: they follow its scale and its turn towards `back`.
	sparks.local_coords = true
	sparks.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	sparks.visibility_aabb = AABB(Vector3.ONE * -40.0, Vector3.ONE * 80.0)
	sparks.scale = Vector3.ONE * size
	if back.is_normalized() and absf(back.dot(Vector3.UP)) < 0.999:
		sparks.basis = Basis.looking_at(back, Vector3.UP) * Basis(Vector3.RIGHT, -PI / 2.0)
	elif back.is_normalized() and back.y < 0.0:
		sparks.basis = Basis(Vector3.RIGHT, PI)
	sparks.emitting = true
	add_child(sparks)


func _process(delta: float) -> void:
	_age += delta
	_star.set_instance_shader_parameter("age", 1.0 if _hidden else minf(_age / star_time, 0.999))
	if _age >= star_time:
		_star.visible = false
	if _age >= maxf(star_time, spark_lifetime):
		queue_free()


func _assets(scene: PackedScene) -> Dictionary:
	if _cache.has(scene):
		return _cache[scene]
	var star_material := ShaderMaterial.new()
	star_material.shader = SHADER
	star_material.set_shader_parameter("core_color", core_color)
	star_material.set_shader_parameter("mid_color", mid_color)
	star_material.set_shader_parameter("rim_color", rim_color)
	var star := QuadMesh.new()
	star.material = star_material

	# Sparks: thin flat-coloured rods stretched along their flight (align_y),
	# transparent so the ink outlines leave them alone.
	var spark_material := StandardMaterial3D.new()
	spark_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	spark_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	spark_material.vertex_color_use_as_albedo = true
	spark_material.albedo_color = Color(1.5, 1.5, 1.5)
	var spark := BoxMesh.new()
	spark.size = Vector3(0.12, 1.0, 0.12)
	spark.material = spark_material
	var process := ParticleProcessMaterial.new()
	process.particle_flag_align_y = true
	process.direction = Vector3.UP
	process.spread = spark_spread
	process.initial_velocity_min = spark_speed.x
	process.initial_velocity_max = spark_speed.y
	process.damping_min = spark_speed.x * 1.5
	process.damping_max = spark_speed.y * 1.5
	process.gravity = Vector3.ZERO
	process.scale_min = spark_length
	process.scale_max = spark_length
	var shrink := Curve.new()
	shrink.add_point(Vector2(0.0, 1.0))
	shrink.add_point(Vector2(1.0, 0.15))
	var shrink_texture := CurveTexture.new()
	shrink_texture.curve = shrink
	process.scale_curve = shrink_texture
	var colors := Gradient.new()
	colors.set_color(0, spark_color)
	colors.set_color(1, spark_end_color)
	var ramp := GradientTexture1D.new()
	ramp.gradient = colors
	process.color_ramp = ramp

	var assets := {star = star, spark = spark, spark_process = process}
	_cache[scene] = assets
	return assets
