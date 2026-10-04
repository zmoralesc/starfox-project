class_name WingCommand
extends Node
## Turns the player's input into orders for the wingmen.
##
## Selection: each wingman can be selected individually (D-pad left / up /
## right, or 1 / 2 / 3), and D-pad down / 4 selects or deselects all of them.
## Orders go to the selected wingmen. With nobody selected, an order goes to
## every wingman except those whose standing order is Cover Me. The selection
## clears once an order goes out.
##
## Orders are always assigned, never toggled:
## - Attack: the target under (or nearest to) the crosshair.
## - Cover Me: a standing order. Covering wingmen go after enemies attacking
##   the player (one threat each where possible) and wait in formation between
##   threats.
## - Form Up: back into formation (also a standing order).
## - Weapons Free: roam near the player and engage enemy fighters freely
##   (also a standing order).
## When an Attack target is gone, each wingman returns to its standing order.

signal selection_changed
## A short message about the order that just went out.
## Nothing shows it at the moment (the HUD toast was removed); kept for tests
## and future use.
signal order_feedback(message: String)

@export var leader: Ship
## How far off the crosshair (degrees, beyond the target's own size) a target
## can be and still get picked.
@export var assist_angle_deg := 4.0

## Currently selected wingmen (in wing order).
var selected: Array[Wingman] = []

const SELECT_ACTIONS := {&"select_wingman_1": 0, &"select_wingman_2": 1, &"select_wingman_3": 2}


## Call sign of whoever called out the last destroyer. Static, so it carries
## over level restarts in the same session.
static var _last_destroyer_caller := ""

## Wingman -> the acknowledgement it used last.
var _last_ack := {}
## The last line said to praise one of the player's kills.
var _last_praise := ""


func _ready() -> void:
	add_to_group("wing_command")


func _unhandled_input(event: InputEvent) -> void:
	if leader and not leader.controls_enabled:
		return  # no orders during cutscenes
	for action: StringName in SELECT_ACTIONS:
		if event.is_action_pressed(action):
			var wingman := wingman_at(SELECT_ACTIONS[action])
			if wingman:
				toggle_select(wingman)
			return
	if event.is_action_pressed("select_all"):
		toggle_select_all()
	elif event.is_action_pressed("command_attack"):
		order_attack(pick_target())
	elif event.is_action_pressed("command_cover"):
		order_cover_me()
	elif event.is_action_pressed("command_cancel"):
		order_form_up()
	elif event.is_action_pressed("command_free"):
		order_weapons_free()


func _physics_process(_delta: float) -> void:
	_update_cover()


#region Selection

func wingmen() -> Array[Wingman]:
	var result: Array[Wingman] = []
	for wingman: Wingman in get_tree().get_nodes_in_group("wingmen"):
		result.append(wingman)
	result.sort_custom(func(a: Wingman, b: Wingman) -> bool: return a.wing_index < b.wing_index)
	return result


func wingman_at(index: int) -> Wingman:
	for wingman in wingmen():
		if wingman.wing_index == index:
			return wingman
	return null


func is_selected(wingman: Wingman) -> bool:
	return wingman in selected


func toggle_select(wingman: Wingman) -> void:
	if wingman in selected:
		selected.erase(wingman)
	else:
		selected.append(wingman)
		selected.sort_custom(func(a: Wingman, b: Wingman) -> bool: return a.wing_index < b.wing_index)
	selection_changed.emit()


## Selects everyone, or deselects everyone if they're all selected already.
func toggle_select_all() -> void:
	var everyone := wingmen()
	if selected.size() == everyone.size():
		selected.clear()
	else:
		selected = everyone
	selection_changed.emit()


func clear_selection() -> void:
	if selected.is_empty():
		return
	selected.clear()
	selection_changed.emit()


## Who an order goes to right now: the selection, or with nobody selected,
## everyone not standing on Cover Me.
func recipients() -> Array[Wingman]:
	if not selected.is_empty():
		return selected.duplicate()
	var result: Array[Wingman] = []
	result.assign(wingmen().filter(func(w: Wingman) -> bool: return w.standing_order != Wingman.Order.COVER_ME))
	return result

#endregion


#region Orders

func order_attack(new_target: Node3D) -> void:
	if not is_instance_valid(new_target) or not Fighter.is_attack_target(new_target):
		return
	_issue(func(w: Wingman) -> void: w.assign_attack(new_target),
		func(w: Wingman) -> bool: return w.order != Wingman.Order.ATTACK or w.target != new_target,
		"attacking %s" % Wingman.target_label(new_target).to_lower())


func order_cover_me() -> void:
	_issue(func(w: Wingman) -> void: w.assign_cover_me(),
		func(w: Wingman) -> bool: return w.order != Wingman.Order.COVER_ME,
		"covering you")


func order_form_up() -> void:
	_issue(func(w: Wingman) -> void: w.assign_form_up(),
		func(w: Wingman) -> bool: return w.order != Wingman.Order.FORM_UP,
		"forming up")


func order_weapons_free() -> void:
	_issue(func(w: Wingman) -> void: w.assign_weapons_free(),
		func(w: Wingman) -> bool: return w.order != Wingman.Order.WEAPONS_FREE,
		"weapons free")


func _issue(assign: Callable, needs_change: Callable, what: String) -> void:
	var all_recipients := recipients()
	if all_recipients.is_empty():
		return
		
	var to: Array[Wingman] = []
	for w in all_recipients:
		if needs_change.call(w):
			to.append(w)
			
	if to.is_empty():
		clear_selection()
		return
		
	for wingman in to:
		assign.call(wingman)
		
	var names := PackedStringArray(to.map(func(w: Wingman) -> String: return w.call_sign))
	order_feedback.emit("%s: %s" % [", ".join(names), what])
	clear_selection()
	_acknowledge(to.pick_random())


## One wingman confirms an order over the comms (never the same words twice in
## a row). Low priority: dropped if someone's already talking.
func _acknowledge(wingman: Wingman) -> void:
	var comms := Comms.find(get_tree())
	var pilot := wingman.pilot
	if comms == null or pilot == null or pilot.acknowledgements.is_empty():
		return
	var options := Array(pilot.acknowledgements)
	if options.size() > 1:
		options.erase(_last_ack.get(wingman, ""))
	var line: String = options.pick_random()
	if comms.say(pilot, line):
		_last_ack[wingman] = line


## A destroyer has arrived: a random wingman calls it out, with the hint on
## how to kill it (never the same wingman as last time). High priority, so it
## cuts off chatter.
func announce_destroyer() -> void:
	var comms := Comms.find(get_tree())
	var speakers := wingmen().filter(func(w: Wingman) -> bool:
		return w.pilot != null and w.pilot.destroyer_callout != "")
	if comms == null or speakers.is_empty():
		return
	if speakers.size() > 1:
		speakers = speakers.filter(func(w: Wingman) -> bool: return w.call_sign != _last_destroyer_caller)
	var wingman: Wingman = speakers.pick_random()
	_last_destroyer_caller = wingman.call_sign
	comms.say(wingman.pilot, wingman.pilot.destroyer_callout, Comms.Priority.HIGH)


## The player shot down an enemy fighter: a random wingman may compliment it,
## with that pilot's celebration_chance (the same odds as celebrating their
## own kills). Never the same words twice in a row. Low priority: dropped if
## someone's already talking.
func praise_player_kill() -> void:
	var comms := Comms.find(get_tree())
	var speakers := wingmen().filter(func(w: Wingman) -> bool:
		return w.pilot != null and not w.pilot.praise.is_empty())
	if comms == null or speakers.is_empty():
		return
	var pilot: Pilot = (speakers.pick_random() as Wingman).pilot
	if randf() > pilot.celebration_chance:
		return
	var options := Array(pilot.praise)
	if options.size() > 1:
		options.erase(_last_praise)
	var line: String = options.pick_random()
	if comms.say(pilot, line):
		_last_praise = line

#endregion


## Enemies currently attacking the player, nearest to the player first.
func threats() -> Array[EnemyFighter]:
	var result: Array[EnemyFighter] = []
	for enemy: EnemyFighter in get_tree().get_nodes_in_group("enemies"):
		if enemy.state == EnemyFighter.State.CHASE:
			result.append(enemy)
	if leader:
		var origin := leader.global_position
		result.sort_custom(func(a: EnemyFighter, b: EnemyFighter) -> bool:
			return a.global_position.distance_squared_to(origin) < b.global_position.distance_squared_to(origin))
	return result


## The shootable thing under the crosshair, or failing that the one closest to
## it. Only things whose `attack_target` allows it (Fighter.is_attack_target;
## not asteroids): looking through a rock still finds the enemy nearest the
## crosshair.
func pick_target() -> Node3D:
	if leader == null:
		return null
	if is_instance_valid(leader.aim_target) and Fighter.is_attack_target(leader.aim_target):
		return leader.aim_target

	var forward := -leader.global_basis.z
	var best: Node3D
	var best_score := INF
	for node in get_tree().get_nodes_in_group("targets"):
		var candidate := node as Node3D
		if not Fighter.is_attack_target(candidate):
			continue
		var to_candidate := candidate.global_position - leader.global_position
		var dist := to_candidate.length()
		if dist > leader.aim_range or dist < 0.01:
			continue
		var angle := forward.angle_to(to_candidate)
		var allowance := atan2(Fighter.radius_of(candidate), dist) + deg_to_rad(assist_angle_deg)
		# Fighters are small and moving, so give them twice the slack and
		# prefer them over rocks near the crosshair.
		var is_enemy := candidate.is_in_group("enemies")
		if is_enemy:
			allowance += deg_to_rad(assist_angle_deg)
		var score := angle * (0.5 if is_enemy else 1.0)
		if angle < allowance and score < best_score:
			best = candidate
			best_score = score
	return best


## Give each covering wingman a threat to deal with, or send it back to
## formation to wait.
func _update_cover() -> void:
	var covering := wingmen().filter(func(w: Wingman) -> bool: return w.order == Wingman.Order.COVER_ME)
	if covering.is_empty():
		return
	var current_threats := threats()
	var taken: Array[Node3D] = []
	var unassigned: Array[Wingman] = []

	# Pass 1: keep existing engagements, one wingman per enemy. Once on a
	# threat, a wingman stays on it until it's destroyed or gives up on the
	# player (back to patrol); evading or searching doesn't count.
	for wingman: Wingman in covering:
		var current := _cover_target(wingman)
		if current and current not in taken:
			taken.append(current)
		else:
			unassigned.append(wingman)

	# Pass 2: everyone else takes a threat nobody is on yet. If there's none,
	# a wingman already sharing a target keeps it, and an idle one doubles
	# up on the nearest threat.
	for wingman in unassigned:
		var current := _cover_target(wingman)
		var pick: Node3D = null
		for enemy in current_threats:
			if enemy not in taken:
				pick = enemy
				break
		if pick == null:
			if current:
				continue
			if not current_threats.is_empty():
				pick = current_threats[0]
		if pick:
			if pick != current:
				wingman.command_attack(pick, false)
			taken.append(pick)
		elif wingman.state == Wingman.State.ATTACK:
			wingman.command_follow()


## The enemy this wingman is covering against, if it's still a threat.
func _cover_target(wingman: Wingman) -> Node3D:
	if wingman.state != Wingman.State.ATTACK or not is_instance_valid(wingman.target):
		return null
	var enemy := wingman.target as EnemyFighter
	if enemy and enemy.state != EnemyFighter.State.PATROL:
		return enemy
	return null
