shader_type spatial;

// toon.gdshader with worn paint: the colour wears through to bare metal in
// ragged noise patches (TOON_WEAR in toon_surface.gdshaderinc). Used for the
// Juggernaut's crimson markings (Destroyer.worn_paint). It includes the clip
// plane too, so it hides inside the warp portal like the toon_clip copies
// (Destroyer._use_clip_shader() only swaps plain toon materials); the clip
// is off (all zero) everywhere else.

#define TOON_CLIP
#define TOON_WEAR
#include "res://effects/toon_surface.gdshaderinc"
