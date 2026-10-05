shader_type spatial;
render_mode cull_disabled;

// One puff of an explosion (Explosion, on GPUParticles3D quads): a camera-
// facing ball that starts as fire in hard bands (white-hot core, orange, deep
// red rim), cools from the edge inwards into smoke over its life, then breaks
// up into holes and is gone. The smoke is toon-lit like everything else (the
// puff's NORMAL is a sphere's), and it's opaque with a ragged cut-out edge, so
// it gets ink outlines: the cartoon explosion look.
//
// The puff's age comes from the particle system (INSTANCE_CUSTOM.y, 0 to 1
// over its life).

uniform vec4 hot_color : source_color = vec4(1.0, 0.96, 0.7, 1.0);
uniform vec4 fire_color : source_color = vec4(1.0, 0.62, 0.15, 1.0);
uniform vec4 ember_color : source_color = vec4(0.85, 0.22, 0.06, 1.0);
uniform vec4 smoke_color : source_color = vec4(0.17, 0.16, 0.16, 1.0);
// How brightly the fire glows.
uniform float glow = 3.0;
// Fraction of its life after which the puff is all smoke. Tiny = smoke from the start.
uniform float cool_at = 0.5;
// Fraction of its life after which it starts breaking up.
uniform float dissolve_from = 0.55;
// How lumpy the outline is (fraction of the radius).
uniform float lumpiness = 0.22;

#include "res://effects/toon_light.gdshaderinc"

varying float v_age;
varying float v_seed;

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
}

// Hard edge, blended over about one pixel.
float step_aa(float edge, float x) {
	float w = max(fwidth(x), 0.001);
	return smoothstep(edge - w, edge + w, x);
}

void fragment() {
	vec2 p = vec2(UV.x * 2.0 - 1.0, 1.0 - UV.y * 2.0);
	float r = length(p);
	vec2 seed = vec2(v_seed, v_seed * 1.7);

	// Lumpy outline: the radius wobbles with the direction.
	float lumps = noise(normalize(p + 1e-4) * 2.2 + seed) - 0.5;
	float edge = 1.0 - lumpiness * 0.5 + lumps * lumpiness;
	if (r > edge) {
		discard;
	}
	// Breaking up: growing holes, then nothing.
	float breakup = clamp((v_age - dissolve_from) / max(1.0 - dissolve_from, 1e-3), 0.0, 1.0);
	if (breakup > 0.0 && noise(p * 2.5 + seed * 3.0) * 0.9 + 0.1 * (1.0 - r) < breakup) {
		discard;
	}

	float rr = clamp(r / edge, 0.0, 1.0);
	vec3 n = vec3(p / max(edge, 1e-3), sqrt(max(1.0 - rr * rr, 0.0)));
	NORMAL = normalize(n);

	// Heat: hottest in the middle and early on, cooling from the rim inwards.
	float cool = clamp(v_age / max(cool_at, 1e-3), 0.0, 1.0);
	float heat = (1.0 - cool) * (0.45 + 0.55 * n.z) + (noise(p * 3.0 + seed) - 0.5) * 0.2 * (1.0 - cool);
	vec3 fire = mix(ember_color.rgb, fire_color.rgb, step_aa(0.45, heat));
	fire = mix(fire, hot_color.rgb, step_aa(0.72, heat));
	float burning = step_aa(0.18, heat);

	ALBEDO = smoke_color.rgb * (1.0 - burning);
	EMISSION = fire * glow * burning;
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
}
