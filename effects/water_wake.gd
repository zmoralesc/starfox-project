class_name WaterWake
extends Node3D
## Water splitting under a ship skimming low over it, stronger the lower and
## faster it flies: a V of foam lines spreading behind it on the water, with
## churned foam down the middle (drawn by the water shader from the trail
## this reports to WaterMarks), and two solid sheets of spray thrown up
## either side with lobed top edges (effects/water_spray.gdshader on a plane
## each, moving with the ship).
## Below `start_height` over water it starts; at `full_height` and `full_speed`
## it's at full strength.
##
## A child of the ship (in ship.tscn, so wingmen have it too); it sits on the
## water under the ship, turned to its heading (top_level), and does nothing
## without a `terrain` group node (space missions). Purely visual.

const SPRAY_SHADER := preload("res://effects/water_spray.gdshader")

## Height over the water (m) where the wake starts, and where it's at full
## strength.
@export var start_height := 12.0
@export var full_height := 3.0
## Speed (m/s) for full strength, and how sharply it falls off below it
## (strength goes with (speed / full_speed) ^ speed_curve): 1 is in
## proportion, higher keeps cruising and braking ships calmer while boosting
## stays at full.
@export var full_speed := 105.0
@export var speed_curve := 1.2

@export_group("Spray")
## The sheets at full strength: length back along the track, how far out they
## spread over it and start from the track, their top's height and where along
## it peaks (fraction of the length), how far the top leans out (all metres).
@export var spray_length := 8.0
@export var spray_spread := 4.0
@export var spray_offset := 3.0
## How far ahead of the ship the sheets start (m): from the chase camera the
## water behind the ship is out of sight below it, so the spray has to rise
## beside the ship to be seen.
@export var spray_ahead := 3.0
@export var spray_height := 3.5
@export_range(0.05, 0.95) var spray_peak_at := 0.25
@export var spray_lean := 2.0
## The lobes along their top edges: length (m), how deep the dips between
## them cut (fraction of the height), and how fast they stream back (m/s).
@export var lobe_length := 3.5
@export_range(0.0, 1.0) var lobe_depth := 0.35
@export var churn_speed := 30.0
## How far the foot wobbles in and out (m), in step with the lobes.
@export var foot_wobble := 0.5
## A painted shade along the base of the sheets, where they meet the water:
## its colour and how far up it reaches (fraction of the height).
@export var base_color := Color(0.62, 0.8, 1.0)
@export_range(0.0, 1.0) var base_height := 0.45
@export var water_color := Color(0.93, 0.97, 1.0)
## Toon light on the spray: shade floor and middle band (higher = paler); the
## sun's shadow tint cools the shade.
@export var shadow_tone := 0.55
@export var mid_tone := 0.8

var _ship: Node3D
var _terrain: Terrain
var _marks: WaterMarks
var _sheets: Array[MeshInstance3D] = []
## 0..1, how strong the wake is this frame (read by tests).
var strength := 0.0


func _ready() -> void:
	_ship = get_parent() as Node3D
	top_level = true
	_terrain = get_tree().get_first_node_in_group("terrain") as Terrain
	if _terrain == null:
		set_physics_process(false)
		return
	var mesh := PlaneMesh.new()
	mesh.size = Vector2.ONE
	mesh.subdivide_width = 16
	mesh.subdivide_depth = 6
	var material := ShaderMaterial.new()
	material.shader = SPRAY_SHADER
	material.set_shader_parameter("sheet_length", spray_length)
	material.set_shader_parameter("spread", spray_spread)
	material.set_shader_parameter("start_offset", spray_offset)
	material.set_shader_parameter("ahead", spray_ahead)
	material.set_shader_parameter("sheet_height", spray_height)
	material.set_shader_parameter("peak_at", spray_peak_at)
	material.set_shader_parameter("lean", spray_lean)
	material.set_shader_parameter("lobe_length", lobe_length)
	material.set_shader_parameter("lobe_depth", lobe_depth)
	material.set_shader_parameter("churn_speed", churn_speed)
	material.set_shader_parameter("foot_wobble", foot_wobble)
	material.set_shader_parameter("base_color", base_color)
	material.set_shader_parameter("base_height", base_height)
	material.set_shader_parameter("water_color", water_color)
	material.set_shader_parameter("shadow_tone", shadow_tone)
	material.set_shader_parameter("mid_tone", mid_tone)
	material.set_shader_parameter("glint", 0.0)
	# The shader bends the unit plane far out of its own bounds.
	var reach := spray_offset + spray_spread + spray_lean
	var box := AABB(Vector3(-reach, -1.0, -spray_ahead - 1.0), Vector3(reach * 2.0, spray_height + 2.0, spray_length + 2.0))
	for side: float in [-1.0, 1.0]:
		var sheet := MeshInstance3D.new()
		sheet.mesh = mesh
		sheet.material_override = material
		sheet.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		sheet.custom_aabb = box
		sheet.set_instance_shader_parameter("side", side)
		sheet.visible = false
		add_child(sheet)
		_sheets.append(sheet)


func _physics_process(_delta: float) -> void:
	var at := _ship.global_position
	var water := _terrain.water_level_at(at.x, at.z)
	strength = 0.0
	if _ship.is_visible_in_tree() and water > -INF:
		var low := 1.0 - smoothstep(full_height, start_height, at.y - water)
		var speed := (_ship as CharacterBody3D).velocity.length() if _ship is CharacterBody3D else full_speed
		strength = low * pow(clampf(speed / full_speed, 0.0, 1.0), speed_curve)
	# On the water under the ship, turned to its heading (flattened).
	var forward := -_ship.global_basis.z
	forward.y = 0.0
	if forward.length_squared() > 0.001:
		global_basis = Basis.looking_at(forward.normalized(), Vector3.UP)
	global_position = Vector3(at.x, water if water > -INF else at.y, at.z)
	for sheet in _sheets:
		sheet.visible = strength > 0.02
		sheet.set_instance_shader_parameter("strength", strength)
	if _marks == null:
		_marks = WaterMarks.find(get_tree())
	if _marks:
		_marks.track(_ship, global_position, strength)
