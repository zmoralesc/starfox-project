extends CanvasLayer
## Autoload "DevConsole": the developer console, for testing and tuning.
##
## The key left of 1 (` on a US keyboard; matched by position, so any layout
## works) opens and closes it; Esc also closes it. While it's open the game is
## paused (and stays paused on closing if it was before, e.g. under the pause
## menu). Only in debug builds (the editor, debug exports): in a release export
## it removes itself.
##
## Cheats and tuning overrides last for the session, across restarts and
## mission changes: they're applied to every new Ship, Wingman and EnemyFighter
## as it enters the tree (before its _ready()), and to the ones already there
## when the command runs. `reset` puts everything back.
##
## Commands are registered in _register_commands(); other scripts can add their
## own with register(). Scripts (and headless tests) can run one with execute().

## The physical key that opens and closes the console.
const TOGGLE_KEY := KEY_QUOTELEFT

## The player's speeds that `speed` scales.
const SPEED_PROPERTIES: Array[StringName] = [&"cruise_speed", &"min_speed", &"max_speed", &"boost_speed"]

## Fighter types `spawn` knows besides the level's own ("fighter").
const FIGHTER_SCENES := {
	"light": preload("res://enemies/light_fighter.tscn"),
	"elite": preload("res://enemies/enemy_fighter.tscn"),
	"trooper": preload("res://enemies/trooper.tscn"),
}

const MISSIONS_DIR := "res://missions"
const SPEAKERS_DIR := "res://comms/speakers"

## Canvas layer: above the HUD, menus and the SceneFader (100).
@export var console_layer := 110
## Height of the console, as a fraction of the screen.
@export_range(0.1, 1.0) var height_fraction := 0.45
## Font size of the log and the command line.
@export var font_size := 13
## Lines kept in the log; older ones are dropped.
@export var max_log_lines := 400
## Commands kept in the Up / Down history.
@export var history_size := 50

@export_group("Colours")
@export var background_color := Color(0.02, 0.04, 0.08, 0.9)
@export var border_color := Color(0.3, 0.7, 1.0)
@export var echo_color := Color(0.55, 0.65, 0.75)
@export var text_color := Color(0.88, 0.92, 0.96)
@export var good_color := Color(0.5, 1.0, 0.6)
@export var error_color := Color(1.0, 0.45, 0.4)

## True while the console is open.
var is_open := false

## Cheats (see the commands of the same names).
var god := false
var notarget := false
var wingmen_god := false

## Tuning overrides in force: "speed" and "firerate" (multipliers),
## "damage", "enemy_health" and "enemy_damage" (ints). Absent = the scenes' own.
var _overrides := {}
## Command name -> {usage, help, run: Callable(args: PackedStringArray),
## options: Callable() -> PackedStringArray for Tab on the first argument}.
var _commands := {}
var _history := PackedStringArray()
## Position in _history while browsing it with Up / Down (-1 = not browsing).
var _history_index := -1
var _log_lines := 0
var _was_paused := false
var _was_mouse_mode := Input.MOUSE_MODE_VISIBLE
var _was_focused: Control
## Strips markup from log lines copied to stdout.
var _bbcode_tag := RegEx.create_from_string("\\[(?!lb\\])/?[a-z_]+[^\\]]*\\]")

var _panel: PanelContainer
var _log: RichTextLabel
var _line: LineEdit


func _ready() -> void:
	if not OS.is_debug_build():
		queue_free()
		return
	layer = console_layer
	process_mode = Node.PROCESS_MODE_ALWAYS
	_build_ui()
	_register_commands()
	get_tree().node_added.connect(_on_node_added)
	_print("Developer console. [b]help[/b] lists the commands; Tab completes, Up / Down recall.",
		echo_color, false, true)


func _input(event: InputEvent) -> void:
	var key := event as InputEventKey
	if key and key.pressed and not key.echo and key.physical_keycode == TOGGLE_KEY:
		toggle()
		get_viewport().set_input_as_handled()
		return
	if not is_open:
		return
	if event.is_action_pressed(&"ui_cancel"):
		close()
		get_viewport().set_input_as_handled()
	# The command line takes the typing; keep the rest (the pause menu's
	# Esc / Start, gamepad buttons) from reaching the game underneath.
	elif event is InputEventJoypadButton or event is InputEventJoypadMotion \
			or (key and key.unicode == 0 and event.is_action(&"pause")):
		get_viewport().set_input_as_handled()


func toggle() -> void:
	if is_open:
		close()
	else:
		open()


## Opens the console and pauses the game.
func open() -> void:
	if is_open:
		return
	is_open = true
	_was_paused = get_tree().paused
	_was_mouse_mode = Input.mouse_mode
	_was_focused = get_viewport().gui_get_focus_owner()
	get_tree().paused = true
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	_panel.show()
	_line.clear()
	_line.grab_focus()


## Closes the console, restoring the pause state and mouse mode it found.
func close() -> void:
	if not is_open:
		return
	is_open = false
	_line.release_focus()
	_panel.hide()
	get_tree().paused = _was_paused
	Input.mouse_mode = _was_mouse_mode
	if is_instance_valid(_was_focused) and _was_focused.is_visible_in_tree():
		_was_focused.grab_focus()


## Adds a command. `run` takes the arguments (PackedStringArray); `options`,
## if valid, returns what Tab offers for the first argument.
func register(command: String, usage: String, help: String, run: Callable,
		options: Callable = Callable()) -> void:
	_commands[command] = {"usage": usage, "help": help, "run": run, "options": options}


## Runs one command line, as if typed (echoed to the log).
func execute(text: String) -> void:
	text = text.strip_edges()
	if text == "":
		return
	_print("> " + text, echo_color, false)
	var words := text.split(" ", false)
	var command := words[0].to_lower()
	if not _commands.has(command):
		_error("Unknown command '%s'. Type help for the list." % command)
		return
	_commands[command].run.call(words.slice(1))


# --- UI ----------------------------------------------------------------------

func _build_ui() -> void:
	_panel = PanelContainer.new()
	_panel.anchor_right = 1.0
	_panel.anchor_bottom = height_fraction
	var style := StyleBoxFlat.new()
	style.bg_color = background_color
	style.border_color = border_color
	style.border_width_bottom = 2
	style.set_content_margin_all(10.0)
	_panel.add_theme_stylebox_override(&"panel", style)
	add_child(_panel)

	var column := VBoxContainer.new()
	_panel.add_child(column)

	_log = RichTextLabel.new()
	_log.bbcode_enabled = true
	_log.scroll_following = true
	_log.selection_enabled = true
	_log.focus_mode = Control.FOCUS_NONE
	_log.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_log.add_theme_font_size_override(&"normal_font_size", font_size)
	_log.add_theme_font_size_override(&"bold_font_size", font_size)
	_log.add_theme_color_override(&"default_color", text_color)
	column.add_child(_log)

	_line = LineEdit.new()
	_line.placeholder_text = "command (help lists them)"
	_line.add_theme_font_size_override(&"font_size", font_size)
	_line.keep_editing_on_text_submit = true
	_line.text_submitted.connect(_on_submitted)
	_line.gui_input.connect(_on_line_input)
	column.add_child(_line)
	_panel.hide()


func _on_submitted(text: String) -> void:
	_line.clear()
	text = text.strip_edges()
	if text == "":
		return
	if _history.is_empty() or _history[-1] != text:
		_history.append(text)
		if _history.size() > history_size:
			_history.remove_at(0)
	_history_index = -1
	execute(text)


## Up / Down browse the history, Tab completes. Accepted here, before the
## LineEdit (or focus navigation) acts on them.
func _on_line_input(event: InputEvent) -> void:
	var key := event as InputEventKey
	if key == null or not key.pressed:
		return
	match key.keycode:
		KEY_UP:
			_recall(-1)
		KEY_DOWN:
			_recall(1)
		KEY_TAB:
			_complete()
		_:
			return
	_line.accept_event()


func _recall(step: int) -> void:
	if _history.is_empty():
		return
	if _history_index == -1:
		_history_index = _history.size() if step < 0 else -1
		if step > 0:
			return
	_history_index += step
	if _history_index >= _history.size():
		_history_index = -1
		_line.text = ""
	else:
		_history_index = maxi(_history_index, 0)
		_line.text = _history[_history_index]
	_line.caret_column = _line.text.length()


## Completes the command name, or its first argument from the command's options.
## Several matches: completes their common start and lists them.
func _complete() -> void:
	var text := _line.text
	var words := text.split(" ")
	var candidates := PackedStringArray()
	if words.size() == 1:
		candidates = PackedStringArray(_commands.keys())
	elif words.size() == 2 and _commands.has(words[0].to_lower()):
		var options: Callable = _commands[words[0].to_lower()].options
		if options.is_valid():
			candidates = options.call()
	else:
		return
	var prefix := words[-1].to_lower()
	var matches := PackedStringArray()
	for candidate in candidates:
		if candidate.to_lower().begins_with(prefix):
			matches.append(candidate)
	if matches.is_empty():
		return
	matches.sort()
	var common := matches[0]
	for m in matches:
		while not m.to_lower().begins_with(common.to_lower()):
			common = common.left(-1)
	words[-1] = common + (" " if matches.size() == 1 else "")
	_line.text = " ".join(words)
	_line.caret_column = _line.text.length()
	if matches.size() > 1:
		_print("  ".join(matches), echo_color)


## Adds a line to the log (and stdout). `bbcode` = the text has markup;
## otherwise it's shown as is (usages have [optional] arguments).
func _print(text: String, color := text_color, to_stdout := true, bbcode := false) -> void:
	_log.push_color(color)
	if bbcode:
		_log.append_text(text)
	else:
		_log.add_text(text)
	_log.pop()
	_log.newline()
	_log_lines += 1
	if _log_lines > max_log_lines:
		_log.remove_paragraph(0)
		_log_lines -= 1
	if to_stdout:
		print("[console] ", _bbcode_tag.sub(text, "", true).replace("[lb]", "[") if bbcode else text)


func _error(text: String) -> void:
	_print(text, error_color)


func _ok(text: String) -> void:
	_print(text, good_color)


# --- Commands ----------------------------------------------------------------

func _register_commands() -> void:
	var on_off := func() -> PackedStringArray: return PackedStringArray(["on", "off"])
	register("help", "help [command]", "Lists the commands, or explains one.", _cmd_help,
		func() -> PackedStringArray: return PackedStringArray(_commands.keys()))
	register("clear", "clear", "Empties the log.", func(_a: PackedStringArray) -> void:
		_log.clear()
		_log_lines = 0)
	register("status", "status", "Shows the cheats and overrides in force.", _cmd_status)
	register("reset", "reset", "Turns every cheat and override off and the time scale back to 1.", _cmd_reset)
	# Cheats.
	register("god", "god [on|off]", "Player invincible: hits and crashes take nothing off the shields.",
		_cmd_cheat.bind("god"), on_off)
	register("notarget", "notarget [on|off]", "Enemies and turrets ignore the player (chasers lose you).",
		_cmd_cheat.bind("notarget"), on_off)
	register("wingmen_god", "wingmen_god [on|off]", "Wingmen take no damage, so they never evade or disengage.",
		_cmd_cheat.bind("wingmen_god"), on_off)
	# Spawning.
	register("spawn", "spawn <fighter|light|elite|trooper|destroyer> [count]",
		"Fighters (the level's type, or light / elite), or Shogun Troopers, as one squad ahead of you, or a destroyer.",
		_cmd_spawn, func() -> PackedStringArray: return PackedStringArray(["fighter", "light", "elite", "trooper", "destroyer"]))
	register("wave", "wave", "Sends the next wave now.", _cmd_wave)
	register("waves", "waves <on|off>", "Holds back the waves, or lets them come again.", _cmd_waves, on_off)
	register("killall", "killall", "Destroys every enemy fighter and the destroyer.", _cmd_killall)
	# Events.
	register("die", "die", "Destroys the player's ship.", _cmd_die)
	register("shields", "shields <amount>", "Sets the player's shields (0 = knocked out).", _cmd_shields)
	register("say", "say <speaker> <text>", "A comms line from a speaker (comms/speakers/).", _cmd_say, _speaker_names)
	register("advisor", "advisor <text>", "A comms line from mission control's advisor.", _cmd_advisor)
	register("restart", "restart", "Restarts the current scene.", _cmd_restart)
	register("mission", "mission [name]", "Lists the missions, or loads one (by file name or title).",
		_cmd_mission, _mission_names)
	# Tuning.
	register("speed", "speed <multiplier|reset>",
		"Scales the player's cruise, min, max and boost speeds (wingmen keep theirs).",
		_cmd_override.bind("speed", TYPE_FLOAT), _reset_option)
	register("firerate", "firerate <multiplier|reset>", "Scales the player's rate of fire.",
		_cmd_override.bind("firerate", TYPE_FLOAT), _reset_option)
	register("damage", "damage <amount|reset>", "Damage of each of the player's bolts (default 1).",
		_cmd_override.bind("damage", TYPE_INT), _reset_option)
	register("enemy_health", "enemy_health <amount|reset>",
		"Enemy fighters' health, now and for new ones (light 3, elite 4). Existing ones heal to it.",
		_cmd_override.bind("enemy_health", TYPE_INT), _reset_option)
	register("enemy_damage", "enemy_damage <amount|reset>",
		"Damage of each enemy fighter bolt (default 4; turrets keep theirs).",
		_cmd_override.bind("enemy_damage", TYPE_INT), _reset_option)
	register("timescale", "timescale <factor>", "Game speed (Engine.time_scale), 0.05 to 10.", _cmd_timescale)
	register("get", "get <who> <property>",
		"Reads a property. who: player, wingmen, enemies, destroyer, spawner, level, a wingman's call sign or a group.",
		_cmd_get, _target_names)
	register("set", "set <who> <property> <value>",
		"Sets a property (until the node is gone; not kept across restarts). Vectors as Vector3(1, 2, 3).",
		_cmd_set, _target_names)


func _cmd_help(args: PackedStringArray) -> void:
	if args.size() > 0:
		var command := args[0].to_lower()
		if not _commands.has(command):
			_error("Unknown command '%s'." % command)
			return
		_print_usage(command)
		return
	for command: String in _commands:
		_print_usage(command)


func _print_usage(command: String) -> void:
	var entry: Dictionary = _commands[command]
	_print("[b]%s[/b]  [color=#%s]%s[/color]" % [entry.usage.replace("[", "[lb]"),
		echo_color.to_html(false), entry.help.replace("[", "[lb]")], text_color, true, true)


func _cmd_status(_args: PackedStringArray) -> void:
	var cheats := PackedStringArray()
	for cheat in ["god", "notarget", "wingmen_god"]:
		if get(cheat):
			cheats.append(cheat)
	_print("Cheats: %s" % (", ".join(cheats) if not cheats.is_empty() else "none"))
	var overrides := PackedStringArray()
	for key: String in _overrides:
		overrides.append("%s %s" % [key, _overrides[key]])
	_print("Overrides: %s" % (", ".join(overrides) if not overrides.is_empty() else "none"))
	_print("Time scale: %s" % Engine.time_scale)
	var spawner := _spawner()
	if spawner:
		_print("Wave %d, %d fighters, waves %s" % [spawner.wave, spawner.fighter_count(),
			"on" if spawner.waves_enabled else "off"])


func _cmd_reset(_args: PackedStringArray) -> void:
	god = false
	notarget = false
	wingmen_god = false
	_overrides.clear()
	Engine.time_scale = 1.0
	_apply_to_all()
	var spawner := _spawner()
	if spawner:
		spawner.set_waves_enabled(true)
	_ok("Everything back to normal.")


func _cmd_cheat(args: PackedStringArray, cheat: String) -> void:
	var on: bool = not get(cheat)
	if args.size() > 0:
		var parsed: Variant = _parse_bool(args[0])
		if parsed == null:
			_error("Expected on or off.")
			return
		on = parsed
	set(cheat, on)
	_apply_to_all()
	_ok("%s %s" % [cheat, "on" if on else "off"])


func _cmd_spawn(args: PackedStringArray) -> void:
	var spawner := _spawner()
	if spawner == null:
		_error("No enemy spawner here (not in a mission).")
		return
	var kind := args[0].to_lower() if args.size() > 0 else "fighter"
	if kind == "destroyer":
		if spawner.spawn_destroyer():
			_ok("Destroyer inbound.")
		else:
			_error("A destroyer is already in play.")
		return
	var scene: PackedScene = spawner.enemy_scene if kind == "fighter" else FIGHTER_SCENES.get(kind)
	if scene == null:
		_error("Unknown type '%s': fighter, light, elite, trooper or destroyer." % kind)
		return
	var count := 1
	if args.size() > 1:
		if not args[1].is_valid_int() or args[1].to_int() < 1:
			_error("Count must be a whole number of at least 1.")
			return
		count = args[1].to_int()
	var spawned: Array[EnemyFighter] = spawner.spawn_squad(spawner.squad_center(), count, scene)
	var noun := "trooper" if kind == "trooper" else ("" if kind == "fighter" else kind + " ") + "fighter"
	_ok("Spawned %d %s%s, %d m ahead." % [spawned.size(), noun, "" if count == 1 else "s",
		roundi(spawner.spawn_distance)])


func _cmd_wave(_args: PackedStringArray) -> void:
	var spawner := _spawner()
	if spawner == null:
		_error("No enemy spawner here (not in a mission).")
		return
	spawner.spawn_wave_now()
	_ok("Wave %d sent." % spawner.wave)


func _cmd_waves(args: PackedStringArray) -> void:
	var spawner := _spawner()
	if spawner == null:
		_error("No enemy spawner here (not in a mission).")
		return
	var on: Variant = _parse_bool(args[0]) if args.size() > 0 else not spawner.waves_enabled
	if on == null:
		_error("Expected on or off.")
		return
	spawner.set_waves_enabled(on)
	_ok("Waves %s." % ("on" if on else "off"))


func _cmd_killall(_args: PackedStringArray) -> void:
	var count := 0
	for node in get_tree().get_nodes_in_group("enemies"):
		var enemy := node as EnemyFighter
		if enemy and enemy.health > 0 and not enemy.is_queued_for_deletion():
			enemy.take_hit(enemy.health, enemy.global_position)
			count += 1
	for node in get_tree().get_nodes_in_group("destroyer"):
		(node as Destroyer).destroy()
		count += 1
	_ok("Destroyed %d enem%s." % [count, "y" if count == 1 else "ies"])


func _cmd_die(_args: PackedStringArray) -> void:
	var ship := _ship()
	if ship == null:
		_error("No player ship here.")
		return
	if god:
		_print("(god is on, but die still destroys the ship)", echo_color)
	ship.destroy()
	_ok("Boom.")


func _cmd_shields(args: PackedStringArray) -> void:
	var ship := _ship()
	if ship == null:
		_error("No player ship here.")
		return
	if args.is_empty() or not args[0].is_valid_float():
		_error("Usage: shields <amount> (max %s)." % ship.max_shields)
		return
	ship.shields = clampf(args[0].to_float(), 0.0, ship.max_shields)
	ship.shields_down = ship.shields < 1.0
	_ok("Shields %s / %s." % [ship.shields, ship.max_shields])


func _cmd_say(args: PackedStringArray) -> void:
	if args.size() < 2:
		_error("Usage: say <speaker> <text>. Speakers: %s" % ", ".join(_speaker_names()))
		return
	var comms := Comms.find(get_tree())
	if comms == null:
		_error("No comms here.")
		return
	var path := "%s/%s.tres" % [SPEAKERS_DIR, args[0].to_lower()]
	if not ResourceLoader.exists(path):
		_error("No speaker '%s'. Speakers: %s" % [args[0], ", ".join(_speaker_names())])
		return
	comms.say(load(path) as CommsSpeaker, " ".join(args.slice(1)), Comms.Priority.HIGH)
	_ok("Queued (shows when the console closes).")


func _cmd_advisor(args: PackedStringArray) -> void:
	var mission_control := get_tree().get_first_node_in_group("mission_control") as MissionControl
	if mission_control == null or args.is_empty():
		_error("No mission control here." if mission_control == null else "Usage: advisor <text>")
		return
	mission_control.say(" ".join(args))
	_ok("Queued (shows when the console closes).")


func _cmd_restart(_args: PackedStringArray) -> void:
	close()
	SceneFader.reload_scene()


func _cmd_mission(args: PackedStringArray) -> void:
	if args.is_empty():
		_print("Missions: %s" % ", ".join(_mission_names()))
		return
	var wanted := " ".join(args).to_lower()
	for file_name in _mission_names():
		var mission := load("%s/%s.tres" % [MISSIONS_DIR, file_name]) as Mission
		if mission and (file_name.to_lower() == wanted or mission.title.to_lower() == wanted):
			close()
			SceneFader.change_scene(mission.scene_path)
			return
	_error("No mission '%s'. Missions: %s" % [wanted, ", ".join(_mission_names())])


## Shared by the tuning commands: a number (or "reset") stored in _overrides.
func _cmd_override(args: PackedStringArray, key: String, type: Variant.Type) -> void:
	if args.is_empty():
		_print("%s: %s" % [key, _overrides.get(key, "default")])
		return
	if args[0].to_lower() == "reset":
		_overrides.erase(key)
		_apply_to_all()
		_ok("%s back to default." % key)
		return
	var valid := args[0].is_valid_int() if type == TYPE_INT else args[0].is_valid_float()
	var value: float = args[0].to_float()
	if not valid or value < 0.0 or (type == TYPE_FLOAT and value == 0.0):
		_error("Expected a %s." % ("whole number of 0 or more" if type == TYPE_INT else "number above 0"))
		return
	if type == TYPE_INT:
		_overrides[key] = args[0].to_int()
	else:
		_overrides[key] = value
	_apply_to_all()
	_ok("%s %s" % [key, _overrides[key]])


func _cmd_timescale(args: PackedStringArray) -> void:
	if args.is_empty() or not args[0].is_valid_float():
		_print("Time scale: %s" % Engine.time_scale)
		return
	Engine.time_scale = clampf(args[0].to_float(), 0.05, 10.0)
	_ok("Time scale %s." % Engine.time_scale)


func _cmd_get(args: PackedStringArray) -> void:
	if args.size() < 2:
		_error("Usage: get <who> <property>")
		return
	var nodes := _targets(args[0])
	if nodes.is_empty():
		_error("Nothing matches '%s'." % args[0])
		return
	for node in nodes:
		if not args[1] in node:
			_error("%s has no property '%s'." % [node.name, args[1]])
			continue
		_print("%s.%s = %s" % [node.name, args[1], var_to_str(node.get(args[1]))])


func _cmd_set(args: PackedStringArray) -> void:
	if args.size() < 3:
		_error("Usage: set <who> <property> <value>")
		return
	var nodes := _targets(args[0])
	if nodes.is_empty():
		_error("Nothing matches '%s'." % args[0])
		return
	var text := " ".join(args.slice(2))
	for node in nodes:
		if not args[1] in node:
			_error("%s has no property '%s'." % [node.name, args[1]])
			continue
		var value: Variant = _parse_value(text, typeof(node.get(args[1])))
		if value == null:
			_error("Can't read '%s' as a %s." % [text, type_string(typeof(node.get(args[1])))])
			return
		node.set(args[1], value)
		_ok("%s.%s = %s" % [node.name, args[1], var_to_str(node.get(args[1]))])


# --- Applying cheats and overrides --------------------------------------------

## New ships pick up the cheats and overrides before their _ready().
func _on_node_added(node: Node) -> void:
	if node is Fighter:
		_apply(node)


func _apply_to_all() -> void:
	for group in ["player", "wingmen", "enemies"]:
		for node in get_tree().get_nodes_in_group(group):
			_apply(node)


func _apply(node: Node) -> void:
	if node is Ship:
		var ship := node as Ship
		ship.invincible = god
		ship.untargetable = notarget
		var mult: float = _overrides.get("speed", 1.0)
		for property in SPEED_PROPERTIES:
			ship.set(property, _base(ship, property) * mult)
		ship.fire_interval = _base(ship, &"fire_interval") / float(_overrides.get("firerate", 1.0))
		ship.bolt_damage = _overrides.get("damage", -1)
	elif node is Wingman:
		(node as Wingman).invincible = wingmen_god
	elif node is EnemyFighter:
		var enemy := node as EnemyFighter
		enemy.max_health = _overrides.get("enemy_health", _base(enemy, &"max_health"))
		if enemy.health > 0:  # already in play (0 before _ready(), which fills it)
			enemy.health = enemy.max_health
		enemy.bolt_damage = _overrides.get("enemy_damage", -1)


## The scene's own value of `property` on `node`, remembered (as metadata) the
## first time an override touches it, so overrides scale it and `reset` puts it back.
func _base(node: Node, property: StringName) -> Variant:
	var key := StringName("dev_base_" + property)
	if not node.has_meta(key):
		node.set_meta(key, node.get(property))
	return node.get_meta(key)


# --- Helpers ---------------------------------------------------------------------

func _ship() -> Ship:
	return get_tree().get_first_node_in_group("player") as Ship


func _spawner() -> EnemySpawner:
	return get_tree().get_first_node_in_group("enemy_spawner") as EnemySpawner


## Nodes `who` names: a shorthand, a wingman's call sign, or any group.
func _targets(who: String) -> Array[Node]:
	var nodes: Array[Node] = []
	match who.to_lower():
		"player":
			nodes = get_tree().get_nodes_in_group("player")
		"spawner":
			nodes = get_tree().get_nodes_in_group("enemy_spawner")
		"level":
			if get_tree().current_scene:
				nodes.append(get_tree().current_scene)
		_:
			for node in get_tree().get_nodes_in_group("wingmen"):
				if node is Wingman and (node as Wingman).call_sign.to_lower() == who.to_lower():
					nodes.append(node)
			if nodes.is_empty():
				nodes = get_tree().get_nodes_in_group(who)
	return nodes


func _target_names() -> PackedStringArray:
	var names := PackedStringArray(["player", "wingmen", "enemies", "destroyer", "spawner", "level"])
	for node in get_tree().get_nodes_in_group("wingmen"):
		if node is Wingman:
			names.append((node as Wingman).call_sign.to_lower())
	return names


func _reset_option() -> PackedStringArray:
	return PackedStringArray(["reset"])


## Resource file names (without .tres) in `dir`; exported builds list them as .remap.
func _resource_names(dir: String) -> PackedStringArray:
	var names := PackedStringArray()
	for file in DirAccess.get_files_at(dir):
		file = file.trim_suffix(".remap")
		if file.ends_with(".tres"):
			names.append(file.get_basename())
	return names


func _mission_names() -> PackedStringArray:
	return _resource_names(MISSIONS_DIR)


func _speaker_names() -> PackedStringArray:
	return _resource_names(SPEAKERS_DIR)


## true / false for on, off, true, false, 1, 0; null otherwise.
func _parse_bool(text: String) -> Variant:
	match text.to_lower():
		"on", "true", "1", "yes":
			return true
		"off", "false", "0", "no":
			return false
	return null


## `text` as a value of `type`, or null if it can't be read as one.
func _parse_value(text: String, type: Variant.Type) -> Variant:
	match type:
		TYPE_BOOL:
			return _parse_bool(text)
		TYPE_INT:
			if text.is_valid_int():
				return text.to_int()
		TYPE_FLOAT:
			if text.is_valid_float():
				return text.to_float()
		TYPE_STRING:
			return text
		TYPE_STRING_NAME:
			return StringName(text)
		_:
			var value: Variant = str_to_var(text)
			if typeof(value) == type:
				return value
	return null
