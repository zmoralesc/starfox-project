// Shared cel-shading light model, included by toon_surface.gdshaderinc (so
// toon, toon_clip and toon_unlined), terrain.gdshader, the explosion puffs and the
// water splash and spray. How hard it is comes from the global shader uniform
// `toon_softness` (Project Settings > Shader Globals), so the whole look is one
// dial: at 0, light falls into hard bands (lit / mid / shadow) with a
// hard-edged glint, the Wind Waker end; at 1, a single soft edge between light
// and shadow, a broad highlight and shadows tinted by `toon_shadow_tint`, the
// Breath of the Wild end. A thin rim of light picks out the silhouette on the
// lit side, and `toon_back_rim` lights it on the side away from the sun.
// Ambient light (from the environment) fills the shadow side with a flat tone.
//
// Define TOON_HARD before including to keep the hard bands whatever the global
// says (effects meant to look drawn: explosion puffs, splash, spray), and
// TOON_NO_BACK_RIM to leave the back rim out (the terrain: seen edge-on at the
// horizon, every slope facing away from the sun would light up).

#ifdef TOON_HARD
const float toon_softness = 0.0;
#else
// 0 = hard bands, 1 = one soft edge (Shader Globals).
global uniform float toon_softness;
#endif
// What sunlight is multiplied by on the shadow side (and in cast shadows), so
// shadows go cool instead of just darker. White = no tint (Shader Globals).
global uniform vec4 toon_shadow_tint : source_color;
// Strength of the light rim on the side away from the sun (Shader Globals).
global uniform float toon_back_rim;

// Brightness of the shadow band, as a fraction of fully lit. Keeps shadowed
// sides reading as a darker shade of their colour instead of going black.
uniform float shadow_tone : hint_range(0.0, 1.0) = 0.2;
// Brightness of the middle band, as a fraction of fully lit (hard bands only).
uniform float mid_tone : hint_range(0.0, 1.0) = 0.5;
// Where the bands split, on the N·L (times shadow) scale.
uniform float mid_threshold : hint_range(0.0, 1.0) = 0.08;
uniform float lit_threshold : hint_range(0.0, 1.0) = 0.45;
// Soft edge: N·L over which shadow turns to light, starting at mid_threshold.
uniform float soft_width : hint_range(0.01, 1.0) = 0.3;
// Hard specular glint. 0 turns it off.
uniform float glint : hint_range(0.0, 2.0) = 0.35;
// Higher = smaller glint. Softness spreads it out (to 0.4 of this).
uniform float glint_size : hint_range(4.0, 256.0) = 48.0;
// Thin light rim on the lit side of the silhouette.
uniform float rim : hint_range(0.0, 1.0) = 0.25;

// Anti-aliased step: hard edge, but blended over about one pixel.
float band(float edge, float x) {
	float w = max(fwidth(x), 0.002);
	return smoothstep(edge - w, edge + w, x);
}

// Blend between a hard step and a soft ramp by toon_softness.
float soft_band(float edge, float width, float x) {
	return mix(band(edge, x), smoothstep(edge - width * 0.5, edge + width * 0.5, x), toon_softness);
}

void light() {
	float ndl = clamp(dot(NORMAL, LIGHT), 0.0, 1.0) * ATTENUATION;
	// The shadow floor and tint are for the sun only: omni/spot lights must
	// fade to nothing outside their range.
	float floor_tone = LIGHT_IS_DIRECTIONAL ? shadow_tone : 0.0;

	float hard = mix(floor_tone, mid_tone, band(mid_threshold, ndl));
	hard = mix(hard, 1.0, band(lit_threshold, ndl));
	float soft_lit = smoothstep(mid_threshold, mid_threshold + soft_width, ndl);
	// A gentle rise across the lit side keeps round shapes round.
	float soft = mix(floor_tone, 1.0, soft_lit) * mix(0.85, 1.0, ndl);
	float tone = mix(hard, soft, toon_softness);
	// How lit this is (0 shadow side, 1 lit), for the tint and the rims.
	float lit = mix(band(mid_threshold, ndl), soft_lit, toon_softness);
	vec3 tint = LIGHT_IS_DIRECTIONAL ? mix(toon_shadow_tint.rgb, vec3(1.0), lit) : vec3(1.0);
	DIFFUSE_LIGHT += tone * tint * LIGHT_COLOR / PI;

	float facing = 1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0);
	DIFFUSE_LIGHT += rim * soft_band(0.72, 0.3, facing) * lit * LIGHT_COLOR / PI;
#ifndef TOON_NO_BACK_RIM
	if (LIGHT_IS_DIRECTIONAL) {
		// Strongest when the sun is behind the object, as seen from the camera.
		float behind = clamp(dot(LIGHT, -VIEW), 0.0, 1.0);
		float back = toon_back_rim * soft_band(0.75, 0.3, facing) * (1.0 - lit) * (0.35 + 0.65 * behind);
		// Not times ATTENUATION: the side away from the sun is always in its
		// own shadow, which would hide the rim exactly where it belongs.
		DIFFUSE_LIGHT += back * LIGHT_COLOR / PI;
	}
#endif

	float size = mix(glint_size, glint_size * 0.4, toon_softness);
	float h = pow(clamp(dot(NORMAL, normalize(LIGHT + VIEW)), 0.0, 1.0), size);
	float shine = mix(band(0.5, h), smoothstep(0.15, 0.85, h) * 0.6, toon_softness);
	SPECULAR_LIGHT += glint * shine * ATTENUATION * LIGHT_COLOR / PI;
}
