class_name HitBurst
extends Node3D
## A bolt's hit: a cartoon star burst (effects/hit_burst.gdshader), a spray of
## sparks and, optionally, a few puffs of dust. Flat colours, no ink outlines.
## Spawned by Laser; frees itself when done. Purely visual.
##
## Two scenes use it (Laser.hit_burst and Laser.surface_hit):
## - effects/hit_burst.tscn: hits on anything shootable (an enemy, a
##   destroyer part, an asteroid, a wreck, the player's shields). A big yellow
##   spiky star, sparks thrown back towards the shooter.
## - effects/surface_hit.tscn: hits on things that can't be shot (the ground,
##   buildings, hulls). A smaller, rounder pop in the bolt's colour, sparks
##   glancing off the surface and a puff of dust, so a miss never reads as a hit.
##
## The settings live on the scene. spawn()'s `size` scales the star, sparks
## and dust, not the timing.

const SHADER := preload("res://effects/hit_burst.gdshader")

@export_group("Star")
## Star radius (metres) and how long it lasts (seconds).
@export var star_size := 2.2
@export var star_time := 0.2
@export var core_color := Color(1.0, 1.0, 0.9)
@export var mid_color := Color(1.0, 0.86, 0.22)
@export var rim_color := Color(1.0, 0.45, 0.1)
## Spikes round the star, how much their lengths vary, and how far in the dips
## between them come (fraction of the radius; near 1 = almost round).
@export var star_spikes := 8.0
@export_range(0.0, 1.0) var star_spike_variety := 0.45
@export_range(0.0, 1.0) var star_valley := 0.38
## Far off, the star is drawn at least `star_min_angle` (radius, radians of
## view) so a distant hit still shows, but never more than `star_max_grow`
## times its real size for that: further still, it shrinks with distance.
@export var star_min_angle := 0.014
@export var star_max_grow := 2.5

@export_group("Bolt colour")
## Colour the star's middle band and rim and the sparks from the bolt's own
## colour (the `tint` spawn() is given: Laser.impact_color) instead of the
## colours set here. The core stays `core_color`.
@export var tint_from_bolt := false
## How far towards white the tinted middle band and the sparks are.
@export_range(0.0, 1.0) var tint_lighten := 0.55

@export_group("Sparks")
## How many, how fast (m/s), how long they last, how long they are (metres),
## and the cone (degrees from the spawn direction) they fly out in.
@export var spark_count := 8
@export var spark_speed := Vector2(25.0, 55.0)
@export var spark_lifetime := 0.28
@export var spark_length := 2.2
@export var spark_spread := 65.0
@export var spark_color := Color(1.0, 0.9, 0.35)
## Colour they fade to by the end of their life.
@export var spark_end_color := Color(1.0, 0.4, 0.08)

@export_group("Dust")
## Puffs kicked up (0 = none): toon smoke puffs (the explosions' shader, born
## cold), growing from `dust_size.x` to `dust_size.y` metres over
## `dust_lifetime` seconds, drifting off along the spawn direction at up to
## `dust_drift` m/s in a cone `dust_spread` degrees wide.
@export var dust_count := 0
@export var dust_size := Vector2(0.8, 3.0)
@export var dust_lifetime := 0.7
@export var dust_drift := 4.0
@export var dust_spread := 35.0
## Its colour: light, so it reads as dust kicked up rather than smoke.
@export var dust_color := Color(0.78, 0.74, 0.66)

## Shared by every burst of a scene and bolt colour (built on first use):
## meshes and materials.
static var _cache := {}

var _age := 0.0
var _star: MeshInstance3D
var _hidden := false


## A burst at `at`, its sparks and dust flying out along `out` (for a hit on a
## target, back the way the bolt came; on a surface, off it), `size` times the
## scene's, coloured from `tint` if the scene takes the bolt's colour.
static func spawn(scene: PackedScene, parent: Node, at: Vector3, out: Vector3, size := 1.0,
		tint := Color.WHITE) -> HitBurst:
	var fx := scene.instantiate() as HitBurst
	parent.add_child(fx)
	fx.global_position = at
	fx._build(scene, out, size, tint)
	return fx


## Builds one microscopic burst in front of the camera, so its shaders are
## compiled before the first real hit (see Explosion.prewarm()).
static func prewarm(scene: PackedScene, parent: Node) -> void:
	var camera := parent.get_viewport().get_camera_3d()
	var at := camera.global_position - camera.global_basis.z * 3.0 if camera else Vector3.ZERO
	var fx := spawn(scene, parent, at, Vector3.UP, 0.001)
	# Its minimum on-screen size would still show it: drawn at the end of its
	# life, when the shader discards every pixel (it still runs, so compiles).
	fx._hidden = true


func _build(scene: PackedScene, out: Vector3, size: float, tint: Color) -> void:
	var assets := _assets(scene, tint if tint_from_bolt else Color.WHITE)
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

	# Sparks and dust in this node's space, +Y along `out`, scaled by `size`.
	var facing := Transform3D(_facing(out).scaled(Vector3.ONE * size), Vector3.ZERO)
	var sparks := GPUParticles3D.new()
	sparks.draw_pass_1 = assets.spark
	sparks.process_material = assets.spark_process
	sparks.amount = spark_count
	sparks.lifetime = spark_lifetime
	sparks.one_shot = true
	sparks.explosiveness = 1.0
	sparks.randomness = 0.3
	sparks.local_coords = true
	sparks.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	sparks.visibility_aabb = AABB(Vector3.ONE * -40.0, Vector3.ONE * 80.0)
	sparks.transform = facing
	sparks.emitting = true
	add_child(sparks)

	if dust_count > 0:
		var dust := GPUParticles3D.new()
		dust.draw_pass_1 = assets.dust
		dust.process_material = assets.dust_process
		dust.amount = dust_count
		dust.lifetime = dust_lifetime
		dust.one_shot = true
		dust.explosiveness = 0.8
		dust.local_coords = true
		dust.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		dust.visibility_aabb = AABB(Vector3.ONE * -20.0, Vector3.ONE * 40.0)
		dust.transform = facing
		dust.emitting = true
		add_child(dust)


## A basis whose +Y (the particles' direction) points along `dir`.
static func _facing(dir: Vector3) -> Basis:
	if not dir.is_normalized():
		return Basis.IDENTITY
	if absf(dir.dot(Vector3.UP)) < 0.999:
		return Basis.looking_at(dir, Vector3.UP) * Basis(Vector3.RIGHT, -PI / 2.0)
	return Basis.IDENTITY if dir.y > 0.0 else Basis(Vector3.RIGHT, PI)


func _process(delta: float) -> void:
	_age += delta
	_star.set_instance_shader_parameter("age", 1.0 if _hidden else minf(_age / star_time, 0.999))
	if _age >= star_time:
		_star.visible = false
	var last := maxf(star_time, spark_lifetime)
	if dust_count > 0:
		last = maxf(last, dust_lifetime)
	if _age >= last:
		queue_free()


func _assets(scene: PackedScene, tint: Color) -> Dictionary:
	var key := [scene, tint]
	if _cache.has(key):
		return _cache[key]
	var mid := mid_color
	var rim := rim_color
	var spark_start := spark_color
	var spark_end := spark_end_color
	if tint_from_bolt:
		mid = tint.lerp(Color.WHITE, tint_lighten)
		rim = tint
		spark_start = mid
		spark_end = tint
	var star_material := ShaderMaterial.new()
	star_material.shader = SHADER
	star_material.set_shader_parameter("core_color", core_color)
	star_material.set_shader_parameter("mid_color", mid)
	star_material.set_shader_parameter("rim_color", rim)
	star_material.set_shader_parameter("spikes", star_spikes)
	star_material.set_shader_parameter("spike_variety", star_spike_variety)
	star_material.set_shader_parameter("valley", star_valley)
	star_material.set_shader_parameter("min_angle", star_min_angle)
	star_material.set_shader_parameter("max_grow", star_max_grow)
	# Drawn after the dust (and any puffs), so they never cover it.
	star_material.render_priority = 1
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
	colors.set_color(0, spark_start)
	colors.set_color(1, spark_end)
	var ramp := GradientTexture1D.new()
	ramp.gradient = colors
	process.color_ramp = ramp

	var assets := {star = star, spark = spark, spark_process = process}
	if dust_count > 0:
		# The wrecks' puff trail, born cold (all smoke): its mesh and settings
		# borrowed for a one-shot puff.
		var style := ExplosionStyle.new()
		style.smoke_color = dust_color
		var trail := Explosion.trail(style, 1.0, dust_lifetime, dust_size.x, dust_size.y,
			0.001, 0.4, 0.3, dust_drift, dust_spread)
		assets.dust = trail.draw_pass_1
		assets.dust_process = trail.process_material
		trail.free()
	_cache[key] = assets
	return assets
