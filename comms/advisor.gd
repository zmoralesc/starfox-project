class_name Advisor
extends CommsSpeaker
## A character who doesn't fly but advises the team over the comms from the
## Great Fox (Peppy): everything a CommsSpeaker has plus the tactical lines
## MissionControl has them say. One file per character in comms/speakers/,
## like the pilots, so they sound the same in every mission.
##
## Every list is picked from at random, never the same line twice in a row.

@export_group("Destroyer")
## Said when a destroyer arrives...
@export_multiline var destroyer_warnings: PackedStringArray = []
## ...followed, for the mission's first destroyer, by how to kill one...
@export_multiline var destroyer_hints: PackedStringArray = []
## ...or, for every later one, by a short reminder.
@export_multiline var destroyer_reminders: PackedStringArray = []
## The bridge is down and thrusters remain.
@export_multiline var bridge_down: PackedStringArray = []
## A single thruster is left (whatever the bridge's state).
@export_multiline var last_thruster: PackedStringArray = []
## Every thruster is down and the bridge remains.
@export_multiline var thrusters_down: PackedStringArray = []
## The destroyer has been destroyed.
@export_multiline var destroyer_killed: PackedStringArray = []
