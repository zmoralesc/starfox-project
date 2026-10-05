shader_type spatial;

// toon.gdshader with a clip plane: parts of the mesh behind `clip_plane` (an
// instance uniform, set per mesh with set_instance_shader_parameter) aren't
// drawn. Used by the destroyer while it comes out of its warp portal, so the
// hull still "inside" the portal stays hidden from every angle. A separate
// shader so the discard costs nothing on every other toon surface.

#define TOON_CLIP
#include "res://effects/toon_surface.gdshaderinc"
