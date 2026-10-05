extends Control
## Draws the targeting reticles, steering cursor and gauges.
##
## The main crosshair sits where the lasers actually aim (Ship.aim_point),
## and turns red when something shootable is under it. Its screen position is
## smoothed so it doesn't jump aggressively when depths change.

const COLOR_IDLE := Color(0.45, 1.0, 0.55, 0.9)
const COLOR_TARGET := Color(1.0, 0.3, 0.25, 1.0)
const COLOR_COVER := Color(0.4, 0.8, 1.0, 0.9)
const COLOR_ORDER := Color(1.0, 0.7, 0.15, 1.0)
const COLOR_WING := Color(0.95, 0.75, 0.3, 0.7)
const COLOR_ENEMY := Color(1.0, 0.25, 0.2, 0.85)
const COLOR_SHIELD := Color(0.35, 0.95, 0.45, 0.95)
const COLOR_SHIELD_DOWN := Color(1.0, 0.3, 0.2, 0.95)
## Thruster bar: full when the thrusters are cool, emptied by throttling.
const COLOR_THRUSTERS := Color(0.4, 0.8, 1.0, 0.9)
## After an overheat the thruster bar refills in red, fading slowly out and
## in once every this many seconds (from full brightness)...
const OVERHEAT_BLINK_PERIOD := 1.0
## ...down to this opacity.
const OVERHEAT_BLINK_MIN_ALPHA := 0.2
## On Form Up, a wingman's order icon blinks slowly while it is still joining
## (not yet firing with you: Wingman.joins_leader_fire()). Only after this many
## seconds, so the moments it drops out of position in a hard turn don't
## flicker the icon...
const JOIN_BLINK_DELAY := 0.4
## ...fading out and back in once every this many seconds...
const JOIN_BLINK_PERIOD := 1.2
## ...down to this fraction of its normal opacity (0 = gone at the low point).
const JOIN_BLINK_MIN_ALPHA := 0.0
## Within this many degrees above or below you, an enemy shows as level.
const RADAR_LEVEL_DEG := 15.0
## ...or within this many metres, for enemies close by.
const RADAR_LEVEL_METRES := 10.0
## Wingmen closer than this to the centre (pixels) are pushed out to it.
const RADAR_WINGMAN_MIN := 9.0
## Enemies beyond radar_range sit on the rim as the same ▲ / ▼ / ■ icons,
## this much smaller and at this opacity.
const RADAR_FAR_SCALE := 0.65
const RADAR_FAR_ALPHA := 0.6
## The destroyer on the radar: its hull outline, this long (pixels) whatever
## the range (to scale it would cover the radar), turned to its heading. Its
## above / below tick (a line, like the wingmen's) is this long.
const RADAR_DESTROYER_LENGTH := 20.0
const RADAR_DESTROYER_TICK := 6.0
const BAR_WIDTH := 220.0
const BAR_HEIGHT := 12.0
## Space between the shield and thruster bars.
const BAR_GAP := 10.0
## Half-size (px) of the icons left of the bars (shield, flame), and the gap
## between an icon and its bar.
const GAUGE_ICON_SIZE := 7.0
const GAUGE_ICON_GAP := 7.0
## Outlines of those icons, in units of GAUGE_ICON_SIZE around their centre
## (y down). Shield: filled, so it doesn't read as the outlined Cover Me icon.
const SHIELD_ICON: Array[Vector2] = [
	Vector2(-0.8, -0.9), Vector2(0.8, -0.9), Vector2(0.8, 0.05), Vector2(0.68, 0.45),
	Vector2(0.4, 0.75), Vector2(0.0, 1.0), Vector2(-0.4, 0.75), Vector2(-0.68, 0.45),
	Vector2(-0.8, 0.05),
]
## Thrusters: a flame, tip up, with a smaller tongue on the left (index 0 is
## the tip, then down the right side to the bottom at FLAME_BOTTOM and up the
## left)...
const FLAME_ICON: Array[Vector2] = [
	Vector2(0.12, -1.0), Vector2(0.38, -0.6), Vector2(0.62, -0.18), Vector2(0.7, 0.25),
	Vector2(0.6, 0.65), Vector2(0.32, 0.93), Vector2(0.0, 1.0), Vector2(-0.32, 0.93),
	Vector2(-0.6, 0.65), Vector2(-0.7, 0.25), Vector2(-0.62, -0.12), Vector2(-0.5, -0.6),
	Vector2(-0.28, -0.28), Vector2(-0.1, -0.55),
]
## ...with a see-through core cut out of it (same order: top first, bottom at
## FLAME_HOLE_BOTTOM).
const FLAME_HOLE: Array[Vector2] = [
	Vector2(0.02, -0.15), Vector2(0.28, 0.25), Vector2(0.34, 0.55), Vector2(0.18, 0.8),
	Vector2(0.0, 0.85), Vector2(-0.18, 0.8), Vector2(-0.34, 0.55), Vector2(-0.26, 0.25),
]
const FLAME_BOTTOM := 6
const FLAME_HOLE_BOTTOM := 4
## Half-size of the order icons on the wing panel cards, in pixels.
const ORDER_ICON_SIZE := 8.0
## Size of the whole wing panel (cards, gaps, icons, text) relative to its
## base layout: 56 px cards, 13 px names.
const WING_PANEL_SCALE := 1.15
## Corner radius (px) of the wing panel cards' backgrounds.
const CARD_CORNER_RADIUS := 6
## Width and height of the triangle over each wingman, in pixels.
const WINGMAN_MARKER_SIZE := Vector2(36.0, 29.0)
## Size of the initial inside it. Independent of the triangle size.
const WINGMAN_INITIAL_SIZE := 15
## Hit-direction marker: distance from the screen centre (fraction of the
## smaller screen side), half the arc's angle, and its thickness.
const HIT_MARKER_RADIUS := 0.36
const HIT_MARKER_SPREAD_DEG := 20.0
const HIT_MARKER_WIDTH := 6.0

## How far the radar sees, in metres.
@export var radar_range := 500.0
## Radius of the radar on screen, in pixels of the 1152×648 base layout. It
## grows down and to the right from the top-left corner; blips keep their size.
@export_range(40.0, 160.0, 1.0, "suffix:px") var radar_radius := 80.0

@export_group("Enemy markers")
## Enemy fighters get brackets only within this distance of the crosshair (in
## pixels of the base layout). They pop in and out at the edge, no fade, like
## a combat visor locking on.
@export_range(20.0, 400.0, 1.0, "suffix:px") var enemy_marker_radius := 180.0
## No brackets on enemies that something solid (terrain, an asteroid, the
## destroyer) hides from the camera, so they can't be tracked through cover.
## Clouds don't count: they have no collision.
@export var hide_hidden_enemies := true

@export_group("Pilot senses")
## Off-screen enemy fighters closer than this (m) get a faint arrow at the edge
## of the screen, Fox sensing them before he sees them. Kept short so finding
## enemies is still the radar's job (radar_range is 500 m); only the ones
## about to matter show.
@export var sense_range := 150.0
## Within this distance the arrow is at full strength (sense_opacity); it fades
## out from here to sense_range.
@export var sense_full_range := 50.0
@export_range(0.0, 1.0) var sense_opacity := 0.85
## Length of the arrows, in pixels of the base layout.
@export var sense_arrow_length := 16.0

## Points from kills. Not shown at the moment; kept for a mission-end screen.
var score := 0

var _ship: Ship
var _wing: WingCommand
var _destroyer: Destroyer
var _boundary: PlayBoundary
var _font: Font
## Bold version of _font, for the wingman initials.
var _bold_font: FontVariation
## One-shot SubViewports holding the wingman markers (see _wingman_marker()), keyed by
## initial and colour, and the gauge icons (_gauge_icon_texture()). Cleared when the window is resized.
var _marker_cache := {}

var _crosshair_pos := Vector2.ZERO
## Enemy fighters the camera can't see right now (something solid in between),
## updated each physics tick by _update_hidden_enemies().
var _hidden_enemies := {}
## Seconds each wingman has been joining on Form Up (0 once it fires with you),
## keyed by Wingman. Drives the order icon blink (JOIN_BLINK_DELAY).
var _joining_for := {}
## Seconds since the thrusters overheated (0 while they work): times the
## thruster bar's blink.
var _overheated_for := 0.0
## Background of the wing panel cards (_draw_card_frame() sets its colour).
var _card_style := StyleBoxFlat.new()
## The flame icon's fill as two hole-free halves (see _split_ring()).
var _flame_halves: Array = []


func _ready() -> void:
	add_to_group("hud")
	# The project font (Project Settings > GUI > Theme > Custom Font), like every menu.
	_font = get_theme_default_font()
	_bold_font = FontVariation.new()
	_bold_font.base_font = _font
	_bold_font.variation_embolden = 0.9
	get_viewport().size_changed.connect(_clear_marker_cache)
	_card_style.set_corner_radius_all(roundi(CARD_CORNER_RADIUS * WING_PANEL_SCALE))
	_flame_halves = _split_ring(FLAME_ICON, FLAME_HOLE, FLAME_BOTTOM, FLAME_HOLE_BOTTOM)



func add_score(points: int) -> void:
	score += points


func _process(delta: float) -> void:
	if not is_instance_valid(_destroyer):
		_destroyer = get_tree().get_first_node_in_group("destroyer") as Destroyer
	if not is_instance_valid(_boundary):
		_boundary = get_tree().get_first_node_in_group("boundary") as PlayBoundary
	if not is_instance_valid(_ship):
		_ship = get_tree().get_first_node_in_group("player") as Ship
	if not is_instance_valid(_wing):
		_wing = get_tree().get_first_node_in_group("wing_command") as WingCommand
	if is_instance_valid(_wing):
		for wingman in _wing.wingmen():
			var joining := wingman.order == Wingman.Order.FORM_UP and not wingman.joins_leader_fire()
			_joining_for[wingman] = _joining_for.get(wingman, 0.0) + delta if joining else 0.0
	if is_instance_valid(_ship):
		_overheated_for = _overheated_for + delta if _ship.overheated else 0.0
	queue_redraw()


func _physics_process(_delta: float) -> void:
	_update_hidden_enemies()


func _draw() -> void:
	var cam := get_viewport().get_camera_3d()
	if _ship == null or cam == null:
		return

	if _ship.damage_flash > 0.0:
		# Blue: the shields took it.
		draw_rect(Rect2(Vector2.ZERO, size), Color(0.2, 0.45, 1.0, 0.2 * _ship.damage_flash))

	if _ship.shields_down and not _ship.is_dead and fmod(Time.get_ticks_msec() / 1000.0, 0.8) < 0.5:
		draw_string(_font, Vector2(0.0, size.y * 0.5 + 90.0), "SHIELDS DOWN",
			HORIZONTAL_ALIGNMENT_CENTER, size.x, 24, COLOR_SHIELD_DOWN)

	if _ship.is_dead:
		draw_string(_font, Vector2(0.0, size.y * 0.5), "SHIP DESTROYED",
			HORIZONTAL_ALIGNMENT_CENTER, size.x, 40, COLOR_TARGET)
		_draw_gauges()
		return

	var color := COLOR_TARGET if _ship.aim_on_target else COLOR_IDLE
	if not cam.is_position_behind(_ship.aim_point):
		var target_pos := cam.unproject_position(_ship.aim_point)
		if _crosshair_pos == Vector2.ZERO:
			_crosshair_pos = target_pos
		else:
			_crosshair_pos = _crosshair_pos.lerp(target_pos, 1.0 - exp(-25.0 * get_process_delta_time()))
		_draw_reticle(_crosshair_pos, 20.0, color)

	if _boundary:
		_draw_boundary_warning()
	if is_instance_valid(_destroyer):
		_draw_destroyer(cam, _destroyer)
	_draw_enemies(cam)
	_draw_hit_direction(cam)
	_draw_wingmen(cam)
	_draw_order_markers(cam)
	_draw_radar()
	# The steering cursor shows where the mouse is steering; hidden on a gamepad.
	if not Settings.using_gamepad:
		_draw_stick_cursor()
	_draw_gauges()


## Destroyer: inbound warning, brackets on intact parts (bridge and thrusters,
## which must die to kill it, are brightest), edge arrow. Peppy also calls
## it out over the comms (MissionControl.announce_destroyer).
func _draw_destroyer(cam: Camera3D, destroyer: Destroyer) -> void:
	if destroyer.age < 6.0 and fmod(destroyer.age, 0.8) < 0.5:
		draw_string(_font, Vector2(0.0, 120.0), "WARNING: DESTROYER INBOUND",
			HORIZONTAL_ALIGNMENT_CENTER, size.x, 28, COLOR_TARGET)

	var visible_rect := Rect2(Vector2.ZERO, size).grow(-24.0)
	var center_visible := false
	if not cam.is_position_behind(destroyer.global_position):
		center_visible = visible_rect.has_point(cam.unproject_position(destroyer.global_position))
	if not center_visible:
		_draw_edge_arrow(cam, destroyer.global_position, COLOR_ORDER, 22.0)
	if not destroyer.is_damageable():
		return  # still arriving (or dying): nothing to shoot yet
	for part in destroyer.all_parts():
		if part.is_destroyed or cam.is_position_behind(part.global_position):
			continue
		if _ship.global_position.distance_to(part.global_position) > 1200.0:
			continue
		var p := cam.unproject_position(part.global_position)
		if not visible_rect.has_point(p):
			continue
		match part.kind:
			DestroyerPart.Kind.BRIDGE, DestroyerPart.Kind.THRUSTER:
				_draw_brackets(p, 14.0, COLOR_TARGET)
			DestroyerPart.Kind.HANGAR:
				_draw_brackets(p, 12.0, COLOR_ORDER)
			_:
				_draw_brackets(p, 8.0, Color(COLOR_ENEMY, 0.5))


## Brackets on enemy fighters, one colour whatever they're doing (their
## behaviour shows in how they fly). Only near the crosshair (fading out with
## distance from it), to line up a shot, and never on enemies hidden behind
## terrain, rocks or the destroyer: brackets shouldn't see through cover
## (clouds don't count). Off-screen enemies only get an arrow when very close
## (see sense_range): finding them is the radar's job.
func _draw_enemies(cam: Camera3D) -> void:
	var visible_rect := Rect2(Vector2.ZERO, size).grow(-24.0)
	for enemy: EnemyFighter in get_tree().get_nodes_in_group("enemies"):
		var pos := enemy.global_position
		var on_screen := not cam.is_position_behind(pos) and visible_rect.has_point(cam.unproject_position(pos))
		if not on_screen:
			_draw_sense_arrow(cam, pos)
			continue
		var p := cam.unproject_position(pos)
		if not _hidden_enemies.has(enemy) and p.distance_to(_crosshair_pos) <= enemy_marker_radius:
			_draw_brackets(p, 10.0, COLOR_ENEMY)


## "Pilot senses": an edge arrow towards an off-screen enemy at `pos`, only
## within sense_range of the ship, fading out with distance.
func _draw_sense_arrow(cam: Camera3D, pos: Vector3) -> void:
	var distance := _ship.global_position.distance_to(pos)
	if distance >= sense_range:
		return
	var strength := 1.0 - smoothstep(sense_full_range, sense_range, distance)
	_draw_edge_arrow(cam, pos, Color(COLOR_ENEMY, COLOR_ENEMY.a * sense_opacity * strength), sense_arrow_length)


## Which enemy fighters something solid hides from the camera: one ray per
## enemy against the World layer (terrain, water, asteroids, destroyer hull;
## not ships or hurtboxes). Physics queries belong in the physics step, so
## this runs there and _draw() reads the result.
func _update_hidden_enemies() -> void:
	_hidden_enemies.clear()
	var cam := get_viewport().get_camera_3d()
	if not hide_hidden_enemies or cam == null:
		return
	var space := cam.get_world_3d().direct_space_state
	var from := cam.global_position
	for enemy: EnemyFighter in get_tree().get_nodes_in_group("enemies"):
		var to := enemy.global_position
		if cam.is_position_behind(to):
			continue
		var query := PhysicsRayQueryParameters3D.create(from, to, Fighter.LAYER_WORLD)
		if not space.intersect_ray(query).is_empty():
			_hidden_enemies[enemy] = true


## A red arc around the screen centre on the side a shot that just hit you
## came from (below = from behind), fading out. Tells you where to turn when
## something you can't see is shooting at you.
func _draw_hit_direction(cam: Camera3D) -> void:
	if _ship.shot_flash <= 0.0:
		return
	var local := cam.global_transform.affine_inverse() * _ship.last_shot_from
	var dir := Vector2(local.x, -local.y)
	if dir.length() < 0.01:
		dir = Vector2.DOWN  # straight behind
	var angle := dir.angle()
	var spread := deg_to_rad(HIT_MARKER_SPREAD_DEG)
	var radius := minf(size.x, size.y) * HIT_MARKER_RADIUS
	draw_arc(size * 0.5, radius, angle - spread, angle + spread, 24,
		Color(COLOR_TARGET, 0.9 * _ship.shot_flash), HIT_MARKER_WIDTH, true)


## A solid downward triangle over each wingman in its own colour, with its
## initial in white, so you can find them when they split off. It looks the
## same whether or not the wingman is selected (the wing panel shows that).
## The triangle and letter are drawn once into a texture per wingman
## (_wingman_marker()); each frame only places that texture.
func _draw_wingmen(cam: Camera3D) -> void:
	for wingman: Wingman in get_tree().get_nodes_in_group("wingmen"):
		var pos := wingman.global_position + cam.global_basis.y * 4.0
		if cam.is_position_behind(pos):
			continue
		var p := cam.unproject_position(pos)
		var marker_size := WINGMAN_MARKER_SIZE
		# Tip at the point above the ship, flat side on top.
		draw_texture_rect(_wingman_marker(wingman),
			Rect2(p - Vector2(marker_size.x * 0.5, marker_size.y), marker_size), false)


## The texture of a wingman's marker, drawn the first time it's needed: a
## one-shot SubViewport renders the triangle and initial at the screen's real
## resolution (so it stays sharp when the HUD is stretched), then keeps the
## result.
func _wingman_marker(wingman: Wingman) -> Texture2D:
	var initial := wingman.call_sign.left(1)
	var color := wingman.accent_color
	var key := "%s|%s" % [initial, color.to_html()]
	if _marker_cache.has(key):
		return (_marker_cache[key] as SubViewport).get_texture()

	# Screen pixels per HUD pixel.
	var bake_scale := maxf(get_viewport().get_final_transform().get_scale().y, 1.0)
	var marker_size := WINGMAN_MARKER_SIZE
	var viewport := SubViewport.new()
	viewport.size = Vector2i((marker_size * bake_scale).ceil())
	viewport.transparent_bg = true
	viewport.disable_3d = true
	viewport.render_target_update_mode = SubViewport.UPDATE_ONCE
	var canvas := Node2D.new()
	canvas.scale = Vector2.ONE * bake_scale
	canvas.draw.connect(func() -> void:
		canvas.draw_colored_polygon(PackedVector2Array([
			Vector2.ZERO, Vector2(marker_size.x, 0.0), Vector2(marker_size.x * 0.5, marker_size.y)
		]), Color(color, 0.85))
		var font_size := WINGMAN_INITIAL_SIZE
		# The initial sits in the wide upper part of the triangle.
		var baseline := marker_size.y * 0.38 + font_size * 0.36
		canvas.draw_string(_bold_font, Vector2(0.0, baseline), initial,
			HORIZONTAL_ALIGNMENT_CENTER, marker_size.x, font_size, Color.WHITE))
	viewport.add_child(canvas)
	add_child(viewport)
	_marker_cache[key] = viewport
	return viewport.get_texture()


## Throws the cached markers away (after a resize), to redraw them sharp at
## the new scale.
func _clear_marker_cache() -> void:
	for viewport: SubViewport in _marker_cache.values():
		if is_instance_valid(viewport):
			viewport.queue_free()
	_marker_cache.clear()


## An orange diamond on whatever a wingman was ordered to Attack, labelled
## with who's on it, or an arrow at the screen edge when it's off screen.
## Targets picked by Cover Me or Weapons Free aren't marked.
func _draw_order_markers(cam: Camera3D) -> void:
	var by_target := {}
	for wingman: Wingman in get_tree().get_nodes_in_group("wingmen"):
		if wingman.order == Wingman.Order.ATTACK and wingman.state == Wingman.State.ATTACK \
				and not Wingman.target_gone(wingman.target):
			if not by_target.has(wingman.target):
				by_target[wingman.target] = []
			by_target[wingman.target].append(wingman)
	for target: Node3D in by_target:
		var attackers: Array = by_target[target]
		attackers.sort_custom(func(a: Wingman, b: Wingman) -> bool: return a.wing_index < b.wing_index)
		var initials := " ".join(PackedStringArray(attackers.map(func(w: Wingman) -> String: return w.call_sign.left(1))))
		_draw_order_marker(cam, target, COLOR_ORDER, initials)


func _draw_order_marker(cam: Camera3D, target: Node3D, color: Color, label: String) -> void:
	var pos := target.global_position
	var visible_rect := Rect2(Vector2.ZERO, size).grow(-30.0)
	if not cam.is_position_behind(pos):
		var p := cam.unproject_position(pos)
		if visible_rect.has_point(p):
			var r := 26.0
			draw_polyline(PackedVector2Array([
				p + Vector2(0, -r), p + Vector2(r, 0), p + Vector2(0, r), p + Vector2(-r, 0), p + Vector2(0, -r)
			]), color, 2.0, true)
			var dist := roundi(_ship.global_position.distance_to(pos))
			draw_string(_font, p + Vector2(r + 6.0, 0.0), label, HORIZONTAL_ALIGNMENT_LEFT, -1, 13, color)
			draw_string(_font, p + Vector2(r + 6.0, 15.0), "%dm" % dist, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, color)
			return
	_draw_edge_arrow(cam, pos, color, 18.0)


## Arrow near the screen edge pointing towards an off-screen world position.
func _draw_edge_arrow(cam: Camera3D, pos: Vector3, color: Color, length: float) -> void:
	# Use the direction in camera space so points behind us still work.
	var local := cam.global_transform.affine_inverse() * pos
	var dir := Vector2(local.x, -local.y)
	dir = dir.normalized() if dir.length() > 0.001 else Vector2.UP
	var tip := size * 0.5 + dir * (minf(size.x, size.y) * 0.5 - 40.0)
	var side := dir.orthogonal() * length * 0.5
	draw_colored_polygon(PackedVector2Array([tip, tip - dir * length + side, tip - dir * length - side]), color)


func _draw_reticle(center: Vector2, r: float, color: Color) -> void:
	draw_arc(center, r, 0.0, TAU, 48, color, 2.0, true)
	for dir: Vector2 in [Vector2.UP, Vector2.DOWN, Vector2.LEFT, Vector2.RIGHT]:
		draw_line(center + dir * (r - 6.0), center + dir * (r + 8.0), color, 2.0, true)
	draw_circle(center, 2.0, color)


func _draw_brackets(center: Vector2, r: float, color: Color) -> void:
	for corner: Vector2 in [Vector2(-1, -1), Vector2(1, -1), Vector2(-1, 1), Vector2(1, 1)]:
		var p := center + corner * r
		draw_line(p, p - Vector2(corner.x * r * 0.5, 0.0), color, 2.0, true)
		draw_line(p, p - Vector2(0.0, corner.y * r * 0.5), color, 2.0, true)


func _draw_stick_cursor() -> void:
	var center := size * 0.5
	var radius := minf(size.x, size.y) * 0.28
	draw_arc(center, radius, 0.0, TAU, 96, Color(1, 1, 1, 0.07), 1.5, true)
	var p := center + _ship.stick * radius
	if _ship.stick.length() > 0.02:
		draw_line(center, p, Color(1, 1, 1, 0.12), 1.0, true)
	draw_arc(p, 5.0, 0.0, TAU, 24, Color(1, 1, 1, 0.5), 1.5, true)


## Radar, top left. Always oriented like the ship: straight ahead is up,
## right is right, and it turns and rolls with you. Shows enemy fighters within
## radar_range (▲ above you, ▼ below, ■ roughly level) and the wingmen as dots
## in their own colours (a tick above or below the dot for height).
func _draw_radar() -> void:
	var r := radar_radius
	var center := Vector2(28.0 + r, 28.0 + r)
	draw_circle(center, r, Color(0.0, 0.02, 0.04, 0.5))
	draw_arc(center, r, 0.0, TAU, 64, Color(COLOR_IDLE, 0.35), 1.5, true)
	draw_arc(center, r * 0.5, 0.0, TAU, 48, Color(COLOR_IDLE, 0.15), 1.0, true)
	draw_line(center + Vector2(0.0, -r), center + Vector2(0.0, -r + 7.0), Color(COLOR_IDLE, 0.6), 1.5)
	# You: a chevron in the middle, pointing ahead (up).
	draw_colored_polygon(PackedVector2Array([
		center + Vector2(0.0, -5.0), center + Vector2(4.0, 4.0), center + Vector2(0.0, 2.0), center + Vector2(-4.0, 4.0)
	]), Color(1, 1, 1, 0.8))

	var to_local := _ship.global_transform.affine_inverse()
	# The destroyer first, so fighters around it draw on top.
	for node in get_tree().get_nodes_in_group("destroyer"):
		_draw_radar_destroyer(node as Destroyer, center, to_local)
	for wingman: Wingman in get_tree().get_nodes_in_group("wingmen"):
		var local := to_local * wingman.global_position
		if local.length() > radar_range:
			continue
		# Wingmen in formation would sit right on top of you; keep them a few
		# pixels out in their real direction so the formation stays readable.
		var offset := Vector2(local.x, local.z) / radar_range * r
		if offset.length() < RADAR_WINGMAN_MIN and offset.length() > 0.01:
			offset = offset.normalized() * RADAR_WINGMAN_MIN
		var p := center + offset
		var color := Color(wingman.accent_color, 1.0)
		draw_circle(p, 3.0, color)
		var height := _radar_height(local)
		if height != 0:
			draw_line(p + Vector2(0.0, -3.0 * height), p + Vector2(0.0, -7.0 * height), color, 1.5)

	for enemy: Node3D in get_tree().get_nodes_in_group("enemies"):
		var local := to_local * enemy.global_position
		var flat := Vector2(local.x, local.z)
		if local.length() > radar_range:
			# Out of range: a small dim icon on the rim in its direction (still
			# showing above / below / level), so you can find a far-off wave.
			if flat.length() > 0.01:
				_draw_radar_enemy(center + flat.normalized() * r, _radar_height(local), RADAR_FAR_SCALE,
					Color(COLOR_ENEMY, RADAR_FAR_ALPHA))
			continue
		_draw_radar_enemy(center + flat / radar_range * r, _radar_height(local), 1.0, COLOR_ENEMY)


## The destroyer on the radar centred on `center`: a small silhouette of its
## hull (hull_outline), pointing where it's heading; on the rim, smaller and
## dimmer, while its centre is beyond radar_range (like fighters).
func _draw_radar_destroyer(destroyer: Destroyer, center: Vector2, to_local: Transform3D) -> void:
	if destroyer == null or destroyer.hull_outline.size() < 3:
		return
	var r := radar_radius
	var local := to_local * destroyer.global_position
	var flat := Vector2(local.x, local.z)
	var icon_scale := 1.0
	var color := COLOR_ENEMY
	var p := center + flat / radar_range * r
	if local.length() > radar_range:
		if flat.length() < 0.01:
			return
		p = center + flat.normalized() * r
		icon_scale = RADAR_FAR_SCALE
		color = Color(COLOR_ENEMY, RADAR_FAR_ALPHA)
	# Its x and z axes on the radar (the ship's local x / z), so the outline
	# turns with its heading relative to you.
	var axis_x := to_local.basis * destroyer.global_basis.x
	var axis_z := to_local.basis * destroyer.global_basis.z
	var ax := Vector2(axis_x.x, axis_x.z)
	var az := Vector2(axis_z.x, axis_z.z)
	var bounds := Rect2(destroyer.hull_outline[0], Vector2.ZERO)
	for point in destroyer.hull_outline:
		bounds = bounds.expand(point)
	var k := RADAR_DESTROYER_LENGTH * icon_scale / maxf(bounds.size.y, 1.0)
	var mid := bounds.get_center()
	var shape := PackedVector2Array()
	for point in destroyer.hull_outline:
		shape.append(p + (ax * (point.x - mid.x) + az * (point.y - mid.y)) * k)
	draw_colored_polygon(shape, color)
	var height := _radar_height(local)
	if height != 0:
		var tick := RADAR_DESTROYER_TICK * icon_scale
		var edge := (RADAR_DESTROYER_LENGTH * 0.5 + 1.0) * icon_scale  # clear of the outline at any heading
		draw_line(p + Vector2(0.0, -edge * height), p + Vector2(0.0, -(edge + tick) * height), color, 1.5)


## An enemy on the radar at `p`: ▲ above you (`height` 1), ▼ below (-1), ■ level
## (0), `icon_scale` times the full size.
func _draw_radar_enemy(p: Vector2, height: int, icon_scale: float, color: Color) -> void:
	var s := icon_scale
	match height:
		1:
			draw_colored_polygon(PackedVector2Array([p + Vector2(0, -5) * s, p + Vector2(4.5, 3.5) * s, p + Vector2(-4.5, 3.5) * s]), color)
		-1:
			draw_colored_polygon(PackedVector2Array([p + Vector2(0, 5) * s, p + Vector2(4.5, -3.5) * s, p + Vector2(-4.5, -3.5) * s]), color)
		_:
			draw_rect(Rect2(p - Vector2(3.5, 3.5) * s, Vector2(7.0, 7.0) * s), color)


## 1 if a position (in the ship's local space) is above you, -1 if below, 0 if
## roughly level: within RADAR_LEVEL_DEG up or down, or RADAR_LEVEL_METRES for
## things close by, so icons don't flicker as they pass.
func _radar_height(local: Vector3) -> int:
	var horizontal := Vector2(local.x, local.z).length()
	var level := maxf(RADAR_LEVEL_METRES, horizontal * tan(deg_to_rad(RADAR_LEVEL_DEG)))
	if local.y > level:
		return 1
	if local.y < -level:
		return -1
	return 0


## Shield and thruster heat bars, top right (the comms box has the bottom left),
## then the wing panel. Bars only, no numbers. While the shields are down, the
## shield bar turns red and fills up as they reboot.
func _draw_gauges() -> void:
	var origin := Vector2(size.x - 28.0 - BAR_WIDTH, 32.0)
	if _ship.shields_down:
		_draw_bar(origin, _ship.shield_reboot_progress(), Color(COLOR_SHIELD_DOWN, 0.6))
		_draw_gauge_icon("shield", [SHIELD_ICON], [SHIELD_ICON], origin, COLOR_SHIELD_DOWN)
	else:
		_draw_bar(origin, _ship.shields / _ship.max_shields, COLOR_SHIELD)
		_draw_gauge_icon("shield", [SHIELD_ICON], [SHIELD_ICON], origin, COLOR_SHIELD)
	# Thrusters underneath: a blue bar that throttling empties (it shows how
	# much throttle is left before they overheat). Overheated, it refills over
	# the lockout, red and slowly blinking; the throttle works again once full.
	var thruster_color := COLOR_THRUSTERS
	if _ship.overheated:
		var wave := 0.5 + 0.5 * cos(TAU * _overheated_for / OVERHEAT_BLINK_PERIOD)
		thruster_color = Color(COLOR_SHIELD_DOWN, COLOR_SHIELD_DOWN.a * lerpf(OVERHEAT_BLINK_MIN_ALPHA, 1.0, wave))
	var thruster_origin := origin + Vector2(0.0, BAR_HEIGHT + BAR_GAP)
	_draw_bar(thruster_origin, 1.0 - _ship.thruster_heat, thruster_color)
	_draw_gauge_icon("flame", _flame_halves, [FLAME_ICON, FLAME_HOLE], thruster_origin, thruster_color)
	if _wing:
		_draw_wing_panel()


## Wing panel, bottom right, laid out like the D-pad that selects the wingmen:
## Falco on the left, Slippy on top, Krystal on the right, ALL below. Each card
## shows an icon for the current order above the call sign; selected cards light
## up. The middle shows who the next order will go to. (What a wingman is doing
## right now isn't shown: you can see it.)
func _draw_wing_panel() -> void:
	# Wingman cards (and the middle) are W × H squares; ALL is W × ALL_H. All
	# sizes are the base layout times WING_PANEL_SCALE (k).
	const k := WING_PANEL_SCALE
	const W := 56.0 * k
	const H := W
	const GAP := 5.0 * k
	const ALL_H := 20.0 * k
	var right := size.x - 24.0
	var bottom := size.y - 24.0
	var left := right - 3.0 * W - 2.0 * GAP
	var top := bottom - ALL_H - 2.0 * H - 2.0 * GAP
	# The icon-over-name stack is 44 px tall (base): centre it in the square.
	var stack_offset := (H - 44.0 * k) * 0.5
	var cells := {
		0: Rect2(left, top + H + GAP, W, H),                 	# Falco: D-pad left
		1: Rect2(left + W + GAP, top, W, H),                 	# Slippy: D-pad up
		2: Rect2(left + 2.0 * (W + GAP), top + H + GAP, W, H),  # Krystal: D-pad right
	}
	var pad: bool = Settings.using_gamepad
	var select_actions := [&"select_wingman_1", &"select_wingman_2", &"select_wingman_3"]
	for wingman in _wing.wingmen():
		if not cells.has(wingman.wing_index):
			continue
		var rect: Rect2 = cells[wingman.wing_index]
		var key := "" if pad else _short_key(select_actions[wingman.wing_index])
		_draw_wing_card(rect, wingman, _wing.is_selected(wingman), key, stack_offset)

	# ALL, under the middle (D-pad down).
	var all_rect := Rect2(left + W + GAP, top + 2.0 * (H + GAP), W, ALL_H)
	var everyone := _wing.wingmen()
	var all_selected := not everyone.is_empty() and _wing.selected.size() == everyone.size()
	_draw_card_frame(all_rect, COLOR_IDLE, all_selected)
	draw_string(_font, all_rect.position + Vector2(0.0, 15.0 * k), "ALL", HORIZONTAL_ALIGNMENT_CENTER, W, roundi(13 * k),
		Color(1, 1, 1, 0.95) if all_selected else Color(COLOR_IDLE, 0.8))
	if not pad:
		draw_string(_font, all_rect.position + Vector2(5.0, 14.0) * k, _short_key(&"select_all"),
			HORIZONTAL_ALIGNMENT_LEFT, -1, roundi(10 * k), Color(1, 1, 1, 0.4))

	# Middle: who gets the next order.
	var middle := Rect2(left + W + GAP, top + H + GAP, W, H)
	var to := _wing.recipients()
	var to_text := " ".join(PackedStringArray(to.map(func(w: Wingman) -> String: return w.call_sign.left(1))))
	draw_string(_font, middle.position + Vector2(0.0, 15.0 * k + stack_offset), "ORDERS TO", HORIZONTAL_ALIGNMENT_CENTER, W, roundi(10 * k),
		Color(1, 1, 1, 0.45))
	draw_string(_font, middle.position + Vector2(0.0, 32.0 * k + stack_offset), to_text if to_text != "" else "NOBODY",
		HORIZONTAL_ALIGNMENT_CENTER, W, roundi(14 * k), COLOR_IDLE if to_text != "" else COLOR_TARGET)


func _draw_wing_card(rect: Rect2, wingman: Wingman, selected: bool, key: String, stack_offset: float) -> void:
	_draw_card_frame(rect, wingman.accent_color, selected)
	var order_color := COLOR_IDLE
	match wingman.order:
		Wingman.Order.ATTACK:
			order_color = COLOR_ORDER
		Wingman.Order.COVER_ME:
			order_color = COLOR_COVER
		Wingman.Order.WEAPONS_FREE:
			order_color = COLOR_TARGET
	# Still joining on Form Up: the icon fades slowly out and in, starting from
	# full brightness.
	var joining: float = _joining_for.get(wingman, 0.0) - JOIN_BLINK_DELAY
	if joining > 0.0:
		order_color.a *= lerpf(JOIN_BLINK_MIN_ALPHA, 1.0, 0.5 + 0.5 * cos(TAU * joining / JOIN_BLINK_PERIOD))
	# Stacked and centred: order icon on top, NAME under it; key in the corner.
	# Base layout sizes, times WING_PANEL_SCALE.
	const k := WING_PANEL_SCALE
	var icon_size := ORDER_ICON_SIZE * k
	var icon_center := Vector2(rect.get_center().x, rect.position.y + stack_offset + 4.0 * k + icon_size)
	_draw_order_icon(wingman.order, icon_center, icon_size, order_color)
	draw_string(_font, rect.position + Vector2(0.0, stack_offset + 38.0 * k), wingman.call_sign.to_upper(),
		HORIZONTAL_ALIGNMENT_CENTER, rect.size.x, roundi(13 * k), Color(wingman.accent_color, 1.0))
	if key != "":
		draw_string(_font, rect.position + Vector2(5.0, 13.0) * k, key, HORIZONTAL_ALIGNMENT_LEFT, -1, roundi(10 * k),
			Color(1, 1, 1, 0.4))


## Small symbol for a wingman order, `half_size` px from the centre to the edge:
## Form Up = three ships in a V, Attack = crosshair, Cover Me = shield,
## Weapons Free = burst.
func _draw_order_icon(order: Wingman.Order, c: Vector2, half_size: float, color: Color) -> void:
	var s := half_size
	match order:
		Wingman.Order.FORM_UP:
			for offset in [Vector2(0.0, -0.55), Vector2(-0.85, 0.45), Vector2(0.85, 0.45)]:
				draw_circle(c + offset * s, s * 0.28, color)
		Wingman.Order.ATTACK:
			draw_arc(c, s * 0.62, 0.0, TAU, 20, color, 1.5, true)
			for dir in [Vector2.UP, Vector2.DOWN, Vector2.LEFT, Vector2.RIGHT]:
				draw_line(c + dir * s * 0.35, c + dir * s, color, 1.5, true)
		Wingman.Order.COVER_ME:
			draw_polyline(PackedVector2Array([
				c + Vector2(-0.8, -0.85) * s, c + Vector2(0.8, -0.85) * s, c + Vector2(0.8, 0.05) * s,
				c + Vector2(0.0, 0.95) * s, c + Vector2(-0.8, 0.05) * s, c + Vector2(-0.8, -0.85) * s,
			]), color, 1.5, true)
		Wingman.Order.WEAPONS_FREE:
			for k in 8:
				var dir := Vector2.from_angle(k * TAU / 8.0)
				var inner := 0.3 if k % 2 == 0 else 0.5
				draw_line(c + dir * s * inner, c + dir * s, color, 1.5, true)


## A card's translucent rounded background, no outline: dark, or tinted in
## `color` when selected.
func _draw_card_frame(rect: Rect2, color: Color, selected: bool) -> void:
	_card_style.bg_color = Color(color, 0.22) if selected else Color(0.0, 0.02, 0.04, 0.45)
	draw_style_box(_card_style, rect)


## Keyboard key for an action's primary binding, shortened for a card corner.
func _short_key(action: StringName) -> String:
	var event := Settings.get_binding(action, Settings.Slot.PRIMARY)
	return Settings.event_name(event).left(3) if event else ""


## One of the icons left of the bars, for the bar at `bar_pos`, tinted `color`.
## `key` names its cached texture (see _gauge_icon_texture()).
func _draw_gauge_icon(key: String, fills: Array, outlines: Array, bar_pos: Vector2, color: Color) -> void:
	var center := bar_pos + Vector2(-GAUGE_ICON_GAP - GAUGE_ICON_SIZE * 0.8, BAR_HEIGHT * 0.5)
	var half := Vector2.ONE * (GAUGE_ICON_SIZE + 1.0)
	draw_texture_rect(_gauge_icon_texture(key, fills, outlines), Rect2(center - half, half * 2.0), false, color)


## A gauge icon drawn once, white and opaque, into a texture (a one-shot
## SubViewport at the screen's real resolution, like _wingman_marker()), then
## tinted when placed. Drawn directly instead, a translucent icon (the blinking
## flame) showed darker lines where its outline and fill pieces overlap.
## `fills`: shapes to fill; `outlines`: closed loops drawn round them,
## antialiased (the fill alone is jagged at this size); both in icon units.
func _gauge_icon_texture(key: String, fills: Array, outlines: Array) -> Texture2D:
	var cache_key := "icon|" + key
	if _marker_cache.has(cache_key):
		return (_marker_cache[cache_key] as SubViewport).get_texture()
	var bake_scale := maxf(get_viewport().get_final_transform().get_scale().y, 1.0)
	var half := Vector2.ONE * (GAUGE_ICON_SIZE + 1.0)
	var viewport := SubViewport.new()
	viewport.size = Vector2i((half * 2.0 * bake_scale).ceil())
	viewport.transparent_bg = true
	viewport.disable_3d = true
	viewport.render_target_update_mode = SubViewport.UPDATE_ONCE
	var canvas := Node2D.new()
	canvas.scale = Vector2.ONE * bake_scale
	canvas.draw.connect(func() -> void:
		for shape: Array[Vector2] in fills:
			canvas.draw_colored_polygon(_icon_points(shape, half), Color.WHITE)
		for shape: Array[Vector2] in outlines:
			var points := _icon_points(shape, half)
			points.append(points[0])
			canvas.draw_polyline(points, Color.WHITE, 1.0, true))
	viewport.add_child(canvas)
	add_child(viewport)
	_marker_cache[cache_key] = viewport
	return viewport.get_texture()


## An icon shape (GAUGE_ICON_SIZE units) placed at `center` in HUD pixels.
func _icon_points(shape: Array[Vector2], center: Vector2) -> PackedVector2Array:
	var points := PackedVector2Array()
	for p in shape:
		points.append(center + p * GAUGE_ICON_SIZE)
	return points


## A shape with a hole, as two hole-free halves that can be filled (polygons
## can't have holes): the right half runs down the outline's right side and
## back up the hole's, the left half likewise. Both loops start at their top and
## run down the right side first, reaching the bottom at the given index.
static func _split_ring(outer: Array[Vector2], hole: Array[Vector2], outer_bottom: int, hole_bottom: int) -> Array:
	var right: Array[Vector2] = outer.slice(0, outer_bottom + 1)
	var hole_right: Array[Vector2] = hole.slice(0, hole_bottom + 1)
	hole_right.reverse()
	right.append_array(hole_right)
	var left: Array[Vector2] = outer.slice(outer_bottom)
	left.append(outer[0])
	var hole_left: Array[Vector2] = hole.slice(hole_bottom)
	hole_left.append(hole[0])
	hole_left.reverse()
	left.append_array(hole_left)
	return [right, left]


func _draw_bar(pos: Vector2, fraction: float, color: Color) -> void:
	draw_rect(Rect2(pos, Vector2(BAR_WIDTH, BAR_HEIGHT)), Color(1, 1, 1, 0.12))
	draw_rect(Rect2(pos, Vector2(BAR_WIDTH * clampf(fraction, 0.0, 1.0), BAR_HEIGHT)), color)


## Past the play boundary: a blinking warning, then a notice while the ship
## turns itself back (Ship.turning_back).
func _draw_boundary_warning() -> void:
	var text := ""
	if _ship.turning_back:
		text = "TURNING BACK"
	elif _boundary.distance_outside(_ship.global_position) > 0.0:
		text = "RETURN TO THE COMBAT AREA"
	if text != "" and fmod(Time.get_ticks_msec() / 1000.0, 0.8) < 0.5:
		draw_string(_font, Vector2(0.0, 160.0), text, HORIZONTAL_ALIGNMENT_CENTER, size.x, 24, COLOR_ORDER)
