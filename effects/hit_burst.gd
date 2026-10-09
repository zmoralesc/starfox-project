class_name HitBurst
extends Node3D
## A bolt's hit: an impact flash (effects/hit_burst.gdshader: hot core, light rays,
## shock ring), a spray of glowing sparks and, optionally, a few puffs of dust.
## Transparent, so no ink outlines.
## Spawned by Laser; frees itself when done. Purely visual.
##
## Two scenes use it (Laser.hit_burst and Laser.surface_hit):
## - effects/hit_burst.tscn: hits on anything shootable (an enemy, a
##   destroyer part, an asteroid, a wreck, the player's shields). A big gold
##   flash with long rays, sparks thrown back towards the shooter.
## - effects/surface_hit.tscn: hits on things that can't be shot (the ground,
##   buildings, hulls). A smaller flash in the bolt's colour, short rays, sparks
##   glancing off the surface and a puff of dust, so a miss never reads as a hit.
##
## The settings live on the scene. spawn()'s `size` scales the flash, sparks
## and dust, not the timing.

const SHADER := preload("res://effects/hit_burst.gdshader")

@export_group("Flash")
## Flash radius (metres) and how long it lasts (seconds).
@export var flash_size := 2.2
@export var flash_time := 0.22
## The core, the middle of the rays and their tips and the ring.
@export var core_color := Color(1.0, 1.0, 0.9)
@export var mid_color := Color(1.0, 0.86, 0.22)
@export var rim_color := Color(1.0, 0.45, 0.1)
## Overall strength (above 1 blooms).
@export var flash_brightness := 1.4
## Rays: how many, how much their lengths vary, and their width at the root
## (fraction of each ray's slice of the circle).
@export var ray_count := 9.0
@export_range(0.0, 1.0) var ray_variety := 0.5
@export_range(0.0, 0.5) var ray_width := 0.22
## Brightness of the shock ring (0 = none).
@export var ring_strength := 0.8
## Far off, the flash is drawn at least `flash_min_angle` (radius, radians of
## view) so a distant hit still shows, but never more than `flash_max_grow`
## times its real size for that: further still, it shrinks with distance.
@export var flash_min_angle := 0.014
@export var flash_max_grow := 2.5

@export_group("Bolt colour")
## Colour the flash's rays and ring and the sparks from the bolt's own
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
## Thickness (metres) and brightness (above 1 blooms).
@export var spark_width := 0.045
@export var spark_glow := 1.15

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
var _flash: MeshInstance3D
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
	_flash = MeshInstance3D.new()
	_flash.mesh = assets.flash
	_flash.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	# The vertex shader places the quad (and keeps it a minimum size on
	# screen): never cull it.
	_flash.extra_cull_margin = 200.0
	_flash.scale = Vector3.ONE * flash_size * size
	_flash.set_instance_shader_parameter("seed", randf() * 100.0)
	_flash.set_instance_shader_parameter("age", 0.0)
	add_child(_flash)

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
	_flash.set_instance_shader_parameter("age", 1.0 if _hidden else minf(_age / flash_time, 0.999))
	if _age >= flash_time:
		_flash.visible = false
	var last := maxf(flash_time, spark_lifetime)
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
	var flash_material := ShaderMaterial.new()
	flash_material.shader = SHADER
	flash_material.set_shader_parameter("core_color", core_color)
	flash_material.set_shader_parameter("mid_color", mid)
	flash_material.set_shader_parameter("rim_color", rim)
	flash_material.set_shader_parameter("brightness", flash_brightness)
	flash_material.set_shader_parameter("rays", ray_count)
	flash_material.set_shader_parameter("ray_variety", ray_variety)
	flash_material.set_shader_parameter("ray_width", ray_width)
	flash_material.set_shader_parameter("ring_strength", ring_strength)
	flash_material.set_shader_parameter("min_angle", flash_min_angle)
	flash_material.set_shader_parameter("max_grow", flash_max_grow)
	# Drawn after the dust (and any puffs), so they never cover it.
	flash_material.render_priority = 1
	var flash := QuadMesh.new()
	flash.material = flash_material

	# Sparks: thin glowing streaks stretched along their flight (align_y),
	# transparent so the ink outlines leave them alone; bright enough to bloom
	# a little, so they read as light, but painted, so they keep their colour.
	var spark_material := StandardMaterial3D.new()
	spark_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	spark_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	spark_material.disable_fog = true
	spark_material.vertex_color_use_as_albedo = true
	spark_material.albedo_color = Color(spark_glow, spark_glow, spark_glow)
	var spark := BoxMesh.new()
	spark.size = Vector3(spark_width, 1.0, spark_width)
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

	var assets := {flash = flash, spark = spark, spark_process = process}
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
