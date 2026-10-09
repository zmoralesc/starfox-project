class_name MapMarkers
extends Resource
## Named places on a map, exported from its Blender master copy (the Markers
## empties in models/corneria2/source/corneria.blend, written by
## export_corneria.py as models/corneria2/corneria_markers.tres): where the
## player starts, the intro's points, the waterfall, the Great Fox. A
## MarkerPlacer in the level moves nodes onto them.

## Marker name: its transform (game coordinates, unscaled).
@export var markers: Dictionary = {}


func has_marker(marker: String) -> bool:
	return markers.has(marker)


## Marker `marker`'s transform (identity if there's none).
func get_marker(marker: String) -> Transform3D:
	return markers.get(marker, Transform3D.IDENTITY)
