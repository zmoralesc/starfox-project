shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, shadows_disabled;

// A bolt's hit on something shootable (HitBurst): a cartoon star burst on a
// quad facing the camera, in hard bands (pale core, yellow, orange rim), that
// pops out to full size and then hollows from the middle and is gone. It steps
// through `frames` poses over its life, like drawn animation, rather than
// moving smoothly. Transparent (it writes ALPHA), so no ink outlines.
//
// Per burst (instance uniforms): `age` 0 to 1 over its life, `seed` for its
// spike pattern. The node's scale is the star's radius in metres.

instance uniform float age = 0.0;
instance uniform float seed = 0.0;

uniform vec4 core_color : source_color = vec4(1.0, 1.0, 0.9, 1.0);
uniform vec4 mid_color : source_color = vec4(1.0, 0.86, 0.22, 1.0);
uniform vec4 rim_color : source_color = vec4(1.0, 0.45, 0.1, 1.0);
// Over 1 makes it bloom; much over and the bloom washes the bands out white.
uniform float brightness = 1.05;
// Spikes round the star, and how much their lengths vary.
uniform float spikes = 8.0;
uniform float spike_variety = 0.45;
// How far in the dips between spikes come (fraction of the radius).
uniform float valley = 0.38;
// Bands: where the core and the yellow end (fractions of the way out).
uniform float core_band = 0.42;
uniform float mid_band = 0.72;
// Poses over the burst's life.
uniform float frames = 5.0;
// Fraction of the life spent popping out to full size.
uniform float pop = 0.25;
// Never smaller on screen than this (radius, radians of view), so a hit on a
// distant fighter still shows, but never grown past `max_grow` times its real
// size for it: further off, it shrinks with distance again, or a far miss
// would be drawn tens of metres wide. Bigger hits are their real size.
uniform float min_angle = 0.014;
uniform float max_grow = 2.5;

float hash(float n) {
	return fract(sin(n * 127.1 + 311.7) * 43758.5453);
}

void vertex() {
	// Billboard: the quad in view space round the node's position, pulled
	// towards the camera by its radius so the hull it hit doesn't hide it.
	vec3 centre = (VIEW_MATRIX * vec4(NODE_POSITION_WORLD, 1.0)).xyz;
	float size = length(MODEL_MATRIX[0].xyz);
	size = max(size, min(-centre.z * min_angle, size * max_grow));
	vec3 p = centre + vec3(VERTEX.xy * 2.0 * size, 0.0);
	p.z = min(p.z + size, -0.05);
	POSITION = PROJECTION_MATRIX * vec4(p, 1.0);
}

void fragment() {
	float t = floor(age * frames) / frames;
	vec2 uv = UV * 2.0 - 1.0;
	float r = length(uv);
	float turns = atan(uv.y, uv.x) / TAU * spikes + seed;
	// 1 at a spike's tip, 0 in the dip between two.
	float tip = 1.0 - abs(fract(turns) * 2.0 - 1.0);
	float reach = 1.0 - spike_variety * hash(floor(turns) + seed * 7.0);
	float outer = mix(valley, reach, pow(tip, 2.2));
	// Pop out, then grow a little more while the middle hollows out.
	float grow = t < pop ? mix(0.55, 1.0, t / pop) : 1.0 + (t - pop) * 0.25;
	outer *= grow;
	float hole = max(t - pop, 0.0) / (1.0 - pop) * outer * 1.1;
	if (r > outer || r < hole) {
		discard;
	}
	float f = (r - hole) / max(outer - hole, 0.001);
	vec3 col = f < core_band ? core_color.rgb : (f < mid_band ? mid_color.rgb : rim_color.rgb);
	ALBEDO = col * brightness;
	ALPHA = 1.0;
}
