class_name PropLayout
extends Resource
## Where a map's kit pieces stand: one entry per placed piece. Written by a
## Blender build script (models/corneria/source/build_corneria.py exports
## models/corneria/corneria_layout.tres) and drawn by MapProps as MultiMesh
## instances of the meshes in the map's kit scene (corneria_kit.glb), so the
## same tower placed 300 times is stored once.

## Kit mesh names (node names in the kit scene), indexed by `piece`.
@export var pieces := PackedStringArray()
## Prop group names (City, Trees...), indexed by `group`: what MapProps decides
## collision and draw distance by.
@export var groups := PackedStringArray()
## Per placed piece: its index in `pieces`.
@export var piece := PackedInt32Array()
## Per placed piece: its index in `groups`.
@export var group := PackedInt32Array()
## Per placed piece, 12 floats: its basis's x, y and z columns, then its origin
## (game coordinates; the basis may be scaled unevenly).
@export var transforms := PackedFloat32Array()


## How many pieces are placed.
func count() -> int:
	return piece.size()


## Placed piece `k`'s transform.
func transform_of(k: int) -> Transform3D:
	var t := transforms.slice(k * 12, k * 12 + 12)
	return Transform3D(Vector3(t[0], t[1], t[2]), Vector3(t[3], t[4], t[5]),
			Vector3(t[6], t[7], t[8]), Vector3(t[9], t[10], t[11]))
