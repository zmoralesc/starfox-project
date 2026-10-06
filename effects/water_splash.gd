class_name WaterSplash
extends Node3D
## A bolt hitting water: a tall jet of water shooting up with a jagged top and
## falling back, a short wide crown round its foot, and a ring of foam
## spreading on the surface. The jet and crown are shapes drawn by
## effects/water_splash.gdshader on one cylinder each (toon-lit white, no ink
## outlines, like the water); the ring is drawn by the water shader (WaterMarks).
## Spawned by Laser (instead of its impact flash) when
## Terrain.is_water_surface() says it hit water; frees itself when done.
## Purely visual.
##
## The settings live on effects/water_splash.tscn; Laser.water_splash points at
## it. spawn()'s `size` scales the shapes and the ring, not the timing.

const SHADER := preload("res://effects/water_splash.gdshader")

## Seconds the splash lasts (the jet rises over `rise` of it and falls back
## over the rest).
@export var lifetime := 1.1

@export_group("Jet")
## The tall middle column: peak height and foot radius (metres), fraction of
## the life it rises, how much its top flares, how much it opens out by the
## end, spikes round its top and how deep they cut, and when it starts to
## break up (fraction of the life).
@export var jet_height := 11.0
@export var jet_radius := 0.7
@export_range(0.05, 0.95) var jet_rise := 0.4
@export var jet_flare := 0.8
@export var jet_open_out := 0.6
@export var jet_spikes := 6.0
@export_range(0.0, 1.0) var jet_spike_depth := 0.4
@export_range(0.0, 1.0) var jet_breakup_from := 0.45

@export_group("Crown")
## The short wide sheet round the foot, flaring out like a crown.
@export var crown_height := 4.5
@export var crown_radius := 1.6
@export_range(0.05, 0.95) var crown_rise := 0.25
@export var crown_flare := 0.9
@export var crown_open_out := 1.2
@export var crown_spikes := 11.0
@export_range(0.0, 1.0) var crown_spike_depth := 0.55
@export_range(0.0, 1.0) var crown_breakup_from := 0.3

@export_group("Look")
@export var water_color := Color(0.93, 0.97, 1.0)
## Toon light on the water: shade floor and middle band (higher = paler).
@export var shadow_tone := 0.6
@export var mid_tone := 0.82
## Size of the foam ring on the water (times WaterMarks' / the water shader's
## ring_radius); 0 = none.
@export var ring_size := 1.0

## Shared by every splash of a scene (built on first use): mesh and materials.
static var _cache := {}

var _age := 0.0
var _seed := 0.0
var _size := 1.0
var _shapes: Array[MeshInstance3D] = []


## A splash at `at` (on the water's surface), `size` times the scene's.
static func spawn(scene: PackedScene, parent: Node, at: Vector3, size := 1.0) -> WaterSplash:
	var fx := scene.instantiate() as WaterSplash
	parent.add_child(fx)
	fx.global_position = at
	fx._build(scene, size)
	return fx


## Builds one microscopic splash in front of the camera, so its shader is
## compiled before the first real one (see Explosion.prewarm()).
static func prewarm(scene: PackedScene, parent: Node) -> void:
	var camera := parent.get_viewport().get_camera_3d()
	var at := camera.global_position - camera.global_basis.z * 3.0 if camera else Vector3.ZERO
	var fx := spawn(scene, parent, at, 0.001)
	fx.ring_size = 0.0


func _build(scene: PackedScene, size: float) -> void:
	_size = size
	_seed = randf() * 100.0
	var assets := _assets(scene)
	# The shapes reach far beyond the unit cylinder: give the culling the room.
	var reach := maxf(jet_height, crown_height) * size
	var wide := maxf(jet_radius * (1.0 + jet_flare) * (1.0 + jet_open_out),
		crown_radius * (1.0 + crown_flare) * (1.0 + crown_open_out)) * size
	for material: Material in [assets.jet, assets.crown]:
		var shape := MeshInstance3D.new()
		shape.mesh = assets.mesh
		shape.material_override = material
		shape.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		shape.custom_aabb = AABB(Vector3(-wide, -1.0, -wide), Vector3(wide * 2.0, reach + 2.0, wide * 2.0))
		shape.set_instance_shader_parameter("seed", _seed)
		shape.set_instance_shader_parameter("size", size)
		shape.set_instance_shader_parameter("age", 0.0)
		add_child(shape)
		_shapes.append(shape)
	# Deferred: prewarm() turns the ring off after spawning.
	_add_ring.call_deferred()


func _add_ring() -> void:
	var marks := WaterMarks.find(get_tree())
	if marks and ring_size > 0.0:
		marks.add_ring(global_position, ring_size * _size)


func _process(delta: float) -> void:
	_age += delta
	var t := _age / lifetime
	if t >= 1.0:
		queue_free()
		return
	for shape in _shapes:
		shape.set_instance_shader_parameter("age", t)


func _assets(scene: PackedScene) -> Dictionary:
	if _cache.has(scene):
		return _cache[scene]
	var mesh := CylinderMesh.new()
	mesh.top_radius = 1.0
	mesh.bottom_radius = 1.0
	mesh.height = 1.0
	mesh.radial_segments = 32
	mesh.rings = 12
	mesh.cap_top = false
	mesh.cap_bottom = false
	var jet := _material(jet_height, jet_radius, jet_rise, jet_flare, jet_open_out, jet_spikes,
		jet_spike_depth, jet_breakup_from)
	var crown := _material(crown_height, crown_radius, crown_rise, crown_flare, crown_open_out,
		crown_spikes, crown_spike_depth, crown_breakup_from)
	var assets := {mesh = mesh, jet = jet, crown = crown}
	_cache[scene] = assets
	return assets


func _material(height: float, radius: float, rise: float, flare: float, open_out: float,
		spikes: float, spike_depth: float, breakup_from: float) -> ShaderMaterial:
	var material := ShaderMaterial.new()
	material.shader = SHADER
	material.set_shader_parameter("height", height)
	material.set_shader_parameter("radius", radius)
	material.set_shader_parameter("rise", rise)
	material.set_shader_parameter("flare", flare)
	material.set_shader_parameter("open_out", open_out)
	material.set_shader_parameter("spikes", spikes)
	material.set_shader_parameter("spike_depth", spike_depth)
	material.set_shader_parameter("breakup_from", breakup_from)
	material.set_shader_parameter("water_color", water_color)
	material.set_shader_parameter("shadow_tone", shadow_tone)
	material.set_shader_parameter("mid_tone", mid_tone)
	material.set_shader_parameter("glint", 0.0)
	return material
