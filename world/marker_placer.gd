class_name MarkerPlacer
extends Node
## Moves a level's nodes onto its map's markers (MapMarkers) when the level
## loads, so moving a marker in Blender and re-exporting moves the start, the
## falls or the Great Fox without editing the scene. It places them in its own
## _ready(), so in the scene tree it must come after the wingmen (who join
## their group in their _ready()) and before nodes that build themselves where
## they stand in theirs (the Waterfall reads the ground under its foot). The
## intro reads its markers later, when the level starts it.

@export var markers: MapMarkers
## Marker name: the node placed on it (its whole transform).
@export var targets: Dictionary[String, NodePath] = {}
## Marker the wingmen start at, each at its formation slot (Wingman.slot_offset)
## from it. Empty: leave them where the scene puts them.
@export var wingmen_marker := "Start"


func _ready() -> void:
	if markers == null:
		return
	for marker: String in targets:
		var node := get_node_or_null(targets[marker]) as Node3D
		if node == null:
			push_warning("MarkerPlacer: no node at %s" % targets[marker])
		elif not markers.has_marker(marker):
			push_warning("MarkerPlacer: the map has no marker %s" % marker)
		else:
			node.global_transform = markers.get_marker(marker)
	if wingmen_marker != "" and markers.has_marker(wingmen_marker):
		var start := markers.get_marker(wingmen_marker)
		for wingman: Wingman in get_tree().get_nodes_in_group("wingmen"):
			wingman.global_transform = Transform3D(start.basis, start * wingman.slot_offset)
