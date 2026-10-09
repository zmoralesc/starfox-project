shader_type spatial;
render_mode depth_draw_always;

// toon_unlined.gdshader for MultiMesh instances (see toon_instanced.gdshader):
// the map's instanced foliage.

#define TOON_UNLINED
#define TOON_INSTANCED
#include "res://effects/toon_surface.gdshaderinc"
