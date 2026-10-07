// Shared cel-shading light model, included by toon_surface.gdshaderinc (so
// toon, toon_clip and toon_unlined), terrain.gdshader, the explosion puffs and the
// water splash and spray. Light falls into hard bands (lit / mid / shadow)
// instead of a smooth gradient, highlights are a hard-edged glint and a thin
// rim of light picks out the silhouette on the lit side. Ambient light (from
// the environment) fills the shadow band with a flat tone.

// Brightness of the shadow band, as a fraction of fully lit. Keeps shadowed
// sides reading as a darker shade of their colour instead of going black.
uniform float shadow_tone : hint_range(0.0, 1.0) = 0.2;
// Brightness of the middle band, as a fraction of fully lit.
uniform float mid_tone : hint_range(0.0, 1.0) = 0.5;
// Where the bands split, on the N·L (times shadow) scale.
uniform float mid_threshold : hint_range(0.0, 1.0) = 0.08;
uniform float lit_threshold : hint_range(0.0, 1.0) = 0.45;
// Hard specular glint. 0 turns it off.
uniform float glint : hint_range(0.0, 2.0) = 0.35;
// Higher = smaller glint.
uniform float glint_size : hint_range(4.0, 256.0) = 48.0;
// Thin light rim on the lit side of the silhouette.
uniform float rim : hint_range(0.0, 1.0) = 0.25;

// Anti-aliased step: hard edge, but blended over about one pixel.
float band(float edge, float x) {
	float w = max(fwidth(x), 0.002);
	return smoothstep(edge - w, edge + w, x);
}

void light() {
	float ndl = clamp(dot(NORMAL, LIGHT), 0.0, 1.0) * ATTENUATION;
	// The shadow floor is for the sun only: omni/spot lights must fade to
	// nothing outside their range.
	float floor_tone = LIGHT_IS_DIRECTIONAL ? shadow_tone : 0.0;
	float tone = mix(floor_tone, mid_tone, band(mid_threshold, ndl));
	tone = mix(tone, 1.0, band(lit_threshold, ndl));
	DIFFUSE_LIGHT += tone * LIGHT_COLOR / PI;

	float facing = 1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0);
	DIFFUSE_LIGHT += rim * band(0.72, facing) * band(mid_threshold, ndl) * LIGHT_COLOR / PI;

	float h = pow(clamp(dot(NORMAL, normalize(LIGHT + VIEW)), 0.0, 1.0), glint_size);
	SPECULAR_LIGHT += glint * band(0.5, h) * ATTENUATION * LIGHT_COLOR / PI;
}
