shader_type spatial;
render_mode cull_disabled, depth_draw_always;

// A puff of dust kicked up by a hit (HitBurst's dust, on GPUParticles3D
// quads), drawn the way 2D effects animation draws dust: a cloud of a few
// overlapping round lobes with crisp edges, each toon-lit as a ball so it
// gets a flat body tone and one shadow crescent. The lobes swell apart early
// on, then each shrinks away in its own time, so the cloud falls apart into
// small discs and is gone: it goes by shrinking, never by fading.
// No ink outlines: writing ALPHA puts it in the transparent pass, out of the
// depth texture InkOutline reads; depth_draw_always still writes depth so
// puffs sort with the ground and each other.
//
// The puff's age comes from the particle system (INSTANCE_CUSTOM.y, 0 to 1
// over its life); its scale is the cloud's full width.

uniform vec4 dust_color : source_color = vec4(0.84, 0.75, 0.58, 1.0);
// Lobes in the cloud (up to 6), their radius (fraction of the quad's half
// width) and how far from the middle they sit (fraction).
uniform float lobes = 4.0;
uniform float lobe_radius = 0.42;
uniform float lobe_spread = 0.45;
// Fraction of the life over which the lobes swell out to full size, and the
// fraction from which they start shrinking away (each in its own time,
// spread over `shrink_stagger` of the life).
uniform float swell = 0.25;
uniform float shrink_from = 0.5;
uniform float shrink_stagger = 0.3;

// Drawn-looking effect: keep the hard bands (see toon_light.gdshaderinc).
#define TOON_HARD
#include "res://effects/toon_light.gdshaderinc"

varying float v_age;
varying float v_seed;

// Integer hash (a float hash breaks at large seeds, see water.gdshader).
float hash(vec2 p) {
	uvec2 q = uvec2(ivec2(floor(p + 0.5)));
	q = q * uvec2(1597334673u, 3812015801u);
	uint n = (q.x ^ q.y) * 1597334673u;
	n ^= n >> 16u;
	return float(n) * (1.0 / 4294967295.0);
}

void vertex() {
	// Face the camera, keeping the particle's position and scale (what
	// BILLBOARD_PARTICLES does in StandardMaterial3D).
	mat4 world = mat4(normalize(INV_VIEW_MATRIX[0]), normalize(INV_VIEW_MATRIX[1]),
		normalize(INV_VIEW_MATRIX[2]), MODEL_MATRIX[3]);
	world = world * mat4(vec4(length(MODEL_MATRIX[0].xyz), 0.0, 0.0, 0.0),
		vec4(0.0, length(MODEL_MATRIX[1].xyz), 0.0, 0.0),
		vec4(0.0, 0.0, length(MODEL_MATRIX[2].xyz), 0.0), vec4(0.0, 0.0, 0.0, 1.0));
	MODELVIEW_MATRIX = VIEW_MATRIX * world;
	MODELVIEW_NORMAL_MATRIX = mat3(MODELVIEW_MATRIX);
	v_age = INSTANCE_CUSTOM.y;
	v_seed = float(INSTANCE_ID) * 7.31;
}

void fragment() {
	vec2 p = vec2(UV.x * 2.0 - 1.0, 1.0 - UV.y * 2.0);
	float grow = smoothstep(0.0, max(swell, 1e-3), v_age);
	// The lobe this pixel belongs to: the one it is deepest inside (its
	// normalised distance the smallest), so overlaps shade as one ball each.
	float best = 10.0;
	vec2 best_n = vec2(0.0);
	float best_r = 1.0;
	for (int i = 0; i < 6; i++) {
		if (float(i) >= lobes) {
			break;
		}
		vec2 s = vec2(v_seed + float(i) * 3.7, float(i) * 1.3);
		float angle = hash(s) * 6.2831853;
		float dist = lobe_spread * mix(0.3, 1.0, hash(s + 11.0)) * mix(0.4, 1.0, grow);
		vec2 centre = vec2(cos(angle), sin(angle)) * dist;
		// Each lobe shrinks away in its own time once the cloud starts to go.
		float go = shrink_from + hash(s + 23.0) * shrink_stagger;
		float shrink = 1.0 - smoothstep(go, min(go + shrink_stagger, 1.0), v_age);
		float radius = lobe_radius * mix(0.7, 1.0, hash(s + 37.0)) * mix(0.5, 1.0, grow) * shrink;
		vec2 d = p - centre;
		float nd = length(d) / max(radius, 1e-4);
		if (nd < best) {
			best = nd;
			best_n = d / max(radius, 1e-4);
			best_r = radius;
		}
	}
	// Crisp edge, blended over about a pixel.
	float w = max(fwidth(best), 0.001);
	if (best > 1.0 + w) {
		discard;
	}
	ALBEDO = dust_color.rgb;
	// The lobe lit as a ball: the toon bands give it a flat body tone and one
	// shadow crescent.
	float rr = clamp(best, 0.0, 1.0);
	NORMAL = normalize(vec3(best_n, sqrt(max(1.0 - rr * rr, 0.0))));
	// Transparent pass, so no ink outlines (ALPHA stays 1).
	ALPHA *= 1.0;
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
}
