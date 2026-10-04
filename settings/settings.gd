extends Node
## Autoload "Settings": display options and control bindings.
##
## Owns every gameplay input action: registers them in the InputMap at startup,
## lets the settings screen rebind them, and saves everything to
## user://settings.cfg. Each action has three binding slots: two for keyboard /
## mouse (primary and alternate) and one for the gamepad.
##
## Mouse movement always steers (see Ship); it isn't an action, so it isn't
## rebindable.

signal bindings_changed
signal display_changed
## The player switched between gamepad and keyboard/mouse (see using_gamepad).
signal input_device_changed

const SAVE_PATH := "user://settings.cfg"

enum Slot { PRIMARY, ALTERNATE, GAMEPAD }

## Window sizes offered by the settings screen (the most common ones).
## Sizes larger than the screen are left out.
const RESOLUTIONS: Array[Vector2i] = [
	Vector2i(1280, 720),
	Vector2i(1366, 768),
	Vector2i(1600, 900),
	Vector2i(1920, 1080),
	Vector2i(2560, 1440),
	Vector2i(3840, 2160),
]

## Rebindable actions in display order, grouped for the controls screen.
const ACTIONS := [
	{"group": "Flight", "id": &"steer_up", "name": "Steer Up"},
	{"group": "Flight", "id": &"steer_down", "name": "Steer Down"},
	{"group": "Flight", "id": &"steer_left", "name": "Steer Left"},
	{"group": "Flight", "id": &"steer_right", "name": "Steer Right"},
	{"group": "Flight", "id": &"throttle_up", "name": "Throttle Up"},
	{"group": "Flight", "id": &"throttle_down", "name": "Throttle Down"},
	{"group": "Flight", "id": &"roll_left", "name": "Roll Left"},
	{"group": "Flight", "id": &"roll_right", "name": "Roll Right"},
	{"group": "Flight", "id": &"boost", "name": "Boost"},
	{"group": "Weapons", "id": &"fire", "name": "Fire"},
	{"group": "Wingmen", "id": &"select_wingman_1", "name": "Select Wingman 1"},
	{"group": "Wingmen", "id": &"select_wingman_2", "name": "Select Wingman 2"},
	{"group": "Wingmen", "id": &"select_wingman_3", "name": "Select Wingman 3"},
	{"group": "Wingmen", "id": &"select_all", "name": "Select All Wingmen"},
	{"group": "Wingmen", "id": &"command_attack", "name": "Order: Attack Target"},
	{"group": "Wingmen", "id": &"command_cover", "name": "Order: Cover Me"},
	# Kept as command_cancel so saved bindings carry over from when it was "Regroup".
	{"group": "Wingmen", "id": &"command_cancel", "name": "Order: Form Up"},
	{"group": "Wingmen", "id": &"command_free", "name": "Order: Weapons Free"},
	{"group": "System", "id": &"pause", "name": "Pause"},
]

const DEADZONE := 0.2

var fullscreen := false
var resolution := Vector2i(1280, 720)
## True while the player is using a gamepad (the last input came from one).
var using_gamepad := false

## action id -> Array of 3 InputEvents (or null), indexed by Slot.
var _bindings := {}


func _ready() -> void:
	# Keep tracking the input device while the game is paused.
	process_mode = Node.PROCESS_MODE_ALWAYS
	_add_menu_gamepad_buttons()
	_bindings = _default_bindings()
	_load()
	_apply_bindings()
	_apply_display.call_deferred()


## Tracks which device the player is using, so the HUD can show only the
## matching hints (no mouse cursor or keyboard keys while on a gamepad).
## Small stick drift and tiny mouse nudges don't count as switching.
func _input(event: InputEvent) -> void:
	var gamepad := using_gamepad
	if event is InputEventJoypadButton and event.is_pressed():
		gamepad = true
	elif event is InputEventJoypadMotion and absf((event as InputEventJoypadMotion).axis_value) > 0.5:
		gamepad = true
	elif event is InputEventMouseMotion and (event as InputEventMouseMotion).screen_relative.length() > 3.0:
		gamepad = false
	elif (event is InputEventKey or event is InputEventMouseButton) and event.is_pressed():
		gamepad = false
	if gamepad != using_gamepad:
		using_gamepad = gamepad
		input_device_changed.emit()


## Godot's built-in menu actions have no gamepad button for accept or cancel
## (only the D-pad / left stick for moving focus), so add A and B to them.
func _add_menu_gamepad_buttons() -> void:
	for pair in [[&"ui_accept", JOY_BUTTON_A], [&"ui_cancel", JOY_BUTTON_B]]:
		var event := _button(pair[1])
		if not InputMap.action_has_event(pair[0], event):
			InputMap.action_add_event(pair[0], event)


# --- Display -----------------------------------------------------------------

func set_fullscreen(on: bool) -> void:
	fullscreen = on
	_apply_display()
	save()


func set_resolution(size: Vector2i) -> void:
	resolution = size
	_apply_display()
	save()


## The resolutions that fit on the current screen (always at least one).
func available_resolutions() -> Array[Vector2i]:
	var screen := _screen_size()
	var fits: Array[Vector2i] = []
	fits.assign(RESOLUTIONS.filter(
		func(r: Vector2i) -> bool: return r.x <= screen.x and r.y <= screen.y))
	if fits.is_empty():
		fits.append(RESOLUTIONS[0])
	return fits


func _screen_size() -> Vector2i:
	if DisplayServer.get_name() == "headless":
		return RESOLUTIONS[-1]
	return DisplayServer.screen_get_size(DisplayServer.window_get_current_screen())


## Windowed: the window is resized to the resolution and centred.
## Fullscreen: the window fills the screen, and the 3D scene renders at the
## chosen resolution and is scaled up (the UI stays sharp at native size).
func _apply_display() -> void:
	if DisplayServer.get_name() == "headless":
		return
	var window := get_tree().root
	if fullscreen:
		window.mode = Window.MODE_FULLSCREEN
		var screen := _screen_size()
		window.scaling_3d_scale = clampf(float(resolution.y) / float(screen.y), 0.25, 1.0)
	else:
		window.mode = Window.MODE_WINDOWED
		window.scaling_3d_scale = 1.0
		var screen := DisplayServer.window_get_current_screen()
		var usable := DisplayServer.screen_get_usable_rect(screen)
		window.size = resolution
		window.position = usable.position + (usable.size - resolution) / 2
	display_changed.emit()


# --- Bindings ----------------------------------------------------------------

## The event bound to an action's slot, or null.
func get_binding(action: StringName, slot: Slot) -> InputEvent:
	return _bindings[action][slot]


## True if this event can go in this slot (keys and mouse buttons go in the
## keyboard slots, joypad buttons and sticks in the gamepad slot).
func accepts(slot: Slot, event: InputEvent) -> bool:
	if slot == Slot.GAMEPAD:
		return event is InputEventJoypadButton or event is InputEventJoypadMotion
	return event is InputEventKey or event is InputEventMouseButton


## Binds the event to the slot. Anything else using the same input loses it,
## so one key never does two things. Returns the display names of the actions
## that lost it (for the settings screen to report).
func bind(action: StringName, slot: Slot, event: InputEvent) -> PackedStringArray:
	var code := event_to_code(event)
	var unbound := PackedStringArray()
	for other in _bindings:
		var slots: Array = _bindings[other]
		for i in slots.size():
			if slots[i] != null and event_to_code(slots[i]) == code and not (other == action and i == slot):
				slots[i] = null
				if other != action:
					unbound.append(action_name(other))
	_bindings[action][slot] = code_to_event(code)
	_apply_bindings()
	save()
	return unbound


func clear(action: StringName, slot: Slot) -> void:
	_bindings[action][slot] = null
	_apply_bindings()
	save()


func reset_controls() -> void:
	_bindings = _default_bindings()
	_apply_bindings()
	save()


func action_name(action: StringName) -> String:
	for entry in ACTIONS:
		if entry.id == action:
			return entry.name
	return String(action)


func _apply_bindings() -> void:
	for entry in ACTIONS:
		var action: StringName = entry.id
		if not InputMap.has_action(action):
			InputMap.add_action(action, DEADZONE)
		InputMap.action_erase_events(action)
		for event in _bindings[action]:
			if event != null:
				InputMap.action_add_event(action, event)
	bindings_changed.emit()


func _default_bindings() -> Dictionary:
	return {
		&"steer_up": [_key(KEY_UP), null, _axis(JOY_AXIS_LEFT_Y, -1.0)],
		&"steer_down": [_key(KEY_DOWN), null, _axis(JOY_AXIS_LEFT_Y, 1.0)],
		&"steer_left": [_key(KEY_LEFT), null, _axis(JOY_AXIS_LEFT_X, -1.0)],
		&"steer_right": [_key(KEY_RIGHT), null, _axis(JOY_AXIS_LEFT_X, 1.0)],
		&"throttle_up": [_key(KEY_W), null, _axis(JOY_AXIS_RIGHT_Y, -1.0)],
		&"throttle_down": [_key(KEY_S), null, _axis(JOY_AXIS_RIGHT_Y, 1.0)],
		&"roll_left": [_key(KEY_Q), _key(KEY_A), _button(JOY_BUTTON_LEFT_SHOULDER)],
		&"roll_right": [_key(KEY_E), _key(KEY_D), _button(JOY_BUTTON_RIGHT_SHOULDER)],
		&"boost": [_key(KEY_SHIFT), null, _button(JOY_BUTTON_A)],
		&"fire": [_mouse(MOUSE_BUTTON_LEFT), _key(KEY_SPACE), _axis(JOY_AXIS_TRIGGER_RIGHT, 1.0)],
		&"select_wingman_1": [_key(KEY_1), null, _button(JOY_BUTTON_DPAD_LEFT)],
		&"select_wingman_2": [_key(KEY_2), null, _button(JOY_BUTTON_DPAD_UP)],
		&"select_wingman_3": [_key(KEY_3), null, _button(JOY_BUTTON_DPAD_RIGHT)],
		&"select_all": [_key(KEY_4), null, _button(JOY_BUTTON_DPAD_DOWN)],
		&"command_attack": [_key(KEY_F), null, _button(JOY_BUTTON_Y)],
		&"command_cover": [_key(KEY_C), null, _button(JOY_BUTTON_X)],
		&"command_cancel": [_key(KEY_R), null, _button(JOY_BUTTON_B)],
		&"command_free": [_key(KEY_V), null, _button(JOY_BUTTON_BACK)],
		&"pause": [_key(KEY_ESCAPE), null, _button(JOY_BUTTON_START)],
	}


func _key(keycode: Key) -> InputEventKey:
	var event := InputEventKey.new()
	event.physical_keycode = keycode
	return event


func _mouse(button: MouseButton) -> InputEventMouseButton:
	var event := InputEventMouseButton.new()
	event.button_index = button
	return event


func _button(button: JoyButton) -> InputEventJoypadButton:
	var event := InputEventJoypadButton.new()
	event.button_index = button
	return event


func _axis(axis: JoyAxis, direction: float) -> InputEventJoypadMotion:
	var event := InputEventJoypadMotion.new()
	event.axis = axis
	event.axis_value = signf(direction)
	return event


# --- Event <-> text ----------------------------------------------------------

## Compact text form used for saving and comparing bindings:
## "key:<physical keycode>", "mouse:<button>", "button:<joy button>",
## "axis:<joy axis>:<+1|-1>". Empty for unsupported events.
func event_to_code(event: InputEvent) -> String:
	if event is InputEventKey:
		var key := event as InputEventKey
		var code := key.physical_keycode if key.physical_keycode != KEY_NONE else key.keycode
		return "key:%d" % code
	if event is InputEventMouseButton:
		return "mouse:%d" % (event as InputEventMouseButton).button_index
	if event is InputEventJoypadButton:
		return "button:%d" % (event as InputEventJoypadButton).button_index
	if event is InputEventJoypadMotion:
		var motion := event as InputEventJoypadMotion
		return "axis:%d:%d" % [motion.axis, 1 if motion.axis_value > 0.0 else -1]
	return ""


func code_to_event(code: String) -> InputEvent:
	var parts := code.split(":")
	match parts[0]:
		"key":
			return _key(int(parts[1]) as Key)
		"mouse":
			return _mouse(int(parts[1]) as MouseButton)
		"button":
			return _button(int(parts[1]) as JoyButton)
		"axis":
			if parts.size() == 3:
				return _axis(int(parts[1]) as JoyAxis, float(parts[2]))
	return null


## Player-facing name of an input, e.g. "Shift", "Left Mouse", "RT", "Left Stick Up".
func event_name(event: InputEvent) -> String:
	if event == null:
		return "—"
	if event is InputEventKey:
		var physical := (event as InputEventKey).physical_keycode
		# Show the key's label on the player's keyboard layout (e.g. Z on AZERTY
		# for the key in QWERTY's W position), where the platform supports it.
		var keycode := KEY_NONE
		if DisplayServer.get_name() != "headless":
			keycode = DisplayServer.keyboard_get_keycode_from_physical(physical)
		var text := OS.get_keycode_string(keycode if keycode != KEY_NONE else physical)
		return text if text != "" else "Key %d" % physical
	if event is InputEventMouseButton:
		var button := (event as InputEventMouseButton).button_index
		const MOUSE_NAMES := {
			MOUSE_BUTTON_LEFT: "Left Mouse", MOUSE_BUTTON_RIGHT: "Right Mouse",
			MOUSE_BUTTON_MIDDLE: "Middle Mouse", MOUSE_BUTTON_WHEEL_UP: "Wheel Up",
			MOUSE_BUTTON_WHEEL_DOWN: "Wheel Down", MOUSE_BUTTON_WHEEL_LEFT: "Wheel Left",
			MOUSE_BUTTON_WHEEL_RIGHT: "Wheel Right", MOUSE_BUTTON_XBUTTON1: "Mouse 4",
			MOUSE_BUTTON_XBUTTON2: "Mouse 5",
		}
		return MOUSE_NAMES.get(button, "Mouse %d" % button)
	if event is InputEventJoypadButton:
		var button := (event as InputEventJoypadButton).button_index
		# Xbox-style names, the most common layout.
		const BUTTON_NAMES := {
			JOY_BUTTON_A: "A", JOY_BUTTON_B: "B", JOY_BUTTON_X: "X", JOY_BUTTON_Y: "Y",
			JOY_BUTTON_BACK: "Back", JOY_BUTTON_GUIDE: "Guide", JOY_BUTTON_START: "Start",
			JOY_BUTTON_LEFT_STICK: "LS Click", JOY_BUTTON_RIGHT_STICK: "RS Click",
			JOY_BUTTON_LEFT_SHOULDER: "LB", JOY_BUTTON_RIGHT_SHOULDER: "RB",
			JOY_BUTTON_DPAD_UP: "D-Pad Up", JOY_BUTTON_DPAD_DOWN: "D-Pad Down",
			JOY_BUTTON_DPAD_LEFT: "D-Pad Left", JOY_BUTTON_DPAD_RIGHT: "D-Pad Right",
			JOY_BUTTON_MISC1: "Share",
		}
		return BUTTON_NAMES.get(button, "Button %d" % button)
	if event is InputEventJoypadMotion:
		var motion := event as InputEventJoypadMotion
		var positive := motion.axis_value > 0.0
		match motion.axis:
			JOY_AXIS_LEFT_X:
				return "Left Stick Right" if positive else "Left Stick Left"
			JOY_AXIS_LEFT_Y:
				return "Left Stick Down" if positive else "Left Stick Up"
			JOY_AXIS_RIGHT_X:
				return "Right Stick Right" if positive else "Right Stick Left"
			JOY_AXIS_RIGHT_Y:
				return "Right Stick Down" if positive else "Right Stick Up"
			JOY_AXIS_TRIGGER_LEFT:
				return "LT"
			JOY_AXIS_TRIGGER_RIGHT:
				return "RT"
		return "Axis %d %s" % [motion.axis, "+" if positive else "-"]
	return "?"


## Short help-text form of an action's bindings for one device, e.g.
## "LMB / Space" (keyboard and mouse) or "RT" (gamepad).
func describe(action: StringName, gamepad: bool) -> String:
	var slots := [Slot.GAMEPAD] if gamepad else [Slot.PRIMARY, Slot.ALTERNATE]
	var names := PackedStringArray()
	for slot in slots:
		var event := get_binding(action, slot)
		if event != null:
			names.append(_short_name(event))
	return " / ".join(names) if not names.is_empty() else "unbound"


## Help-text form of a pair of opposite actions, e.g. "W/S", "LB/RB", or
## "Right Stick" when both are the two directions of one stick axis.
func describe_pair(negative: StringName, positive: StringName, gamepad: bool) -> String:
	var slot := Slot.GAMEPAD if gamepad else Slot.PRIMARY
	var a := get_binding(negative, slot)
	var b := get_binding(positive, slot)
	if a is InputEventJoypadMotion and b is InputEventJoypadMotion \
			and (a as InputEventJoypadMotion).axis == (b as InputEventJoypadMotion).axis:
		return _stick_name(a)
	return "%s/%s" % [_short_name(a), _short_name(b)]


## Help-text form of the four steering actions, e.g. "Mouse / Arrows" or "Left Stick".
func describe_steering(gamepad: bool) -> String:
	var steer: Array[StringName] = [&"steer_up", &"steer_down", &"steer_left", &"steer_right"]
	var slot := Slot.GAMEPAD if gamepad else Slot.PRIMARY
	var events := steer.map(func(a: StringName) -> InputEvent: return get_binding(a, slot))
	if gamepad:
		if events.all(func(e: InputEvent) -> bool: return e is InputEventJoypadMotion) \
				and events.all(func(e: InputEvent) -> bool: return _stick_name(e) == _stick_name(events[0])):
			return _stick_name(events[0])
		return "/".join(events.map(func(e: InputEvent) -> String: return _short_name(e)))
	var parts := PackedStringArray(["Mouse"])
	var arrow_codes := [KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT].map(func(k: Key) -> String: return "key:%d" % k)
	if events.map(func(e: InputEvent) -> String: return event_to_code(e) if e else "") == arrow_codes:
		parts.append("Arrows")
	elif not events.has(null):
		parts.append("/".join(events.map(func(e: InputEvent) -> String: return _short_name(e))))
	return " / ".join(parts)


## "Left Stick" / "Right Stick" for a stick direction; the plain name otherwise.
func _stick_name(event: InputEvent) -> String:
	var text := event_name(event)
	return text.get_slice(" Stick", 0) + " Stick" if text.contains(" Stick") else text


func _short_name(event: InputEvent) -> String:
	if event == null:
		return "—"
	if event is InputEventMouseButton and (event as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT:
		return "LMB"
	if event is InputEventMouseButton and (event as InputEventMouseButton).button_index == MOUSE_BUTTON_RIGHT:
		return "RMB"
	return event_name(event)


# --- Saving ------------------------------------------------------------------

func save() -> void:
	var config := ConfigFile.new()
	config.set_value("display", "fullscreen", fullscreen)
	config.set_value("display", "resolution", resolution)
	for action in _bindings:
		var codes := PackedStringArray()
		for event in _bindings[action]:
			codes.append(event_to_code(event) if event != null else "")
		config.set_value("controls", action, codes)
	config.save(SAVE_PATH)


func _load() -> void:
	var config := ConfigFile.new()
	if config.load(SAVE_PATH) != OK:
		resolution = _default_resolution()
		return
	fullscreen = config.get_value("display", "fullscreen", fullscreen)
	resolution = config.get_value("display", "resolution", _default_resolution())
	# Actions missing from the file (e.g. added in a later version) keep their defaults.
	for action in _bindings:
		var codes: PackedStringArray = config.get_value("controls", action, PackedStringArray())
		if codes.size() != Slot.size():
			continue
		for i in codes.size():
			_bindings[action][i] = code_to_event(codes[i]) if codes[i] != "" else null


func _default_resolution() -> Vector2i:
	return available_resolutions()[0]
