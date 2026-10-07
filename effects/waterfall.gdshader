shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_always, shadows_disabled;

// The Corneria waterfall's sheet (Waterfall, world/waterfall.gd): cartoon water
// in flat bands, the water's blues with white streaks, pouring down. Streaks
// move with the water, speeding up as it falls (the mesh's UV.y is each
// point's time of travel from the lip, in seconds); a white band where it
// spills over the lip; more and more white towards the foot as it breaks up;
// ragged sides; optionally (`splits`), a few splits just under the lip, as if rocks there parted the
// water, closing again lower down, rimmed with foam. A darker band where the
// body turns away from you (its rounded sides), so it reads as a thick body
// of water from any angle, not a flat sheet.
//
// Drawn in the transparent pass (it writes ALPHA), so no ink outlines.
//
// Mesh (a closed lens-shaped body): UV.x 0 to 1 across, UV.y seconds of travel
// (negative on the run-up on the river above the lip), UV2.x 0 at the lip to 1
// at the foot, UV2.y 0 on the front and 1 on the back; COLOR.a fades the
// run-up in over the river.

uniform vec4 water_color : source_color = vec4(0.16, 0.45, 0.76, 1.0);
uniform vec4 light_color : source_color = vec4(0.42, 0.7, 0.92, 1.0);
uniform vec4 foam_color : source_color = vec4(0.94, 0.98, 1.0, 1.0);
// How fast the pattern pours, times real falling speed (a 120 m drop takes
// five seconds, which looks sluggish at this size).
uniform float speed = 2.2;
// Streaks across the sheet, and their length (per second of travel).
uniform float streaks = 16.0;
uniform float streak_length = 1.1;
// Noise thresholds for the light and the white streaks (higher = fewer).
uniform float light_above = 0.52;
uniform float foam_above = 0.68;
// The white band over the lip: where it peaks and how far it reaches either
// side (seconds of travel).
uniform float lip_foam_at = 0.25;
uniform float lip_foam_reach = 0.6;
// From this far down (fraction of the drop) the white takes over, until it's
// nearly all foam at the foot.
uniform float foot_foam_from = 0.6;
// Ragged sides: how far in they bite (fraction of the half width), growing
// down the drop.
uniform float ragged = 0.18;
// Splits under the lip where the cliff shows through: how many could fit
// across, how much they open (noise units; 0 = none, the default; try 0.2),
// how far down they close
// (fraction of the drop), and how wide their foam rims are (noise units).
uniform float split_count = 4.0;
uniform float splits = 0.0;
uniform float split_close = 0.4;
uniform float split_rim = 0.05;
// Where the body turns this far from facing you (1 = straight at you, 0 =
// edge on), it's drawn `shade` times as bright.
uniform float shade_below = 0.45;
uniform float shade = 0.8;

// The same integer-hashed gradient noise as water.gdshader (see there why not
// a float hash).
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
	vec2 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
	float a0 = hash(i) * 6.2831853;
	float a1 = hash(i + vec2(1.0, 0.0)) * 6.2831853;
	float a2 = hash(i + vec2(0.0, 1.0)) * 6.2831853;
	float a3 = hash(i + vec2(1.0, 1.0)) * 6.2831853;
	float n0 = dot(vec2(cos(a0), sin(a0)), f);
	float n1 = dot(vec2(cos(a1), sin(a1)), f - vec2(1.0, 0.0));
	float n2 = dot(vec2(cos(a2), sin(a2)), f - vec2(0.0, 1.0));
	float n3 = dot(vec2(cos(a3), sin(a3)), f - vec2(1.0, 1.0));
	return 0.5 + 0.75 * mix(mix(n0, n1, u.x), mix(n2, n3, u.x), u.y);
}

float noise2(vec2 p) {
	const mat2 turn = mat2(vec2(0.8, 0.6), vec2(-0.6, 0.8));
	return noise(p) * 0.65 + noise(turn * p * 2.1 + 5.2) * 0.35;
}

void fragment() {
	float across = UV.x;
	float fall = UV2.x;
	// The pattern's coordinate along the flow: travel time, minus the clock,
	// so it moves with the water.
	float flow = UV.y - TIME * speed;

	// Ragged sides, the bites travelling down with the water.
	float side = abs(across * 2.0 - 1.0);
	float bite = ragged * (0.3 + fall) * noise(vec2(flow * 2.0, step(0.5, across) * 17.0));
	if (side > 1.0 - bite) {
		discard;
	}

	// Splits: fixed across the lip (rocks don't move), opening just under it
	// and narrowing to nothing by `split_close`, a wedge pointing down, as the
	// water spreads back together. Their edges flicker a little with the flow.
	float rock = noise(vec2(across * split_count + 3.7, 1.3)) + noise(vec2(across * 40.0, flow * 3.0)) * 0.04;
	float open = splits * smoothstep(0.0, 0.04, fall) * (1.0 - smoothstep(0.04, split_close, fall));
	float split_edge = 0.86 - open;
	if (open > 0.0 && rock > split_edge) {
		discard;
	}
	bool rim = open > 0.0 && rock > split_edge - split_rim;

	// Streaks: long along the flow, narrow across.
	float n = noise2(vec2(across * streaks, flow * streak_length));
	float lip = 1.0 - smoothstep(0.0, lip_foam_reach, abs(UV.y - lip_foam_at));
	float foot = smoothstep(foot_foam_from, 1.0, fall);
	// The run-up on the river: plain water, streaks forming towards the lip.
	float calm = 1.0 - smoothstep(-1.2, 0.0, UV.y);
	float light_t = light_above + calm * 0.3 - foot * 0.35;
	float foam_t = foam_above + calm * 0.4 - foot * 0.6 - lip * 0.35;

	vec3 col = water_color.rgb;
	if (n > light_t) {
		col = light_color.rgb;
	}
	if (n > foam_t || rim) {
		col = foam_color.rgb;
	}
	// Its rounded sides, turning away from you, a band darker. (abs: the back
	// surface's normals point the other way.)
	if (abs(dot(NORMAL, VIEW)) < shade_below) {
		col *= shade;
	}
	ALBEDO = col;
	ALPHA *= COLOR.a;
}
