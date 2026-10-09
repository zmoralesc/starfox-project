shader_type spatial;
render_mode depth_draw_always;

// toon_unlined.gdshader for MultiMesh instances (see toon_instanced.gdshader):
// the map's instanced foliage, its faceted cones and lumps shaded round
// (TOON_FOLIAGE, foliage_round).

#define TOON_UNLINED
#define TOON_INSTANCED
#define TOON_FOLIAGE
#include "res://effects/toon_surface.gdshaderinc"
