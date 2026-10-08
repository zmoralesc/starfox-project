class_name Comms
extends CanvasLayer
## In-game comms, bottom left: a portrait square with the speaker's name under
## it, and a box to its right where their line types out letter by letter.
##
## Anything can talk through it with say(). Each line is spoken over a
## recording (`voice`) if it has one, or with short beeps as the letters
## appear, pitched per speaker.
##
## Priorities:
## - LOW lines never interrupt anything. One that arrives while another line
##   is on screen is dropped (chatter like "Aye aye." goes stale fast).
## - HIGH lines (story, important callouts) interrupt LOW ones at once. A HIGH
##   line arriving during another HIGH line waits its turn, so none is lost.
## - URGENT lines (the lament when the player's ship is lost) interrupt
##   anything and drop every line still waiting.
##
## It's its own layer, separate from the HUD, so lines can play during
## cutscenes while the HUD is hidden. It pauses with the game.
##
## Opening, all driven by one value, _open_t (see _apply_open()):
## 1. the portrait square expands from a horizontal line,
## 2. it shows static for a moment,
## 3. the portrait and name appear as the text box unfolds to the right.
## Then the line types out. Closing plays the same timeline backwards, except
## that the portrait and name cut to static as soon as it starts. A line
## waiting in the queue turns a closing box around once it's back to static,
## so the next speaker comes in without the square collapsing. A different
## speaker interrupting an open box gets a short burst of static over the
## portrait (SWITCHING) instead.

enum Priority { LOW, HIGH, URGENT }

enum Phase { IDLE, OPENING, SWITCHING, TYPING, HOLDING, CLOSING }

const PORTRAIT_SIZE := 88.0
const NAME_HEIGHT := 20.0
const BOX_WIDTH := 400.0
const GAP := 8.0
const MARGIN := 24.0
const BEEP_RATE := 22050
const STATIC_SHADER := preload("res://comms/static.gdshader")

## Letters typed per second.
@export var chars_per_second := 40.0
## Extra pause after . ! ? and after , ; : (seconds).
@export var sentence_pause := 0.18
@export var comma_pause := 0.08
## Seconds a finished line stays up, plus a little more per character.
@export var hold_time := 1.5
@export var hold_per_char := 0.03
## Beep on every Nth letter (1 = every letter). Spaces and punctuation are silent.
@export var beep_every := 2
@export var beep_volume_db := -12.0
@export var voice_volume_db := 0.0

@export_group("Opening and closing")
## Seconds for the portrait square to expand from a line (closing: collapse).
@export var expand_time := 0.09
## Seconds of static before the portrait appears (also a speaker switch).
@export var noise_time := 0.09
## Seconds for the text box to unfold to the right as the portrait appears.
@export var unfold_time := 0.12
## Thickness of the line the square expands from, in pixels.
@export var line_height := 2.0
## Static strength in the square while the speaker has no portrait (0 = none).
@export_range(0.0, 1.0) var empty_portrait_static := 0.3
## Backdrop behind a portrait: the speaker's colour darkened by this much.
@export_range(0.0, 1.0) var portrait_backdrop_darken := 0.72


class Line:
	var speaker: CommsSpeaker
	var text: String
	var priority: Priority
	var voice: AudioStream


var _line: Line
var _queue: Array[Line] = []
var _phase := Phase.IDLE
var _shown := 0
var _next_char_in := 0.0
var _hold_left := 0.0
## Seconds of the current recording still to play. Timed here rather than
## trusting the player's `playing` flag, so a broken audio device can't hold
## a line on screen forever.
var _voice_left := 0.0
var _letters := 0
## Position on the opening timeline: 0 = closed, _open_total() = fully open.
var _open_t := 0.0
## Seconds of static left in a speaker switch.
var _switch_left := 0.0
## Clock for the static shader; advances only while the comms run (not paused).
var _static_time := 0.0

var _panel: Control
var _portrait_frame: Panel
var _portrait: TextureRect
var _static: ColorRect
var _static_material: ShaderMaterial
var _name: Label
var _box: Panel
var _text: Label
var _beep: AudioStreamPlayer
var _voice: AudioStreamPlayer


## The level's comms, or null if there isn't one (e.g. in a test scene).
static func find(tree: SceneTree) -> Comms:
	return tree.get_first_node_in_group("comms") as Comms


func _ready() -> void:
	add_to_group("comms")
	_build()
	_panel.hide()


## Speaks a line. Returns false if it was dropped (a LOW line while another is
## on screen). See the class notes for how priorities interact.
func say(speaker: CommsSpeaker, text: String, priority := Priority.LOW, voice: AudioStream = null) -> bool:
	var line := Line.new()
	line.speaker = speaker
	line.text = text
	line.priority = priority
	line.voice = voice
	if priority == Priority.URGENT:
		_queue.clear()
		if _phase == Phase.TYPING or _phase == Phase.HOLDING or _phase == Phase.OPENING \
				or _phase == Phase.SWITCHING:
			_interrupt(line)
			return true
	if _phase == Phase.IDLE:
		_start(line)
		return true
	if _phase == Phase.CLOSING:
		# The box turns around for it once it's back to static (see _process).
		if _queue.is_empty() or priority == Priority.HIGH:
			_queue.append(line)
			return true
		return false
	if priority == Priority.HIGH:
		if _line.priority == Priority.LOW:
			_interrupt(line)
		else:
			_queue.append(line)
		return true
	return false


## True while a line is on screen (opening, typing, holding or closing).
func is_speaking() -> bool:
	return _phase != Phase.IDLE


## The line on screen, or null.
func current_line() -> Line:
	return _line if is_speaking() else null


## The part of the current line typed out so far.
func shown_text() -> String:
	return _line.text.left(_shown) if is_speaking() else ""


## Opens the box from closed for `line`.
func _start(line: Line) -> void:
	_set_content(line)
	_open_t = 0.0
	_phase = Phase.OPENING
	_panel.show()
	_apply_open()


## A HIGH line cutting off a LOW one. The same speaker just starts the new
## line; a different one gets a burst of static over the portrait first.
func _interrupt(line: Line) -> void:
	var new_speaker := line.speaker != _line.speaker
	_set_content(line)
	if _phase == Phase.OPENING:
		return  # keeps opening, now with the new line
	if new_speaker:
		_phase = Phase.SWITCHING
		_switch_left = noise_time
	else:
		_begin_typing()
	_apply_open()


## Puts `line` in the box (colours, name, portrait, untyped text) without
## changing the phase.
func _set_content(line: Line) -> void:
	_line = line
	_shown = 0
	_letters = 0
	_next_char_in = 0.0
	var color := line.speaker.color if line.speaker else Color.WHITE
	_set_border(_portrait_frame, color, 2)
	_set_border(_box, Color(color, 0.5), 1)
	_portrait.texture = line.speaker.portrait if line.speaker else null
	# Portraits are drawn on a transparent background: give them a solid
	# backdrop in a dark shade of the speaker's colour.
	var backdrop := Color(0.0, 0.02, 0.04, 0.65)
	if _portrait.texture:
		backdrop = Color(color.darkened(portrait_backdrop_darken), 0.95)
	(_portrait_frame.get_theme_stylebox("panel") as StyleBoxFlat).bg_color = backdrop
	_name.text = line.speaker.display_name.to_upper() if line.speaker else ""
	_name.add_theme_color_override("font_color", color)
	_static_material.set_shader_parameter("tint", color)
	_text.text = line.text
	_text.visible_characters = 0
	_voice.stop()
	_voice_left = 0.0


## The box is open: type the line out (and start its recording, if any).
func _begin_typing() -> void:
	_phase = Phase.TYPING
	_next_char_in = 0.0
	if _line.voice:
		_voice.stream = _line.voice
		_voice.play()
		_voice_left = _line.voice.get_length()


func _open_total() -> float:
	return expand_time + noise_time + unfold_time


func _process(delta: float) -> void:
	_voice_left -= delta
	_static_time += delta
	match _phase:
		Phase.OPENING:
			_open_t = minf(_open_t + delta, _open_total())
			if _open_t >= _open_total():
				_begin_typing()
		Phase.SWITCHING:
			_switch_left -= delta
			if _switch_left <= 0.0:
				_begin_typing()
		Phase.TYPING:
			_next_char_in -= delta
			while _phase == Phase.TYPING and _next_char_in <= 0.0:
				_reveal_next()
		Phase.HOLDING:
			_hold_left -= delta
			if _hold_left <= 0.0 and _voice_left <= 0.0:
				_phase = Phase.CLOSING
		Phase.CLOSING:
			_open_t = maxf(_open_t - delta, 0.0)
			if not _queue.is_empty() and _open_t <= expand_time:
				# Back to static: bring in the next line from here.
				_set_content(_queue.pop_front())
				_phase = Phase.OPENING
			elif _open_t <= 0.0:
				_phase = Phase.IDLE
				_panel.hide()
	if _phase != Phase.IDLE:
		_apply_open()


## Lays the box out for the current point on the opening timeline (the same
## function serves closing, run backwards):
##   0 .. expand_time               square grows from a line to full height
##   .. + noise_time                square shows static
##   .. + unfold_time               portrait and name shown, text box unfolds
func _apply_open() -> void:
	var expand := _segment(0.0, expand_time)
	var unfold := _segment(expand_time + noise_time, unfold_time)
	# Closing isn't quite opening in reverse: the portrait cuts to static as
	# soon as the text box starts folding, not once it has folded away.
	var portrait_on := _open_t >= expand_time + noise_time and _phase != Phase.CLOSING

	var h := lerpf(line_height, PORTRAIT_SIZE, _smooth(expand))
	_portrait_frame.size.y = h
	_portrait_frame.position.y = (PORTRAIT_SIZE - h) * 0.5

	var showing_portrait := portrait_on and _phase != Phase.SWITCHING
	_portrait.visible = showing_portrait
	_name.visible = portrait_on
	var strength := 0.0
	if _open_t > expand_time and not showing_portrait:
		strength = 1.0
	elif showing_portrait and _portrait.texture == null:
		strength = empty_portrait_static
	_static.visible = strength > 0.0
	if _static.visible:
		_static_material.set_shader_parameter("strength", strength)
		_static_material.set_shader_parameter("time", _static_time)

	_box.visible = unfold > 0.0
	_box.size.x = BOX_WIDTH * (1.0 - (1.0 - unfold) * (1.0 - unfold))  # ease out


## Progress (0..1) of `_open_t` through a segment starting at `from`.
func _segment(from: float, length: float) -> float:
	if length <= 0.0:
		return 1.0 if _open_t >= from else 0.0
	return clampf((_open_t - from) / length, 0.0, 1.0)


static func _smooth(x: float) -> float:
	return x * x * (3.0 - 2.0 * x)


func _reveal_next() -> void:
	var c := _line.text[_shown]
	_shown += 1
	_text.visible_characters = _shown
	var is_letter := c.to_upper() != c.to_lower() or c.is_valid_int()
	if is_letter and _line.voice == null:
		if _letters % maxi(beep_every, 1) == 0:
			_beep.pitch_scale = (_line.speaker.beep_pitch if _line.speaker else 1.0) * randf_range(0.97, 1.03)
			_beep.play()
		_letters += 1
	_next_char_in += 1.0 / chars_per_second
	var at_end := _shown >= _line.text.length()
	if not at_end:
		if c in ".!?":
			_next_char_in += sentence_pause
		elif c in ",;:":
			_next_char_in += comma_pause
	else:
		_phase = Phase.HOLDING
		_hold_left = hold_time + hold_per_char * _line.text.length()


#region Building

func _build() -> void:
	var font_size := 17
	_panel = Control.new()
	_panel.name = "Panel"
	_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_panel.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	var height := PORTRAIT_SIZE + NAME_HEIGHT
	_panel.offset_left = MARGIN
	_panel.offset_right = MARGIN + PORTRAIT_SIZE + GAP + BOX_WIDTH
	_panel.offset_top = -MARGIN - height
	_panel.offset_bottom = -MARGIN
	add_child(_panel)

	_portrait_frame = _make_panel(Rect2(0.0, 0.0, PORTRAIT_SIZE, PORTRAIT_SIZE))
	_portrait = TextureRect.new()
	_portrait.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_portrait.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	_portrait.position = Vector2(2.0, 2.0)
	_portrait.size = Vector2.ONE * (PORTRAIT_SIZE - 4.0)
	_portrait.mouse_filter = Control.MOUSE_FILTER_IGNORE
	# Portraits are 256 px, shown at about a third of that: sample mipmaps.
	_portrait.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	_portrait_frame.add_child(_portrait)
	# The square changes height while opening and closing: clip what's inside.
	_portrait_frame.clip_contents = true

	_static = ColorRect.new()
	_static.position = _portrait.position
	_static.size = _portrait.size
	_static.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_static_material = ShaderMaterial.new()
	_static_material.shader = STATIC_SHADER
	_static.material = _static_material
	_portrait_frame.add_child(_static)

	_name = Label.new()
	_name.position = Vector2(0.0, PORTRAIT_SIZE + 2.0)
	_name.size = Vector2(PORTRAIT_SIZE, NAME_HEIGHT)
	_name.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_name.add_theme_font_size_override("font_size", 13)
	_panel.add_child(_name)

	_box = _make_panel(Rect2(PORTRAIT_SIZE + GAP, 0.0, BOX_WIDTH, PORTRAIT_SIZE))
	# The box unfolds by width; the text keeps its full size and is cut off
	# rather than squeezed.
	_box.clip_contents = true
	_text = Label.new()
	_text.position = Vector2(12.0, 9.0)
	_text.size = Vector2(BOX_WIDTH - 24.0, PORTRAIT_SIZE - 18.0)
	_text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	# Wrap the whole line up front so words don't jump lines as they type out.
	_text.visible_characters_behavior = TextServer.VC_CHARS_AFTER_SHAPING
	_text.add_theme_font_size_override("font_size", font_size)
	_text.add_theme_color_override("font_color", Color(1, 1, 1, 0.95))
	_box.add_child(_text)

	_beep = AudioStreamPlayer.new()
	_beep.stream = _make_beep()
	_beep.volume_db = beep_volume_db
	_beep.max_polyphony = 3
	add_child(_beep)
	_voice = AudioStreamPlayer.new()
	_voice.volume_db = voice_volume_db
	add_child(_voice)


func _make_panel(rect: Rect2) -> Panel:
	var panel := Panel.new()
	panel.position = rect.position
	panel.size = rect.size
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.0, 0.02, 0.04, 0.65)
	panel.add_theme_stylebox_override("panel", style)
	_panel.add_child(panel)
	return panel


func _set_border(panel: Panel, color: Color, width: int) -> void:
	var style := panel.get_theme_stylebox("panel") as StyleBoxFlat
	style.border_color = color
	style.set_border_width_all(width)


## A short, soft square-ish blip (no audio files needed). Each speaker plays it
## at their own pitch.
func _make_beep() -> AudioStreamWAV:
	const LENGTH := 0.045
	const FREQUENCY := 740.0
	var count := int(BEEP_RATE * LENGTH)
	var data := PackedByteArray()
	data.resize(count * 2)
	for i in count:
		var t := float(i) / BEEP_RATE
		var phase := fmod(t * FREQUENCY, 1.0)
		# Square wave softened with a sine, with a quick attack and decay.
		var wave := (1.0 if phase < 0.5 else -1.0) * 0.5 + sin(TAU * phase) * 0.5
		var envelope := minf(t / 0.004, 1.0) * clampf((LENGTH - t) / 0.025, 0.0, 1.0)
		data.encode_s16(i * 2, int(wave * envelope * 0.6 * 32767.0))
	var wav := AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = BEEP_RATE
	wav.stereo = false
	wav.data = data
	return wav

#endregion
