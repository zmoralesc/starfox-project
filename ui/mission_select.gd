extends Control
## Mission selector, opened by Start on the title screen. One button per
## mission in `missions`; the highlighted mission's description shows under
## the list. Esc / B / Back returns to the title menu.

signal chosen(mission: Mission)
signal closed

const HEADER_COLOR := Color(0.85, 0.95, 1.0, 0.8)
const DESCRIPTION_COLOR := Color(0.85, 0.95, 1.0, 0.65)

## The missions to list, in order.
@export var missions: Array[Mission] = []

var _buttons: Array[Button] = []
var _description: Label
var _back_button: Button


func _ready() -> void:
	hide()
	_build()


func open() -> void:
	show()
	for button in _buttons:
		button.disabled = false
	if not _buttons.is_empty():
		_buttons[0].grab_focus()
		_show_description(missions[0])


func close() -> void:
	hide()
	closed.emit()


func _build() -> void:
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	var list := VBoxContainer.new()
	list.add_theme_constant_override("separation", 14)
	center.add_child(list)

	var header := Label.new()
	header.text = "SELECT MISSION"
	header.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	header.add_theme_font_size_override("font_size", 40)
	header.add_theme_color_override("font_color", HEADER_COLOR)
	list.add_child(header)
	list.add_child(_spacer(16))

	for mission in missions:
		var button := Button.new()
		button.text = mission.title
		button.custom_minimum_size = Vector2(360, 52)
		button.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
		button.pressed.connect(_on_mission_pressed.bind(mission))
		# Keyboard/gamepad focus and mouse hover both show the description.
		button.focus_entered.connect(_show_description.bind(mission))
		button.mouse_entered.connect(_show_description.bind(mission))
		list.add_child(button)
		_buttons.append(button)

	_description = Label.new()
	_description.custom_minimum_size = Vector2(560, 56)
	_description.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_description.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_description.add_theme_color_override("font_color", DESCRIPTION_COLOR)
	list.add_child(_description)
	list.add_child(_spacer(8))

	_back_button = Button.new()
	_back_button.text = "Back"
	_back_button.custom_minimum_size = Vector2(240, 52)
	_back_button.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	_back_button.pressed.connect(close)
	list.add_child(_back_button)


func _spacer(height: float) -> Control:
	var spacer := Control.new()
	spacer.custom_minimum_size = Vector2(0, height)
	return spacer


func _show_description(mission: Mission) -> void:
	_description.text = mission.description


func _on_mission_pressed(mission: Mission) -> void:
	# No double-starts while the fade runs.
	for button in _buttons:
		button.disabled = true
	_back_button.disabled = true
	chosen.emit(mission)


func _unhandled_input(event: InputEvent) -> void:
	if not visible:
		return
	if event.is_action_pressed("ui_cancel") or event.is_action_pressed("pause"):
		get_viewport().set_input_as_handled()
		close()
