class_name WarpPortal
extends Node3D
## A huge swirling warp portal (effects/warp_portal.gdshader on a flat quad),
## facing along its local Z: it bursts open, stays until close() is called,
## then shrinks shut and frees itself. Pure scenery: no collision. The
## destroyer arrives through one (Destroyer.warp_in).

const SHADER := preload("res://effects/warp_portal.gdshader")
## The quad's half-size over the radius (keep in step with the shader's `extent`).
const EXTENT := 1.3
## Distance (m) its sounds carry.
const SOUND_REACH := 6000.0

## Full radius (m).
@export var radius := 230.0
## Seconds to burst open (with a slight overshoot) and to shrink shut.
@export var open_time := 1.5
@export var close_time := 1.0

@export_group("Light")
## A light at the centre, washing nearby ships and rocks in its colour.
@export var light_color := Color(1.0, 0.3, 0.5)
## Energy of the flash as it opens, and while it stays open.
@export var flash_energy := 10.0
@export var light_energy := 3.0
## Light range, as a multiple of the radius.
@export var light_range := 2.5

@export_group("Sound")
## Played as it opens and as it shuts. Heard across the whole mission area
## (the portal is far out), louder close by.
@export var open_sound: AudioStream = preload("res://audio/sfx/explosion_medium.mp3")
@export var open_volume_db := 6.0
@export var open_pitch := 0.3
@export var close_sound: AudioStream = preload("res://audio/sfx/explosion_medium.mp3")
@export var close_volume_db := 0.0
@export var close_pitch := 0.45

var _material: ShaderMaterial
var _light: OmniLight3D
var _closing := false


## A portal at `where` (facing along its basis' Z) under `parent`, opening now.
static func spawn(parent: Node, where: Transform3D, portal_radius: float) -> WarpPortal:
	var portal := WarpPortal.new()
	portal.radius = portal_radius
	parent.add_child(portal)
	portal.global_transform = where
	return portal


func _ready() -> void:
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE * radius * 2.0 * EXTENT
	_material = ShaderMaterial.new()
	_material.shader = SHADER
	_material.set_shader_parameter("extent", EXTENT)
	_material.set_shader_parameter("open", 0.0)
	var disc := MeshInstance3D.new()
	disc.mesh = quad
	disc.material_override = _material
	disc.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(disc)

	_light = OmniLight3D.new()
	_light.light_color = light_color
	_light.light_energy = 0.0
	_light.omni_range = radius * light_range
	add_child(_light)

	var tween := create_tween().set_parallel()
	tween.tween_method(_set_open, 0.0, 1.0, open_time).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tween.tween_property(_light, "light_energy", flash_energy, open_time * 0.3)
	tween.chain().tween_property(_light, "light_energy", light_energy, open_time)
	_play(open_sound, open_volume_db, open_pitch)


## Shrink shut, then free.
func close() -> void:
	if _closing:
		return
	_closing = true
	var tween := create_tween().set_parallel()
	tween.tween_method(_set_open, 1.0, 0.0, close_time).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_IN)
	tween.tween_property(_light, "light_energy", 0.0, close_time)
	tween.chain().tween_callback(queue_free)
	_play(close_sound, close_volume_db, close_pitch)


func _set_open(amount: float) -> void:
	_material.set_shader_parameter("open", maxf(amount, 0.0))


func _play(stream: AudioStream, volume_db: float, pitch: float) -> void:
	# Huge and far out: carry across the whole area. (On the parent, so the
	# closing sound outlives the portal.)
	SoundFX.play_at(get_parent(), stream, global_position, volume_db, pitch, radius, SOUND_REACH)
