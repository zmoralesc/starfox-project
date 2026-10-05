class_name SoundFX
extends AudioStreamPlayer3D
## A one-shot sound at a position that removes itself when it finishes.
## For sounds that must outlive whatever made them, like a ship that's freed
## the moment it explodes.

## Seconds before the player removes itself even if `finished` never fires
## (e.g. no audio device), on top of the sound's own length.
const CLEANUP_MARGIN := 1.0


## `size` and `reach`: unit_size and max_distance (AudioStreamPlayer3D). The defaults suit
## explosions: they carry, heard well across the fight, silent past 1200 m.
static func play_at(parent: Node, stream: AudioStream, at: Vector3, volume_db := 0.0,
		pitch := 1.0, size := 25.0, reach := 1200.0) -> void:
	if stream == null or parent == null:
		return
	var player := SoundFX.new()
	player.stream = stream
	player.volume_db = volume_db
	player.pitch_scale = pitch
	player.unit_size = size
	player.max_distance = reach
	parent.add_child(player)
	player.global_position = at
	player.finished.connect(player.queue_free)
	player.play()
	player.get_tree().create_timer(stream.get_length() / pitch + CLEANUP_MARGIN, false) \
		.timeout.connect(player.queue_free)
