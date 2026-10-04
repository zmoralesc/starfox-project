class_name Pilot
extends CommsSpeaker
## A character who flies: everything a CommsSpeaker has (name, colour,
## portrait, beeps) plus their ship's accent colour and the lines they say in
## battle. One file per character in comms/speakers/, so a character sounds
## the same in every mission. A wingman gets its pilot through its `speaker`
## export (Wingman.pilot); its role in the formation (slot, wing_index,
## break_side) stays on the wingman node.

## Colour of the ship's accent panels; also this pilot's colour on the HUD
## (call sign, chevron, radar dot, wing panel card).
@export var accent_color := Color(0.95, 0.7, 0.15)

@export_group("Lines")
## Lines picked from to confirm an order (never the same one twice in a row).
@export var acknowledgements: PackedStringArray = []
## Said when a destroyer arrives (if this pilot is the one picked to call it).
@export_multiline var destroyer_callout := ""
## Lines this pilot may say after shooting down an enemy fighter...
@export_multiline var celebrations: PackedStringArray = []
## ...with this chance per kill (never while on Form Up).
@export_range(0.0, 1.0) var celebration_chance := 0.25
## Lines this pilot may say when the player shoots down an enemy fighter, with
## the same celebration_chance per kill (one random wingman is asked).
@export_multiline var praise: PackedStringArray = []
