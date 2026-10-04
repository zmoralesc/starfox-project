class_name LevelMusic
extends Resource
## A level's soundtrack: an optional lead that plays once, then a loop that
## repeats forever. Played by the Music autoload (audio/music.gd); a level
## picks its track with Level.music.
##
## The switch from lead to loop is sample-accurate (built on
## AudioStreamInteractive), so there's no gap between them. Either part can
## be Ogg Vorbis, MP3 or WAV. The loop repeats from its start, or from the
## loop offset set in its import options; the lead never loops, whatever its
## import options say.

## Plays once at the start. Leave empty to start straight on the loop.
@export var lead: AudioStream
## Repeats forever after the lead.
@export var loop: AudioStream
## Volume of this track, on top of the Music bus.
@export_range(-40.0, 12.0, 0.5, "suffix:dB") var volume_db := 0.0


## The stream to play: the loop alone, or lead then loop as an
## AudioStreamInteractive whose lead auto-advances into the loop.
func build_stream() -> AudioStream:
	if loop == null:
		return null
	var looped := _with_loop(loop, true)
	if lead == null:
		return looped
	var stream := AudioStreamInteractive.new()
	stream.clip_count = 2
	stream.set_clip_name(0, &"lead")
	stream.set_clip_stream(0, _with_loop(lead, false))
	stream.set_clip_auto_advance(0, AudioStreamInteractive.AUTO_ADVANCE_ENABLED)
	stream.set_clip_auto_advance_next_clip(0, 1)
	stream.set_clip_name(1, &"loop")
	stream.set_clip_stream(1, looped)
	stream.initial_clip = 0
	return stream


## A copy of `stream` that loops (or doesn't). Copied so the imported file's
## own settings stay as they are for anything else that uses it.
static func _with_loop(stream: AudioStream, looping: bool) -> AudioStream:
	if stream is AudioStreamWAV:
		var wav := stream.duplicate() as AudioStreamWAV
		if not looping:
			wav.loop_mode = AudioStreamWAV.LOOP_DISABLED
		elif wav.loop_mode == AudioStreamWAV.LOOP_DISABLED:
			# Not set up to loop on import: loop the whole file.
			var frame_bytes := (2 if wav.format == AudioStreamWAV.FORMAT_16_BITS else 1) * (2 if wav.stereo else 1)
			if wav.format == AudioStreamWAV.FORMAT_8_BITS or wav.format == AudioStreamWAV.FORMAT_16_BITS:
				wav.loop_mode = AudioStreamWAV.LOOP_FORWARD
				wav.loop_begin = 0
				wav.loop_end = wav.data.size() / frame_bytes
			else:
				push_warning("LevelMusic: turn on Loop in the import options of %s (compressed WAV)." % stream.resource_path)
		return wav
	if "loop" in stream:  # Ogg Vorbis, MP3
		var copy := stream.duplicate()
		copy.set("loop", looping)
		return copy
	return stream
