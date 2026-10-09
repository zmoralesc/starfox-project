shader_type spatial;
render_mode cull_disabled, depth_draw_always;

// One puff of an explosion (Explosion, on GPUParticles3D quads): a camera-
// facing ball of billows that starts as fire (white-hot core, orange, deep
// red rim, in tongues), cools from the edge inwards into smoke over its life,
// then erodes from its edge into wisps and is gone. The smoke is toon-lit in
// hard bands, its NORMAL a sphere's bent by the billows, so the shadows
// follow each lump like painted smoke; next to the fire it glows warm.
// No ink outlines: writing ALPHA puts it in the transparent pass, out of the
// depth texture InkOutline reads. depth_draw_always still writes depth so puffs
// sort and occlude properly.
//
// The puff's age comes from the particle system (INSTANCE_CUSTOM.y, 0 to 1
// over its life).
//
// Near the camera, a puff breaks up the same way (near_fade), so a trail the
// camera follows (the player's wreck) doesn't fill the screen.

uniform vec4 hot_color : source_color = vec4(1.0, 0.96, 0.7, 1.0);
uniform vec4 fire_color : source_color = vec4(1.0, 0.62, 0.15, 1.0);
uniform vec4 ember_color : source_color = vec4(0.85, 0.22, 0.06, 1.0);
uniform vec4 smoke_color : source_color = vec4(0.36, 0.36, 0.39, 1.0);
// How brightly the fire glows.
uniform float glow = 3.0;
// Fraction of its life after which the puff is all smoke. Tiny = smoke from the start.
uniform float cool_at = 0.5;
// Fraction of its life after which it starts breaking up.
uniform float dissolve_from = 0.55;
// How lumpy the outline is (fraction of the radius).
uniform float lumpiness = 0.22;
// Billows: their size (higher = smaller lumps) and how much they bend the
// light (0 = a plain ball).
uniform float billow_scale = 1.4;
uniform float billow_depth = 0.45;
// Near-camera break-up, by the distance from the camera to the puff's edge
// (metres): all gone closer than x, whole from y on. y <= x = off.
uniform vec2 near_fade = vec2(0.0);

// Drawn-looking effect: keep the hard bands (see toon_light.gdshaderinc).
#define TOON_HARD
#include "res://effects/toon_light.gdshaderinc"

varying float v_age;
varying float v_seed;
// 0 = whole, 1 = gone: how far near_fade has broken this puff up.
varying float v_near;

// Integer hash for a grid corner (see water.gdshader: a float hash loses
// precision at large inputs, like the per-puff seed offsets, and breaks the
// noise into seams).
float hash(vec2 p) {
	uvec2 q = uvec2(ivec2(floor(p + 0.5)));
	q = q * uvec2(1597334673u, 3812015801u);
	uint n = (q.x ^ q.y) * 1597334673u;
	n ^= n >> 16u;
	return float(n) * (1.0 / 4294967295.0);
}

float noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
		mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
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
	// The quad is 1 m across before scaling, so the puff's radius is half its scale.
	float edge_distance = length(MODELVIEW_MATRIX[3].xyz) - length(MODEL_MATRIX[0].xyz) * 0.5;
	v_near = near_fade.y > near_fade.x
		? 1.0 - smoothstep(near_fade.x, near_fade.y, edge_distance) : 0.0;
}

// Hard edge, blended over about one pixel.
float step_aa(float edge, float x) {
	float w = max(fwidth(x), 0.001);
	return smoothstep(edge - w, edge + w, x);
}

// The billows' height over the puff (0 to about 1): two octaves of noise that
// drift slowly as the puff ages, so the lumps roll.
float billows(vec2 p, vec2 seed, float age) {
	vec2 q = p * billow_scale + seed + vec2(0.0, age * 0.6);
	return noise(q) * 0.8 + noise(q * 2.3 + 4.7) * 0.2;
}

void fragment() {
	vec2 p = vec2(UV.x * 2.0 - 1.0, 1.0 - UV.y * 2.0);
	float r = length(p);
	vec2 seed = vec2(v_seed, v_seed * 1.7);

	// Billowy outline: big lumps round the edge, then smaller scallops on
	// them, like painted smoke rather than a wobbly ball.
	vec2 dir = p / max(r, 1e-4);
	float lumps = noise(dir * 2.2 + seed) - 0.5;
	float scallops = noise(dir * 6.5 + seed * 1.3 + v_age) - 0.5;
	float edge = 1.0 - lumpiness * 0.6 + lumps * lumpiness + scallops * lumpiness * 0.5;
	if (r > edge) {
		discard;
	}
	// Breaking up: the puff erodes from its edge inwards into ragged wisps,
	// then is gone (near the camera too, by near_fade).
	float breakup = clamp((v_age - dissolve_from) / max(1.0 - dissolve_from, 1e-3), 0.0, 1.0);
	breakup = max(breakup, v_near);
	if (breakup > 0.0) {
		float body = noise(p * 3.2 + seed * 3.0 + vec2(0.0, v_age)) * 0.65 + (1.0 - r / edge) * 0.35;
		if (body < breakup) {
			discard;
		}
	}

	// Normal: the ball's, bent by the billows' slopes, so light and shadow
	// follow each lump instead of one sphere.
	float rr = clamp(r / edge, 0.0, 1.0);
	vec3 n = vec3(p / max(edge, 1e-3), sqrt(max(1.0 - rr * rr, 0.0)));
	float e = 0.04;
	float h = billows(p, seed, v_age);
	vec2 slope = vec2(billows(p + vec2(e, 0.0), seed, v_age) - h, billows(p + vec2(0.0, e), seed, v_age) - h) / e;
	n.xy -= slope * billow_depth;
	NORMAL = normalize(n);

	// Heat: hottest in the middle and early on, cooling from the rim inwards,
	// in tongues (two octaves of noise) rather than rings.
	float cool = clamp(v_age / max(cool_at, 1e-3), 0.0, 1.0);
	float tongues = noise(p * 3.0 + seed + vec2(0.0, v_age * 2.0)) * 0.6 + noise(p * 7.0 + seed) * 0.4 - 0.5;
	// Centre hot, edge cooler (n.z), tongues and billows breaking the bands up.
	float heat = (1.0 - cool) * (0.3 + 0.75 * n.z * n.z + tongues * 0.35 + (h - 0.5) * 0.2);
	vec3 fire = mix(ember_color.rgb, fire_color.rgb, smoothstep(0.38, 0.52, heat));
	fire = mix(fire, hot_color.rgb, smoothstep(0.68, 0.8, heat));
	float burning = step_aa(0.18, heat);
	// Smoke next to the fire glows with it, from inside.
	float scorch = smoothstep(0.02, 0.18, heat) * (1.0 - burning);

	ALBEDO = smoke_color.rgb * (1.0 - burning);
	EMISSION = fire * glow * burning + ember_color.rgb * glow * 0.35 * scorch;
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
	ALPHA *= 1.0;
}
