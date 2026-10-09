shader_type spatial;

// toon.gdshader for MultiMesh instances that may be scaled unevenly (the map
// props' kit pieces, see MapProps): the same surface, with the instance's
// normals corrected (Godot doesn't, see TOON_INSTANCED in
// toon_surface.gdshaderinc). Not for single meshes: their normals are already
// right, and the correction would turn them again.

#define TOON_INSTANCED
#include "res://effects/toon_surface.gdshaderinc"
