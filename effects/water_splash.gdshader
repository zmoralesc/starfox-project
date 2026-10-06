shader_type spatial;
render_mode cull_disabled, depth_draw_always;

// A water splash (WaterSplash): an open cylinder that the vertex shader
// shapes over the splash's life into a column of water shooting up with a
// jagged, spiky top, opening out as it goes, then falling back and breaking
// up into holes. Toon-lit white, solid, with no ink outlines (drawn in the
// transparent pass like the water itself). WaterSplash draws two with different
// settings: a tall narrow jet and a short wide crown round its foot.
//
// Expects a CylinderMesh of height 1 and radius 1 (centred, so VERTEX.y runs
// -0.5 to 0.5), no caps, with enough rings to bend.

#include "res://effects/toon_light.gdshaderinc"

// Set per splash by WaterSplash: 0 to 1 over its life, and a random seed.
instance uniform float age = 0.0;
instance uniform float seed = 0.0;
// Set per splash for its size: everything (but timing) scales with it.
instance uniform float size = 1.0;

// Height of the top at its highest (metres), and the fraction of the life it
// takes to get there; it falls back over the rest.
uniform float height = 10.0;
uniform float rise = 0.35;
// Radius at the foot (metres), how much wider the top flares (times the foot,
// at full height), and how much wider the whole thing gets by the end.
uniform float radius = 0.8;
uniform float flare = 0.6;
uniform float open_out = 0.8;
// The jagged top: how many spikes round it, and how deep the gaps between
// them cut (fraction of the height).
uniform float spikes = 7.0;
uniform float spike_depth = 0.35;
// Fraction of the life after which holes eat it away (the top first).
uniform float breakup_from = 0.45;
uniform vec4 water_color : source_color = vec4(0.93, 0.97, 1.0, 1.0);

varying float v_along;
// Direction round the column (cos, sin): not the angle, which jumps at the
// seam and would draw a stripe in the holes.
varying vec2 v_dir;

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

// Height of the top over the life: up fast (easing out), then down,
// accelerating, to the water.
float top_height(float t) {
	if (t < rise) {
		float k = t / rise;
		return 1.0 - (1.0 - k) * (1.0 - k);
	}
	float k = (t - rise) / (1.0 - rise);
	return 1.0 - k * k;
}

void vertex() {
	float t = clamp(age, 0.0, 1.0);
	float along = VERTEX.y + 0.5;
	float angle = atan(VERTEX.z, VERTEX.x);
	// Spikes: the top's height varies round the rim (noise wrapped round the
	// circle, so there's no seam), only near the top.
	vec2 ring = vec2(cos(angle), sin(angle)) * spikes / 6.2831853 * 2.0;
	float jag = noise(ring + seed * 17.0);
	float top = height * size * top_height(t) * (1.0 - spike_depth * jag * along * along);
	float r = radius * size * (1.0 + flare * along * along * top_height(t)) * (1.0 + open_out * t);
	VERTEX = vec3(cos(angle) * r, along * top, sin(angle) * r);
	// Outward, tilted by the flare (the side leans out as it rises).
	float lean = radius * size * flare * 2.0 * along * top_height(t) / max(top, 0.01);
	NORMAL = normalize(vec3(cos(angle), -lean, sin(angle)));
	v_along = along;
	v_dir = vec2(cos(angle), sin(angle));
}

void fragment() {
	float t = clamp(age, 0.0, 1.0);
	// Holes: noise round and up the column, eating in from the top as it ages.
	float breakup = clamp((t - breakup_from) / (1.0 - breakup_from), 0.0, 1.0);
	vec2 p = v_dir * 2.5 + vec2(v_along * 4.0 - t * 3.0, v_along * 2.7) + seed * 5.0;
	if (noise(p) + (1.0 - v_along) * 0.35 < breakup * 1.2) {
		discard;
	}
	ALBEDO = water_color.rgb;
	// Transparent pass, so no ink outlines (like the water itself; ALPHA stays 1).
	ALPHA *= 1.0;
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
	// Seen from inside (through the open top), light it as the outside.
	NORMAL = FRONT_FACING ? NORMAL : -NORMAL;
}
