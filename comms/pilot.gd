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
## Lines this pilot may say after shooting down an enemy fighter...
@export_multiline var celebrations: PackedStringArray = []
## ...with this chance per kill (never while on Form Up).
@export_range(0.0, 1.0) var celebration_chance := 0.25
## Lines this pilot may say when the player shoots down an enemy fighter, with
## the same celebration_chance per kill (one random wingman is asked).
@export_multiline var praise: PackedStringArray = []
## Lines this pilot may say instead when a kill was teamwork: you finished off
## an enemy fighter this pilot had just hit, or the other way round
## (WingCommand.teamwork_window)...
@export_multiline var teamwork: PackedStringArray = []
## ...with this chance per such kill (any order, Form Up included).
@export_range(0.0, 1.0) var teamwork_chance := 0.3
## Lines said when breaking away from an enemy on their tail (Wingman evasion).
@export_multiline var under_fire: PackedStringArray = []
## Lines confirming an order that has to wait until they've shaken their
## pursuer (said in place of an acknowledgement).
@export_multiline var order_queued: PackedStringArray = []
## Lines said when their shields fail and they pull out of the fight.
@export_multiline var disengaging: PackedStringArray = []
## Lines said when their shields are back and they rejoin.
@export_multiline var back_online: PackedStringArray = []
