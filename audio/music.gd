extends Node
## Autoload (Music) that plays the current LevelMusic on the Music bus.
##
## It lives outside the level, so a track keeps playing when the level
## restarts after a death (Level asks for the same track again, and the same
## track just carries on, without its lead starting over). Asking for a
## different track fades the old one out while the new one starts; asking for
## none (the title screen, for now) fades out. While the game is paused the
## music is turned down.

## Seconds to fade out a track that's being replaced or stopped.
@export var fade_time := 1.0
## How much quieter the music is while the game is paused.
@export var pause_duck_db := -8.0
## How fast the pause ducking follows (per second; higher = quicker).
@export var duck_sharpness := 6.0

const BUS := &"Music"

## The track playing now (null when silent).
var current: LevelMusic

var _player: AudioStreamPlayer
var _duck_db := 0.0


func _ready() -> void:
	# Keep playing (and fading) while the game is paused.
	process_mode = Node.PROCESS_MODE_ALWAYS


## Plays `music`, unless it's already playing. null fades out to silence.
func play(music: LevelMusic) -> void:
	if _same_track(music, current):
		return
	_fade_out()
	current = music
	var stream := music.build_stream() if music else null
	if stream == null:
		return
	_player = AudioStreamPlayer.new()
	_player.name = "Track"
	_player.stream = stream
	_player.bus = BUS if AudioServer.get_bus_index(BUS) >= 0 else &"Master"
	_player.volume_db = music.volume_db + _duck_db
	add_child(_player)
	_player.play()


## Fades out whatever is playing.
func stop() -> void:
	play(null)


func _process(delta: float) -> void:
	var paused := get_tree().paused
	_duck_db = lerpf(_duck_db, pause_duck_db if paused else 0.0, 1.0 - exp(-duck_sharpness * delta))
	if _player and current:
		_player.volume_db = current.volume_db + _duck_db


## Same resource, or the same file loaded again (a reloaded scene may hand
## over a fresh copy of the track).
static func _same_track(a: LevelMusic, b: LevelMusic) -> bool:
	if a == b:
		return true
	return a != null and b != null and a.resource_path != "" and a.resource_path == b.resource_path


func _fade_out() -> void:
	if _player == null:
		return
	var old := _player
	_player = null
	var tween := create_tween()
	tween.tween_property(old, "volume_db", -60.0, fade_time)
	tween.tween_callback(old.queue_free)
