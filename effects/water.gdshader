shader_type spatial;

// Stylised lake water: a flat toon-lit colour with soft bands of lighter
// shimmer drifting across it. Opaque on purpose: shorelines then get ink
// outlines like everything else.

uniform vec4 water_color : source_color = vec4(0.16, 0.42, 0.72, 1.0);
uniform vec4 shimmer_color : source_color = vec4(0.5, 0.78, 0.98, 1.0);
// Rough size of a shimmer band, in metres.
uniform float shimmer_scale = 60.0;
uniform float shimmer_speed = 0.25;
// How much of the surface shimmers (0 = none).
uniform float shimmer_amount : hint_range(0.0, 1.0) = 0.35;

#include "res://effects/toon_light.gdshaderinc"

void fragment() {
	vec3 world = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec2 p = world.xz / shimmer_scale;
	float wave = sin(p.x * 1.7 + TIME * shimmer_speed) * sin(p.y * 1.3 - TIME * shimmer_speed * 0.8)
		+ 0.5 * sin((p.x + p.y) * 2.9 + TIME * shimmer_speed * 1.6);
	// Hard-edged bands, anti-aliased like the toon light bands.
	float w = max(fwidth(wave), 0.002);
	float band_mask = smoothstep(1.0 - shimmer_amount - w, 1.0 - shimmer_amount + w, wave * 0.67);
	ALBEDO = mix(water_color.rgb, shimmer_color.rgb, band_mask);
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
}
