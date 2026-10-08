class_name CommsSpeaker
extends Resource
## A character who can talk over the comms: name, colour, portrait and voice.

@export var display_name := ""
## Frames the portrait and tints the name.
@export var color := Color(0.45, 1.0, 0.55)
## Shown in the comms portrait square, over a dark backdrop of `color`. Empty
## shows faint static instead.
@export var portrait: Texture2D
## Pitch of this character's text beeps (1 = the base beep).
@export var beep_pitch := 1.0
## Cried out when the player's ship is lost, as its wreck explodes (Level
## picks a random character among the wingmen and the advisor who have any).
@export_multiline var laments: PackedStringArray = []
