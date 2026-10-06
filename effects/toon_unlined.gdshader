shader_type spatial;
render_mode depth_draw_always;

// toon.gdshader without ink outlines: the same solid, lit surface, drawn in the
// transparent pass (it writes ALPHA, left at 1), which InkOutline's depth and
// normal reads don't see; depth_draw_always still writes depth, so it hides
// what's behind it and itself as an opaque surface does. Used for foliage (see
// MapProps.unlined_materials), whose many small cones were a tangle of lines.

#define TOON_UNLINED
#include "res://effects/toon_surface.gdshaderinc"
