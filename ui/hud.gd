extends Control
## Draws the targeting reticles, steering cursor and gauges.
##
## The main crosshair sits where the lasers actually aim (Ship.aim_point),
## and turns red when something shootable is under it. Its screen position is
## smoothed so it doesn't jump aggressively when depths change.

const COLOR_IDLE := Color(0.45, 1.0, 0.55, 0.9)
const COLOR_TARGET := Color(1.0, 0.3, 0.25, 1.0)
const COLOR_BOOST := Color(0.4, 0.8, 1.0, 0.9)
const COLOR_ORDER := Color(1.0, 0.7, 0.15, 1.0)
const COLOR_WING := Color(0.95, 0.75, 0.3, 0.7)
const COLOR_ENEMY := Color(1.0, 0.25, 0.2, 0.85)
const COLOR_SHIELD := Color(0.35, 0.95, 0.45, 0.95)
const COLOR_SHIELD_DOWN := Color(1.0, 0.3, 0.2, 0.95)
## Within this many degrees above or below you, an enemy shows as level.
const RADAR_LEVEL_DEG := 15.0
## ...or within this many metres, for enemies close by.
const RADAR_LEVEL_METRES := 10.0
## Wingmen closer than this to the centre (pixels) are pushed out to it.
const RADAR_WINGMAN_MIN := 9.0
## Radius of the dots on the radar rim for enemies beyond radar_range.
const RADAR_FAR_DOT := 3.0
const BAR_WIDTH := 220.0
const BAR_HEIGHT := 8.0
## Half-size of the order icons on the wing panel cards, in pixels.
const ORDER_ICON_SIZE := 8.0
## Width and height of the triangle over each wingman, in pixels.
const WINGMAN_MARKER_SIZE := Vector2(36.0, 29.0)
## Size of the initial inside it (21 when selected). Independent of the
## triangle size.
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
## initial, colour and selection. Cleared when the window is resized.
var _marker_cache := {}

var _crosshair_pos := Vector2.ZERO
## Enemy fighters the camera can't see right now (something solid in between),
## updated each physics tick by _update_hidden_enemies().
var _hidden_enemies := {}


func _ready() -> void:
	add_to_group("hud")
	# The project font (Project Settings > GUI > Theme > Custom Font), like every menu.
	_font = get_theme_default_font()
	_bold_font = FontVariation.new()
	_bold_font.base_font = _font
	_bold_font.variation_embolden = 0.9
	get_viewport().size_changed.connect(_clear_marker_cache)



func add_score(points: int) -> void:
	score += points


func _process(_delta: float) -> void:
	if not is_instance_valid(_destroyer):
		_destroyer = get_tree().get_first_node_in_group("destroyer") as Destroyer
	if not is_instance_valid(_boundary):
		_boundary = get_tree().get_first_node_in_group("boundary") as PlayBoundary
	if not is_instance_valid(_ship):
		_ship = get_tree().get_first_node_in_group("player") as Ship
	if not is_instance_valid(_wing):
		_wing = get_tree().get_first_node_in_group("wing_command") as WingCommand
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
## which must die to kill it, are brightest), edge arrow. A wingman also calls
## it out over the comms (WingCommand.announce_destroyer).
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
	if not destroyer.is_vulnerable():
		return  # still fading in (or dying): nothing to shoot yet
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
## (clouds don't count). Off-screen enemies get no arrow: finding them is the
## radar's job.
func _draw_enemies(cam: Camera3D) -> void:
	var visible_rect := Rect2(Vector2.ZERO, size).grow(-24.0)
	for enemy: EnemyFighter in get_tree().get_nodes_in_group("enemies"):
		var pos := enemy.global_position
		if cam.is_position_behind(pos):
			continue
		var p := cam.unproject_position(pos)
		if not visible_rect.has_point(p):
			continue
		if not _hidden_enemies.has(enemy) and p.distance_to(_crosshair_pos) <= enemy_marker_radius:
			_draw_brackets(p, 10.0, COLOR_ENEMY)


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
## initial in white, so you can find them when they split off. Selected
## wingmen get a bigger triangle and a bracket. The triangle and letter are
## drawn once into a texture per wingman and state (_wingman_marker()); each
## frame only places that texture.
func _draw_wingmen(cam: Camera3D) -> void:
	for wingman: Wingman in get_tree().get_nodes_in_group("wingmen"):
		var pos := wingman.global_position + cam.global_basis.y * 4.0
		if cam.is_position_behind(pos):
			continue
		var p := cam.unproject_position(pos)
		var selected := _wing != null and _wing.is_selected(wingman)
		var marker_size := _wingman_marker_size(selected)
		# Tip at the point above the ship, flat side on top.
		draw_texture_rect(_wingman_marker(wingman, selected),
			Rect2(p - Vector2(marker_size.x * 0.5, marker_size.y), marker_size), false)
		if selected:
			var half_height := marker_size.y * 0.5
			_draw_brackets(p + Vector2(0.0, -half_height), half_height + 8.0, Color(wingman.accent_color, 1.0))


## Width and height of a wingman's triangle, in HUD pixels.
func _wingman_marker_size(selected: bool) -> Vector2:
	return WINGMAN_MARKER_SIZE * (1.4 if selected else 1.0)


## The texture of a wingman's marker, drawn the first time it's needed: a
## one-shot SubViewport renders the triangle and initial at the screen's real
## resolution (so it stays sharp when the HUD is stretched), then keeps the
## result.
func _wingman_marker(wingman: Wingman, selected: bool) -> Texture2D:
	var initial := wingman.call_sign.left(1)
	var color := wingman.accent_color
	var key := "%s|%s|%s" % [initial, color.to_html(), selected]
	if _marker_cache.has(key):
		return (_marker_cache[key] as SubViewport).get_texture()

	# Screen pixels per HUD pixel.
	var bake_scale := maxf(get_viewport().get_final_transform().get_scale().y, 1.0)
	var marker_size := _wingman_marker_size(selected)
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
		]), Color(color, 1.0 if selected else 0.85))
		var font_size := WINGMAN_INITIAL_SIZE if not selected else roundi(WINGMAN_INITIAL_SIZE * 1.4)
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
			# Out of range: a small dim dot on the rim in its direction, so
			# you can still find a far-off wave.
			if flat.length() > 0.01:
				draw_circle(center + flat.normalized() * r, RADAR_FAR_DOT, Color(COLOR_ENEMY, 0.6))
			continue
		var p := center + flat / radar_range * r
		match _radar_height(local):
			1:
				draw_colored_polygon(PackedVector2Array([p + Vector2(0, -5), p + Vector2(4.5, 3.5), p + Vector2(-4.5, 3.5)]), COLOR_ENEMY)
			-1:
				draw_colored_polygon(PackedVector2Array([p + Vector2(0, 5), p + Vector2(4.5, -3.5), p + Vector2(-4.5, -3.5)]), COLOR_ENEMY)
			_:
				draw_rect(Rect2(p - Vector2(3.5, 3.5), Vector2(7.0, 7.0)), COLOR_ENEMY)


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


## Shield and boost bars, top right (the comms box has the bottom left), then
## the wing panel. Bars only, no numbers. While the shields are down, the
## shield bar turns red and fills up as they reboot.
func _draw_gauges() -> void:
	var origin := Vector2(size.x - 28.0 - BAR_WIDTH, 32.0)
	if _ship.shields_down:
		_draw_bar(origin, _ship.shield_reboot_progress(), Color(COLOR_SHIELD_DOWN, 0.6))
	else:
		_draw_bar(origin, _ship.shields / _ship.max_shields, COLOR_SHIELD)
	_draw_bar(origin + Vector2(0.0, BAR_HEIGHT + 8.0), _ship.boost_energy, COLOR_BOOST)
	if _wing:
		_draw_wing_panel()


## Wing panel, bottom right, laid out like the D-pad that selects the wingmen:
## Falco on the left, Slippy on top, Krystal on the right, ALL below. Each card
## shows the call sign with the current order under it; selected cards light
## up. The middle shows who the next order will go to. (What a wingman is doing
## right now isn't shown: you can see it.)
func _draw_wing_panel() -> void:
	const W := 104.0
	const H := 38.0
	const GAP := 6.0
	const ALL_H := 24.0
	var right := size.x - 24.0
	var bottom := size.y - 24.0
	var left := right - 3.0 * W - 2.0 * GAP
	var top := bottom - ALL_H - 2.0 * H - 2.0 * GAP
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
		_draw_wing_card(rect, wingman, _wing.is_selected(wingman), key)

	# ALL, under the middle (D-pad down).
	var all_rect := Rect2(left + W + GAP, top + 2.0 * (H + GAP), W, ALL_H)
	var everyone := _wing.wingmen()
	var all_selected := not everyone.is_empty() and _wing.selected.size() == everyone.size()
	_draw_card_frame(all_rect, COLOR_IDLE, all_selected)
	draw_string(_font, all_rect.position + Vector2(0.0, 17.0), "ALL", HORIZONTAL_ALIGNMENT_CENTER, W, 13,
		Color(1, 1, 1, 0.95) if all_selected else Color(COLOR_IDLE, 0.8))
	if not pad:
		draw_string(_font, all_rect.position + Vector2(6.0, 16.0), _short_key(&"select_all"),
			HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(1, 1, 1, 0.4))

	# Middle: who gets the next order.
	var middle := Rect2(left + W + GAP, top + H + GAP, W, H)
	var to := _wing.recipients()
	var to_text := " ".join(PackedStringArray(to.map(func(w: Wingman) -> String: return w.call_sign.left(1))))
	draw_string(_font, middle.position + Vector2(0.0, 15.0), "ORDERS TO", HORIZONTAL_ALIGNMENT_CENTER, W, 10,
		Color(1, 1, 1, 0.45))
	draw_string(_font, middle.position + Vector2(0.0, 31.0), to_text if to_text != "" else "NOBODY",
		HORIZONTAL_ALIGNMENT_CENTER, W, 14, COLOR_IDLE if to_text != "" else COLOR_TARGET)


func _draw_wing_card(rect: Rect2, wingman: Wingman, selected: bool, key: String) -> void:
	_draw_card_frame(rect, wingman.accent_color, selected)
	var order_color := COLOR_IDLE
	match wingman.order:
		Wingman.Order.ATTACK:
			order_color = COLOR_ORDER
		Wingman.Order.COVER_ME:
			order_color = COLOR_BOOST
		Wingman.Order.WEAPONS_FREE:
			order_color = COLOR_TARGET
	# One row: [key] NAME ......... order icon.
	var x := rect.position.x + 8.0
	var baseline := rect.position.y + rect.size.y * 0.5 + 5.0
	if key != "":
		draw_string(_font, Vector2(x, baseline), key, HORIZONTAL_ALIGNMENT_LEFT, -1, 10,
			Color(1, 1, 1, 0.4))
	var name_x := x + (12.0 if key != "" else 0.0)
	draw_string(_font, Vector2(name_x, baseline), wingman.call_sign.to_upper(),
		HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color(wingman.accent_color, 1.0))
	var icon_center := Vector2(rect.end.x - 8.0 - ORDER_ICON_SIZE, rect.get_center().y)
	_draw_order_icon(wingman.order, icon_center, ORDER_ICON_SIZE, order_color)


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


func _draw_card_frame(rect: Rect2, color: Color, selected: bool) -> void:
	draw_rect(rect, Color(color, 0.22) if selected else Color(0.0, 0.02, 0.04, 0.45))
	draw_rect(rect, Color(color, 1.0) if selected else Color(color, 0.3), false, 2.0 if selected else 1.0)


## Keyboard key for an action's primary binding, shortened for a card corner.
func _short_key(action: StringName) -> String:
	var event := Settings.get_binding(action, Settings.Slot.PRIMARY)
	return Settings.event_name(event).left(3) if event else ""


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
