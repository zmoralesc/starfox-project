class_name Explosion
extends Node3D
## A cel-shaded explosion: a white-hot flash, a fireball of puffs that cool
## into smoke and break up (effects/explosion_puff.gdshader), lingering smoke,
## sparks, tumbling debris, an optional shockwave ring and a burst of light.
## What it looks like comes from an ExplosionStyle (presets in
## effects/explosions/); how big it is from `size`, the fireball's radius in
## metres. Laser hits use the smaller Impact instead.
##
## The whole effect is built in this node's space and the node is scaled by
## `size`, so materials and meshes are shared by every explosion of a style
## (built once, _assets()). It drifts on with some of the exploding object's
## velocity, and frees itself when its longest part is done.

const PUFF_SHADER := preload("res://effects/explosion_puff.gdshader")

## Built materials, meshes and textures per style, shared by every explosion.
static var _cache: Dictionary = {}

var _style: ExplosionStyle
var _velocity := Vector3.ZERO
var _debris: Array[MeshInstance3D] = []
var _debris_velocity: Array[Vector3] = []
var _debris_spin: Array[Vector3] = []
var _age := 0.0


## An explosion of `style` at `at`, its fireball `size` metres in radius,
## carried along by some of `velocity` (the exploding object's).
static func spawn(parent: Node, at: Vector3, style: ExplosionStyle, size := 1.0,
		velocity := Vector3.ZERO) -> Explosion:
	var fx := Explosion.new()
	fx._style = style
	fx._velocity = velocity * style.inherit_velocity
	parent.add_child(fx)
	fx.global_position = at
	fx.scale = Vector3.ONE * size
	fx._build(size)
	return fx


## Sets off a microscopic explosion of `style` just in front of the camera, so
## its materials are built and its shaders compiled now (a ~20 ms stutter)
## rather than at the first real one. It has to be drawn for that, hence in
## view; at a millimetre across it covers less than a pixel.
static func prewarm(parent: Node, style: ExplosionStyle) -> void:
	var camera := parent.get_viewport().get_camera_3d()
	var at := camera.global_position - camera.global_basis.z * 3.0 if camera else Vector3.ZERO
	spawn(parent, at, style, 0.001)


func _process(delta: float) -> void:
	_age += delta
	_velocity *= exp(-_style.drag * delta)
	global_position += _velocity * delta
	var life := clampf(_age / _style.debris_lifetime, 0.0, 1.0)
	for i in _debris.size():
		var chunk := _debris[i]
		chunk.position += _debris_velocity[i] * delta
		chunk.rotate_x(_debris_spin[i].x * delta)
		chunk.rotate_y(_debris_spin[i].y * delta)
		chunk.rotate_z(_debris_spin[i].z * delta)
		# Shrink away over the last third of their life.
		chunk.scale = Vector3.ONE * _style.debris_size * clampf((1.0 - life) * 3.0, 0.0, 1.0)
	if _age >= _style.duration():
		queue_free()


func _build(size: float) -> void:
	var assets := _assets(_style)
	if _style.flash_size > 0.0:
		_add_flash(assets)
	if _style.puff_count > 0:
		add_child(_puffs(assets["fire_puff"], assets["puff_process"], _style.puff_count, _style.puff_lifetime))
	if _style.smoke_count > 0:
		var smoke := _puffs(assets["smoke_puff"], assets["smoke_process"], _style.smoke_count, _style.smoke_lifetime)
		smoke.emitting = false
		add_child(smoke)
		get_tree().create_timer(_style.smoke_delay, false).timeout.connect(func() -> void:
			if is_instance_valid(smoke):
				smoke.emitting = true)
	if _style.spark_count > 0:
		add_child(_puffs(assets["spark"], assets["spark_process"], _style.spark_count, _style.spark_lifetime))
	for i in _style.debris_count:
		_add_debris(assets)
	if _style.shockwave_size > 0.0:
		_add_shockwave(assets)
	if _style.light_energy > 0.0:
		_add_light(size)


func _add_flash(assets: Dictionary) -> void:
	var flash := MeshInstance3D.new()
	flash.mesh = assets["flash"]
	flash.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	flash.scale = Vector3.ONE * _style.flash_size * 0.4
	add_child(flash)
	var tween := create_tween().set_parallel()
	tween.tween_property(flash, "scale", Vector3.ONE * _style.flash_size, _style.flash_time) \
		.set_trans(Tween.TRANS_EXPO).set_ease(Tween.EASE_OUT)
	tween.tween_property(flash, "transparency", 1.0, _style.flash_time).set_ease(Tween.EASE_IN)
	tween.chain().tween_callback(flash.queue_free)


func _puffs(mesh: Mesh, process: ParticleProcessMaterial, count: int, lifetime: float) -> GPUParticles3D:
	var particles := GPUParticles3D.new()
	particles.draw_pass_1 = mesh
	particles.process_material = process
	particles.amount = count
	particles.lifetime = lifetime
	# In this node's space, so they follow its scale (size) and its drift.
	particles.local_coords = true
	particles.one_shot = true
	particles.explosiveness = 1.0
	particles.randomness = 0.3
	particles.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	particles.visibility_aabb = AABB(Vector3.ONE * -12.0, Vector3.ONE * 24.0)
	particles.emitting = true
	return particles


func _add_debris(assets: Dictionary) -> void:
	var chunk := MeshInstance3D.new()
	chunk.mesh = assets["debris"]
	chunk.scale = Vector3.ONE * _style.debris_size
	chunk.rotation = Vector3(randf(), randf(), randf()) * TAU
	chunk.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(chunk)
	_debris.append(chunk)
	_debris_velocity.append(_random_direction() * _style.debris_speed * randf_range(0.5, 1.0))
	_debris_spin.append(Vector3(randf_range(-1, 1), randf_range(-1, 1), randf_range(-1, 1)) * 8.0)


func _add_shockwave(assets: Dictionary) -> void:
	var ring := MeshInstance3D.new()
	ring.mesh = assets["shockwave"]
	ring.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var tilt := deg_to_rad(_style.shockwave_tilt)
	ring.rotation = Vector3(randf_range(-tilt, tilt), randf() * TAU, randf_range(-tilt, tilt))
	ring.scale = Vector3.ONE * 0.2
	add_child(ring)
	var full := Vector3.ONE * _style.shockwave_size * 2.0
	var tween := create_tween().set_parallel()
	tween.tween_property(ring, "scale", full, _style.shockwave_time) \
		.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tween.tween_property(ring, "transparency", 1.0, _style.shockwave_time).set_ease(Tween.EASE_IN)
	tween.chain().tween_callback(ring.queue_free)


func _add_light(size: float) -> void:
	var light := OmniLight3D.new()
	light.light_color = _style.light_color
	light.light_energy = _style.light_energy
	# Set in metres: a light's range doesn't follow its node's scale reliably.
	light.omni_range = _style.light_range * size
	light.top_level = true
	add_child(light)
	light.global_position = global_position
	var tween := create_tween()
	tween.tween_property(light, "light_energy", 0.0, _style.light_time).set_ease(Tween.EASE_IN)
	tween.tween_callback(light.queue_free)


static func _random_direction() -> Vector3:
	return Vector3(randf_range(-1, 1), randf_range(-1, 1), randf_range(-1, 1)).normalized()


## Materials, meshes and particle settings for `style`, built on first use.
static func _assets(style: ExplosionStyle) -> Dictionary:
	if _cache.has(style):
		return _cache[style]
	var assets := {}

	# Flash: a soft white-hot glow facing the camera, added on top.
	var flash_material := StandardMaterial3D.new()
	flash_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	flash_material.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	flash_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	flash_material.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	flash_material.billboard_keep_scale = true
	flash_material.albedo_color = style.flash_color
	flash_material.albedo_texture = _radial_texture([0.0, 0.35, 1.0], [1.0, 0.8, 0.0])
	var flash := QuadMesh.new()
	flash.material = flash_material
	assets["flash"] = flash

	# Fireball and smoke puffs: the same shader, the smoke one born cold.
	var fire_puff := QuadMesh.new()
	fire_puff.material = _puff_material(style, style.cool_at)
	assets["fire_puff"] = fire_puff
	var smoke_puff := QuadMesh.new()
	smoke_puff.material = _puff_material(style, 0.001)
	assets["smoke_puff"] = smoke_puff
	assets["puff_process"] = _puff_process(style.puff_size, style.puff_speed, 0.35)
	assets["smoke_process"] = _puff_process(style.smoke_size, style.smoke_speed, 0.6)

	# Sparks: thin glowing rods stretched along their flight (align_y).
	var spark_material := StandardMaterial3D.new()
	spark_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	spark_material.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	spark_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	spark_material.vertex_color_use_as_albedo = true
	spark_material.albedo_color = Color(3.0, 3.0, 3.0)
	var spark := BoxMesh.new()
	spark.size = Vector3(0.04, 1.0, 0.04)
	spark.material = spark_material
	assets["spark"] = spark
	var spark_process := ParticleProcessMaterial.new()
	spark_process.particle_flag_align_y = true
	spark_process.direction = Vector3.UP
	spark_process.spread = 180.0
	spark_process.initial_velocity_min = style.spark_speed * 0.5
	spark_process.initial_velocity_max = style.spark_speed
	spark_process.damping_min = style.spark_speed * 0.6
	spark_process.damping_max = style.spark_speed * 0.9
	spark_process.gravity = Vector3.ZERO
	spark_process.scale_min = style.spark_length
	spark_process.scale_max = style.spark_length
	spark_process.scale_curve = _curve_texture([Vector2(0.0, 1.0), Vector2(1.0, 0.2)])
	var spark_colors := Gradient.new()
	spark_colors.set_color(0, style.spark_color)
	spark_colors.set_color(1, Color(style.spark_color.r, style.spark_color.g * 0.3, 0.0, 0.0))
	var spark_ramp := GradientTexture1D.new()
	spark_ramp.gradient = spark_colors
	spark_process.color_ramp = spark_ramp
	assets["spark_process"] = spark_process

	# Debris: dark toon-shaded chunks.
	var debris_material := ShaderMaterial.new()
	debris_material.shader = ToonMaterial.SHADER
	debris_material.set_shader_parameter("albedo", style.debris_color)
	var debris: PrimitiveMesh
	if style.debris_rocks:
		var rock := SphereMesh.new()
		rock.radial_segments = 5
		rock.rings = 3
		rock.radius = 0.5
		rock.height = 0.8
		debris = rock
	else:
		var plate := BoxMesh.new()
		plate.size = Vector3(1.0, 0.35, 0.7)
		debris = plate
	debris.material = debris_material
	assets["debris"] = debris

	# Shockwave: a flat ring (bright towards its outer edge), seen from both sides.
	var ring_material := StandardMaterial3D.new()
	ring_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	ring_material.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	ring_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	ring_material.cull_mode = BaseMaterial3D.CULL_DISABLED
	ring_material.albedo_color = style.shockwave_color * 2.0
	ring_material.albedo_texture = _radial_texture([0.0, 0.7, 0.9, 0.97, 1.0], [0.0, 0.0, 0.5, 1.0, 0.0])
	var ring := PlaneMesh.new()
	ring.size = Vector2.ONE
	ring.material = ring_material
	assets["shockwave"] = ring

	_cache[style] = assets
	return assets


static func _puff_material(style: ExplosionStyle, cool_at: float) -> ShaderMaterial:
	var material := ShaderMaterial.new()
	material.shader = PUFF_SHADER
	material.set_shader_parameter("hot_color", style.hot_color)
	material.set_shader_parameter("fire_color", style.fire_color)
	material.set_shader_parameter("ember_color", style.ember_color)
	material.set_shader_parameter("smoke_color", style.smoke_color)
	material.set_shader_parameter("glow", style.glow)
	material.set_shader_parameter("cool_at", cool_at)
	material.set_shader_parameter("dissolve_from", style.dissolve_from)
	# Toon light model: soft smoke, so no glint.
	material.set_shader_parameter("glint", 0.0)
	material.set_shader_parameter("shadow_tone", 0.35)
	return material


## Puffs burst out from a small sphere, slow down and swell.
static func _puff_process(puff_size: float, speed: float, start_scale: float) -> ParticleProcessMaterial:
	var process := ParticleProcessMaterial.new()
	process.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	process.emission_sphere_radius = 0.3
	process.direction = Vector3.UP
	process.spread = 180.0
	process.initial_velocity_min = speed * 0.4
	process.initial_velocity_max = speed
	process.damping_min = speed * 0.5
	process.damping_max = speed * 0.8
	process.gravity = Vector3.ZERO
	process.scale_min = puff_size * 0.75
	process.scale_max = puff_size * 1.25
	process.scale_curve = _curve_texture([Vector2(0.0, start_scale), Vector2(0.25, 0.85), Vector2(1.0, 1.0)])
	return process


static func _curve_texture(points: Array[Vector2]) -> CurveTexture:
	var curve := Curve.new()
	for point in points:
		curve.add_point(point)
	var texture := CurveTexture.new()
	texture.curve = curve
	return texture


## A white radial gradient with these alphas at these distances from the centre (0 to 1).
static func _radial_texture(offsets: Array[float], alphas: Array[float]) -> GradientTexture2D:
	var gradient := Gradient.new()
	gradient.offsets = PackedFloat32Array(offsets)
	var colors := PackedColorArray()
	for alpha in alphas:
		colors.append(Color(1, 1, 1, alpha))
	gradient.colors = colors
	var texture := GradientTexture2D.new()
	texture.gradient = gradient
	texture.fill = GradientTexture2D.FILL_RADIAL
	texture.fill_from = Vector2(0.5, 0.5)
	texture.fill_to = Vector2(0.5, 0.0)
	texture.width = 256
	texture.height = 256
	return texture
