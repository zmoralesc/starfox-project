class_name MissionControl
extends Node
## The team's support aboard the Great Fox: an Advisor (Peppy) who warns of
## destroyers, tells the team how to take them down, and calls out progress as
## their key parts fall. All lines are HIGH priority (tactical information):
## they cut off chatter and queue behind each other, so a warning is always
## followed by its hint.
##
## Lives in levels/level_base.tscn (group `mission_control`); the
## EnemySpawner calls announce_destroyer() when one arrives.

## Who's talking, and what they say (comms/speakers/peppy.tres).
@export var advisor: Advisor

## Destroyers announced so far this mission: the first gets the full hint.
var _destroyers_seen := 0
## List -> the line last said from it, so it isn't repeated next time.
var _last_lines := {}


func _enter_tree() -> void:
	add_to_group("mission_control")


## A destroyer has arrived: warn the team and say how to sink it, then follow
## its parts to call out progress.
func announce_destroyer(destroyer: Destroyer) -> void:
	if advisor == null or not is_instance_valid(destroyer):
		return
	_say(advisor.destroyer_warnings)
	_say(advisor.destroyer_hints if _destroyers_seen == 0 else advisor.destroyer_reminders)
	_destroyers_seen += 1
	if destroyer.bridge:
		destroyer.bridge.destroyed.connect(_on_bridge_down.bind(destroyer))
	for thruster in destroyer.thrusters:
		thruster.destroyed.connect(_on_thruster_down.bind(destroyer))
	destroyer.destroyed.connect(_say.bind(advisor.destroyer_killed))


## The bridge fell: if thrusters remain, point the team at them. (If none do,
## the destroyer is dying and destroyer_killed covers it.)
func _on_bridge_down(destroyer: Destroyer) -> void:
	if is_instance_valid(destroyer) and destroyer.intact_count(destroyer.thrusters) > 0:
		_say(advisor.bridge_down)


## A thruster fell: call out the last one standing, or the bridge once they're
## all gone.
func _on_thruster_down(destroyer: Destroyer) -> void:
	if not is_instance_valid(destroyer) or destroyer.bridge == null:
		return
	var left := destroyer.intact_count(destroyer.thrusters)
	if left == 1:
		_say(advisor.last_thruster)
	elif left == 0 and not destroyer.bridge.is_destroyed:
		_say(advisor.thrusters_down)


## Says one specific line as the advisor (HIGH priority, like every line here:
## it waits for a HIGH line already on screen). Used for scripted mission
## lines, such as Level.intro_advisor_line.
func say(text: String) -> void:
	var comms := Comms.find(get_tree())
	if comms and advisor and text != "":
		comms.say(advisor, text, Comms.Priority.HIGH)


## Says a random line from `lines` (not the same as last time from that list).
func _say(lines: PackedStringArray) -> void:
	var comms := Comms.find(get_tree())
	if comms == null or advisor == null or lines.is_empty():
		return
	var options := Array(lines)
	if options.size() > 1:
		options.erase(_last_lines.get(lines, ""))
	var line: String = options.pick_random()
	_last_lines[lines] = line
	comms.say(advisor, line, Comms.Priority.HIGH)
