class_name Mission
extends Resource
## One entry in the mission selector (title screen → Start). Add a mission by
## adding a .tres of this type to missions/ and to the title screen's
## `missions` list.

## Shown on the mission's button.
@export var title := ""
## One or two lines shown under the list while the mission is highlighted.
@export_multiline var description := ""
## The mission's level scene (inherits levels/level_base.tscn).
@export_file("*.tscn") var scene_path := ""
