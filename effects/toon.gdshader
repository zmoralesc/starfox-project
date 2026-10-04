shader_type spatial;

// Cel shading for every lit surface: one flat colour (`albedo`) per material,
// optionally multiplied by a colour texture and with a glow map, for imported
// textured models (see ToonMaterial.from_material()). Both textures default to
// "no effect" (white albedo, black emission), so flat-colour materials look
// exactly as before. The light model (bands, glint, rim) is in
// toon_light.gdshaderinc, shared with toon_vertex.gdshader. Outlines are drawn
// separately by InkOutline (effects/ink_outline.gd).

uniform vec4 albedo : source_color = vec4(0.8, 0.8, 0.8, 1.0);
// Multiplied with `albedo`. White (no change) when unset.
uniform sampler2D albedo_texture : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
// Glow, added on top of the lighting: emission colour × emission texture × energy.
uniform vec4 emission : source_color = vec4(0.0, 0.0, 0.0, 1.0);
uniform sampler2D emission_texture : source_color, hint_default_black, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float emission_energy : hint_range(0.0, 16.0) = 1.0;

#include "res://effects/toon_light.gdshaderinc"

void fragment() {
	ALBEDO = albedo.rgb * texture(albedo_texture, UV).rgb;
	EMISSION = emission.rgb * texture(emission_texture, UV).rgb * emission_energy;
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
}
