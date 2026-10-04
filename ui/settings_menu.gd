extends Control
## Settings screen, shared by the title screen and the pause menu.
##
## Main page: fullscreen, resolution and a button to the Controls page.
## Controls page: every ship action with two keyboard/mouse slots and one
## gamepad slot. Selecting a slot waits for the next input and binds it
## (Esc cancels, Backspace/Delete clears). Changes apply and save immediately
## through the Settings autoload.

signal closed

const COLUMN_WIDTHS := [280, 200, 200, 240]
const COLUMN_TITLES := ["Action", "Primary", "Alternate", "Gamepad"]
const SLOT_FONT_SIZE := 17
const GROUP_COLOR := Color(0.45, 1.0, 0.55, 0.8)
const HEADER_COLOR := Color(0.85, 0.95, 1.0, 0.5)
const HINT := "Select a binding to change it. Mouse movement always steers."
## Seconds to wait for an input before giving up on a rebind.
const CAPTURE_TIMEOUT := 6.0
## After a rebind, gamepad input is ignored this long so a still-held stick
## or button doesn't also move the menu focus.
const AFTER_CAPTURE_GRACE := 0.35

@onready var _main_page: Control = %MainPage
@onready var _controls_page: Control = %ControlsPage
@onready var _fullscreen_button: Button = %FullscreenButton
@onready var _resolution_option: OptionButton = %ResolutionOption
@onready var _controls_button: Button = %ControlsButton
@onready var _back_button: Button = %BackButton
@onready var _header: HBoxContainer = %Header
@onready var _rows: VBoxContainer = %Rows
@onready var _status: Label = %StatusLabel
@onready var _reset_button: Button = %ResetButton
@onready var _controls_back_button: Button = %ControlsBackButton

var _resolutions: Array[Vector2i] = []
## Every binding button, with its action and slot stored as metadata.
var _slot_buttons: Array[Button] = []
var _capture_button: Button
var _capture_armed := false
var _capture_left := 0.0
var _grace_left := 0.0


func _ready() -> void:
	hide()
	_build_controls()
	_fullscreen_button.pressed.connect(_on_fullscreen_pressed)
	_resolution_option.item_selected.connect(_on_resolution_selected)
	_controls_button.pressed.connect(_show_controls)
	_back_button.pressed.connect(close)
	_reset_button.pressed.connect(_on_reset_pressed)
	_controls_back_button.pressed.connect(_show_main)
	Settings.bindings_changed.connect(_refresh_slots)
	Settings.display_changed.connect(_refresh_display)


func open() -> void:
	show()
	_refresh_display()
	_refresh_slots()
	_show_main()


func close() -> void:
	_cancel_capture()
	hide()
	closed.emit()


func _show_main() -> void:
	_cancel_capture()
	var from_controls := _controls_page.visible
	_controls_page.hide()
	_main_page.show()
	(_controls_button if from_controls else _fullscreen_button).grab_focus()


func _show_controls() -> void:
	_main_page.hide()
	_controls_page.show()
	_status.text = HINT
	_slot_buttons[0].grab_focus()


func _unhandled_input(event: InputEvent) -> void:
	if not visible or _capture_button != null:
		return
	if event.is_action_pressed("ui_cancel") or event.is_action_pressed("pause"):
		get_viewport().set_input_as_handled()
		if _controls_page.visible:
			_show_main()
		else:
			close()


# --- Display page ------------------------------------------------------------

func _refresh_display() -> void:
	_fullscreen_button.text = "On" if Settings.fullscreen else "Off"
	_resolutions = Settings.available_resolutions()
	if not _resolutions.has(Settings.resolution):
		_resolutions.append(Settings.resolution)
	_resolution_option.clear()
	for size in _resolutions:
		_resolution_option.add_item("%d × %d" % [size.x, size.y])
	_resolution_option.select(_resolutions.find(Settings.resolution))


func _on_fullscreen_pressed() -> void:
	Settings.set_fullscreen(not Settings.fullscreen)


func _on_resolution_selected(index: int) -> void:
	Settings.set_resolution(_resolutions[index])


# --- Controls page -----------------------------------------------------------

func _build_controls() -> void:
	for i in COLUMN_TITLES.size():
		var label := _make_label(COLUMN_TITLES[i], 16, HEADER_COLOR)
		label.custom_minimum_size.x = COLUMN_WIDTHS[i]
		if i > 0:
			label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		_header.add_child(label)

	var group := ""
	for entry in Settings.ACTIONS:
		if entry.group != group:
			group = entry.group
			var heading := _make_label(group.to_upper(), 15, GROUP_COLOR)
			heading.custom_minimum_size.x = COLUMN_WIDTHS.reduce(func(a: int, b: int) -> int: return a + b) + 36
			var heading_row := HBoxContainer.new()
			heading_row.alignment = BoxContainer.ALIGNMENT_CENTER
			heading_row.add_child(heading)
			_rows.add_child(heading_row)

		var row := HBoxContainer.new()
		row.alignment = BoxContainer.ALIGNMENT_CENTER
		row.add_theme_constant_override("separation", 12)
		var name_label := _make_label(entry.name, 18, Color(0.85, 0.95, 1.0))
		name_label.custom_minimum_size.x = COLUMN_WIDTHS[0]
		row.add_child(name_label)
		for slot in [Settings.Slot.PRIMARY, Settings.Slot.ALTERNATE, Settings.Slot.GAMEPAD]:
			var button := Button.new()
			button.custom_minimum_size = Vector2(COLUMN_WIDTHS[slot + 1], 36)
			button.add_theme_font_size_override("font_size", SLOT_FONT_SIZE)
			button.clip_text = true
			button.set_meta("action", entry.id)
			button.set_meta("slot", slot)
			button.pressed.connect(_start_capture.bind(button))
			row.add_child(button)
			_slot_buttons.append(button)
		_rows.add_child(row)


func _make_label(text: String, size: int, color: Color) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", color)
	return label


func _refresh_slots() -> void:
	for button in _slot_buttons:
		if button == _capture_button:
			continue
		button.text = Settings.event_name(Settings.get_binding(button.get_meta("action"), button.get_meta("slot")))


func _on_reset_pressed() -> void:
	_cancel_capture()
	Settings.reset_controls()
	_status.text = "Controls reset to defaults."


# --- Rebinding ---------------------------------------------------------------

func _start_capture(button: Button) -> void:
	_cancel_capture()
	_capture_button = button
	_capture_left = CAPTURE_TIMEOUT
	var gamepad: bool = button.get_meta("slot") == Settings.Slot.GAMEPAD
	button.text = "Press a button…" if gamepad else "Press a key…"
	_status.text = "%s: press %s.   Esc: cancel   Backspace: clear" % [
		Settings.action_name(button.get_meta("action")),
		"a gamepad button, trigger or stick direction" if gamepad else "a key or mouse button"]
	# Skip the rest of the input that selected the slot (e.g. the Enter or A press).
	_capture_armed = false
	await get_tree().process_frame
	_capture_armed = true


func _input(event: InputEvent) -> void:
	if _capture_button == null:
		if _grace_left > 0.0 and (event is InputEventJoypadButton or event is InputEventJoypadMotion):
			get_viewport().set_input_as_handled()
		return
	# While waiting for an input, nothing else (menu navigation, pause) sees it.
	get_viewport().set_input_as_handled()
	if not _capture_armed:
		return

	var key := event as InputEventKey
	if key and key.pressed and not key.echo:
		if key.physical_keycode == KEY_ESCAPE:
			_end_capture("Cancelled.")
			return
		if key.physical_keycode in [KEY_BACKSPACE, KEY_DELETE]:
			Settings.clear(_capture_button.get_meta("action"), _capture_button.get_meta("slot"))
			_end_capture("Cleared.")
			return

	if not _is_new_press(event):
		return
	var action: StringName = _capture_button.get_meta("action")
	var slot: Settings.Slot = _capture_button.get_meta("slot")
	if not Settings.accepts(slot, event):
		_status.text = "That slot needs %s." % ("a gamepad input" if slot == Settings.Slot.GAMEPAD else "a key or mouse button")
		return
	var unbound := Settings.bind(action, slot, event)
	var message := "%s: %s" % [Settings.action_name(action), Settings.event_name(event)]
	if not unbound.is_empty():
		message += "   (removed from %s)" % ", ".join(unbound)
	_end_capture(message)


## True for a key / button press, or a stick or trigger pushed most of the way.
func _is_new_press(event: InputEvent) -> bool:
	if event is InputEventJoypadMotion:
		return absf((event as InputEventJoypadMotion).axis_value) >= 0.6
	if event is InputEventKey or event is InputEventMouseButton or event is InputEventJoypadButton:
		return event.is_pressed() and not event.is_echo()
	return false


func _process(delta: float) -> void:
	_grace_left = maxf(_grace_left - delta, 0.0)
	if _capture_button != null:
		_capture_left -= delta
		if _capture_left <= 0.0:
			_end_capture("No input received; binding unchanged.")


func _end_capture(message: String) -> void:
	var button := _capture_button
	_capture_button = null
	_grace_left = AFTER_CAPTURE_GRACE
	_refresh_slots()
	_status.text = message
	button.grab_focus()


func _cancel_capture() -> void:
	if _capture_button != null:
		_capture_button = null
		_refresh_slots()
