shader_type spatial;

// Cel shading for every lit surface: one flat colour (`albedo`) per material,
// optionally multiplied by a colour texture and with a glow map, for imported
// textured models (see ToonMaterial.from_material()). Both textures default to
// "no effect" (white albedo, black emission), so flat-colour materials look
// exactly as before. The surface is in toon_surface.gdshaderinc (shared with
// toon_clip.gdshader), the light model (bands, glint, rim) in
// toon_light.gdshaderinc, shared with toon_vertex.gdshader. Outlines are drawn
// separately by InkOutline (effects/ink_outline.gd).

#include "res://effects/toon_surface.gdshaderinc"
