shader_type spatial;
render_mode depth_draw_always;

// Stylised cel-shaded water for the sea, lakes and rivers.
//
// - Colour in hard bands by depth: turquoise shallows, blue, deep blue. The
//   depth is the surface height minus the ground under it, read from a height
//   texture that Terrain fills in (Terrain._feed_water()); without one, all of
//   the water is deep.
// - Foam: a ragged white edge along every shore, and lines that roll in
//   towards it and fade.
// - Wave crests: sparse squiggly light lines drifting across (contour lines of
//   a slowly warping noise), fading out where they'd get too fine to draw.
// - Sun sparkles: a hard-edged glint on small moving ripples, which merge into
//   one sun path on the water far away.
// - Sky tint at grazing angles.
//
// No ink outlines (no line along every shore and at the horizon): it uses
// ALPHA (always 1, as `ALPHA *= 1.0` keeps it), which puts it in the
// transparent pass, after the outline quad and out of the depth texture the
// outlines read; depth_draw_always still writes depth there. Its materials
// get a render_priority between the outline quad (-100) and the other
// see-through things (0), so a huge plane whose centre is nearer than a laser
// bolt can't be drawn over it. The ripples only reach the sparkles (through
// v_ripple), never NORMAL, so the cel-shaded light on it stays flat.

group_uniforms colour;
uniform vec4 shallow_color : source_color = vec4(0.26, 0.72, 0.76, 1.0);
uniform vec4 water_color : source_color = vec4(0.16, 0.45, 0.76, 1.0);
uniform vec4 deep_color : source_color = vec4(0.09, 0.28, 0.6, 1.0);
// Depths (metres) where water_color and then deep_color take over.
uniform float mid_depth = 3.0;
uniform float deep_depth = 12.0;
// Ragged band edges: how far (metres of depth) the noise shifts them.
uniform float depth_wobble = 2.0;
// Sky colour seen in the water at grazing angles, and how strongly.
uniform vec4 sky_color : source_color = vec4(0.68, 0.82, 0.95, 1.0);
uniform float sky_reflection : hint_range(0.0, 1.0) = 0.45;

group_uniforms foam;
uniform vec4 foam_color : source_color = vec4(0.94, 0.98, 1.0, 1.0);
// Solid foam along the shore, up to this depth (metres).
uniform float foam_depth = 0.6;
// Lines roll in from this depth...
uniform float foam_reach = 4.0;
// ...this many times a second, each this thick (fraction of the spacing).
uniform float foam_speed = 0.35;
uniform float foam_line_width : hint_range(0.0, 1.0) = 0.18;
// The lines would follow the depth exactly, so on an evenly sloping beach
// they ran dead straight and even: noise bends them (`foam_wobble`, in
// fractions of the line spacing; `foam_wobble_scale` metres), varies their
// thickness and breaks them into separate crests (`foam_gaps`: share left
// out, 0 = unbroken).
uniform float foam_wobble = 1.0;
uniform float foam_wobble_scale = 10.0;
uniform float foam_gaps : hint_range(0.0, 1.0) = 0.3;

group_uniforms crests;
uniform vec4 crest_color : source_color = vec4(0.62, 0.86, 1.0, 1.0);
// Rough size of a crest squiggle, in metres.
uniform float crest_scale = 45.0;
// How much of the water has crests (0 = none).
uniform float crest_amount : hint_range(0.0, 1.0) = 0.35;
// Line half-width, in metres.
uniform float crest_width = 0.6;
uniform float crest_speed = 0.06;
// Crests fade out between these distances (metres).
uniform float crest_fade_start = 900.0;
uniform float crest_fade_end = 1800.0;

group_uniforms sparkle;
// Brightness of the sun glints; above 1 they bloom. 0 turns them off.
uniform float sparkle = 2.5;
// Higher = smaller glints.
uniform float sparkle_size : hint_range(4.0, 1024.0) = 300.0;
// Size of the ripples that catch the sun (metres) and how bumpy they are.
uniform float ripple_scale = 7.0;
uniform float ripple_strength = 0.12;
uniform float ripple_speed = 0.5;

group_uniforms light;
// As in the toon shader: brightness in shadow, and where shadow starts.
uniform float shadow_tone : hint_range(0.0, 1.0) = 0.45;
uniform float lit_threshold : hint_range(0.0, 1.0) = 0.45;

group_uniforms marks;
// Foam drawn by things happening on the water, fed by WaterMarks
// (world/water_marks.gd) every frame: rings where bolts splashed, and the
// wakes of ships skimming the surface. Times are WaterMarks' clock.
uniform float marks_time = 0.0;
// Splash rings: (x, z, start time, size), the first ring_count used.
uniform vec4 rings[32];
uniform int ring_count = 0;
// Box round all live rings (min x, min z, max x, max z), so the rest of the
// water skips the loop.
uniform vec4 ring_bounds = vec4(0.0);
// Seconds a ring lasts; its radius (metres, times its size) at the start and
// end; line thickness (metres, times size) as it starts, thinning as it goes.
uniform float ring_life = 1.2;
uniform vec2 ring_radius = vec2(0.6, 6.0);
uniform float ring_width = 0.45;
// Wake trails: points (x, z, time passed, strength 0..1) from oldest to
// newest; a negative strength starts a new trail (no segment from the point
// before), its size is the strength. The first wake_count used.
uniform vec4 wake[192];
uniform int wake_count = 0;
uniform vec4 wake_bounds = vec4(0.0);
// Seconds a wake lasts.
uniform float wake_life = 3.5;
// The V: two foam lines starting `wake_start` metres either side of the
// track and spreading `wake_spread` metres a second, `wake_line` metres thick
// (growing with age), breaking up as they fade.
uniform float wake_start = 1.5;
uniform float wake_spread = 12.0;
uniform float wake_line = 0.7;
// Churned foam straight behind the ship: this wide at first (metres), gone
// after `churn_life` seconds.
uniform float churn_width = 1.3;
uniform float churn_life = 1.6;

group_uniforms ground;
// Set by Terrain: ground heights on its grid (R channel, metres), and the grid
// as (x of the first point, z of the first point, spacing, points per side).
uniform sampler2D ground_heights : filter_linear, repeat_disable;
uniform vec4 ground_grid = vec4(0.0, 0.0, 1.0, 1.0);
uniform bool has_ground = false;
// Depth used outside the grid (open sea).
uniform float open_depth = 100.0;
group_uniforms;

// The ripple normal (view space), for the sparkles in light().
varying vec3 v_ripple;

// Random 0..1 for a grid corner (whole-number coordinates). An integer hash:
// float ones built on fract(p * 123.34) lose precision at world-scale
// coordinates, so neighbouring cells could compute different values for their
// shared corner, and every effect built on the noise broke off along long
// straight seams.
float hash(vec2 p) {
	uvec2 q = uvec2(ivec2(floor(p + 0.5)));
	q = q * uvec2(1597334673u, 3812015801u);
	uint n = (q.x ^ q.y) * 1597334673u;
	n ^= n >> 16u;
	return float(n) * (1.0 / 4294967295.0);
}

// Gradient noise, 0 to 1 (mostly 0.15 to 0.85): each grid corner gets a
// random gradient direction. Not value noise: cut at a threshold (crest
// patches, foam edges), value noise makes blocky shapes with straight edges
// along the world axes, which show as long straight cut-offs at a distance.
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

// Two octaves, the second turned and offset so they don't line up.
float noise2(vec2 p) {
	const mat2 turn = mat2(vec2(0.8, 0.6), vec2(-0.6, 0.8));
	return noise(p) * 0.65 + noise(turn * p * 2.1 + 5.2) * 0.35;
}

// Hard edge, blended over about one pixel.
float aa_step(float edge, float x) {
	float w = max(fwidth(x), 0.0005);
	return smoothstep(edge - w, edge + w, x);
}

// The same with the blur width given (`w`, e.g. metres per pixel): inside the
// marks' loops, which pixels skip differently, fwidth() is undefined.
float px_step(float edge, float x, float w) {
	return smoothstep(edge - w, edge + w, x);
}

float water_depth(vec3 world) {
	if (!has_ground) {
		return open_depth;
	}
	vec2 cell = (world.xz - ground_grid.xy) / ground_grid.z;
	if (any(lessThan(cell, vec2(0.0))) || any(greaterThan(cell, vec2(ground_grid.w - 1.0)))) {
		return open_depth;
	}
	// Texel centres sit on the grid points.
	vec2 uv = (cell + 0.5) / ground_grid.w;
	return world.y - texture(ground_heights, uv).r;
}

// Bumps on the water surface, for the sparkles: two noise layers drifting
// different ways. Returns the world-space normal.
vec3 ripple_normal(vec2 xz, float strength) {
	vec2 p = xz / ripple_scale;
	float t = TIME * ripple_speed;
	vec2 a = p + vec2(t, t * 0.4);
	vec2 b = mat2(vec2(0.6, -0.8), vec2(0.8, 0.6)) * p * 1.7 - vec2(t * 0.7, -t);
	const float e = 0.15;
	float h = noise(a) + noise(b);
	float hx = noise(a + vec2(e, 0.0)) + noise(b + vec2(e * 0.6, e * 0.8));
	float hz = noise(a + vec2(0.0, e)) + noise(b + vec2(-e * 0.8, e * 0.6));
	return normalize(vec3(-(hx - h) / e * strength, 1.0, -(hz - h) / e * strength));
}

bool in_box(vec2 p, vec4 box, float margin) {
	return p.x > box.x - margin && p.y > box.y - margin && p.x < box.z + margin && p.y < box.w + margin;
}

// Foam (0..1) from splash rings at `xz`.
float ring_foam(vec2 xz, float px) {
	if (ring_count == 0 || !in_box(xz, ring_bounds, ring_radius.y * 3.0)) {
		return 0.0;
	}
	float foam = 0.0;
	for (int i = 0; i < ring_count; i++) {
		vec4 r = rings[i];
		float t = (marks_time - r.z) / ring_life;
		if (t < 0.0 || t > 1.0) {
			continue;
		}
		float eased = 1.0 - (1.0 - t) * (1.0 - t);
		float radius = mix(ring_radius.x, ring_radius.y, eased) * r.w;
		float d = length(xz - r.xy);
		// Ragged: the line thins away in places as it fades.
		float rag = noise((xz - r.xy) / 1.5 + r.z * 13.0);
		float width = ring_width * r.w * (1.0 - t) * (0.4 + rag);
		foam = max(foam, 1.0 - px_step(width, abs(d - radius), px));
		// A churned centre for the first moments.
		foam = max(foam, 1.0 - px_step(radius * 0.5 * (1.0 - t * 2.0) * rag, d, px));
	}
	return foam;
}

// Foam (0..1) from ships' wakes at `xz`: per segment of each trail, the
// distance from the track and how long ago the ship passed there.
float wake_foam(vec2 xz, float px) {
	float reach = wake_start + wake_spread * wake_life + wake_line * 3.0;
	if (wake_count < 2 || !in_box(xz, wake_bounds, reach)) {
		return 0.0;
	}
	float foam = 0.0;
	// Noise at this spot (outside the loop: it doesn't depend on the trail),
	// so the bands come out uneven: clean, even-width lines looked drawn on.
	float breakup = noise(xz / 2.5);
	// Large: the arm wanders in and out and swells and thins along its length.
	float wander = noise2(xz / 9.0) - 0.5;
	float swell = noise(xz / 5.0 + 31.0);
	// Small: ragged edges, and foam flecks just outside the band.
	float fleck = noise2(xz / 1.1 + 7.0);
	for (int i = 1; i < wake_count; i++) {
		vec4 b = wake[i];
		if (b.w < 0.0) {
			continue;  // starts a new trail: no segment from the point before
		}
		vec4 a = wake[i - 1];
		vec2 ab = b.xy - a.xy;
		float along = dot(xz - a.xy, ab) / max(dot(ab, ab), 1e-4);
		float s = clamp(along, 0.0, 1.0);
		float d = length(xz - (a.xy + ab * s));
		if (d > reach) {
			continue;
		}
		float age = marks_time - mix(a.z, b.z, s);
		if (age < 0.0 || age > wake_life) {
			continue;
		}
		float strength = mix(abs(a.w), b.w, s);
		float t = age / wake_life;
		// The V's arms: spreading, wandering more as they age, swelling and
		// thinning, with ragged edges, breaking into patches as they fade.
		float arm = abs(d - (wake_start + wake_spread * age) - wander * (1.0 + age * 2.5));
		float width = wake_line * (1.0 + age * 0.6) * strength * (0.25 + 1.5 * swell);
		width += (fleck - 0.5) * wake_line * 1.2;
		// Only beside the segment, not round its ends: there the distance is to
		// a point, and the arm would draw a circle round every trail point.
		float line = (along >= 0.0 && along <= 1.0) ? 1.0 - px_step(width, arm, px) : 0.0;
		// Patchy from the start, and more so in the first moments, so the arms
		// fray in behind the ship rather than starting on a straight edge.
		line *= px_step(max(0.15 + t * 0.75, 1.0 - age / 0.3), breakup, 0.02);
		// Churn down the middle.
		float churn_edge = churn_width * strength * (1.0 - age / churn_life) * (0.3 + breakup + (fleck - 0.5) * 0.8);
		// Breaking into patches as it narrows, not tapering to a thin straight line.
		float churn = (1.0 - px_step(churn_edge, d, px)) * px_step(0.1 + age / churn_life * 0.6, breakup, 0.02);
		foam = max(foam, max(line, churn));
	}
	return foam;
}

void fragment() {
	vec3 world = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float dist = length(VERTEX);
	float slow = TIME * crest_speed;

	// Depth bands, with ragged edges.
	float depth = water_depth(world);
	float wobble = (noise2(world.xz / 30.0 + slow) - 0.5) * depth_wobble;
	vec3 col = shallow_color.rgb;
	col = mix(col, water_color.rgb, aa_step(mid_depth, depth + wobble));
	col = mix(col, deep_color.rgb, aa_step(deep_depth, depth + wobble));

	// Wave crests: contour lines of a warping noise, in sparse patches.
	vec2 p = world.xz / crest_scale;
	vec2 warp = vec2(noise(p * 0.5 + slow), noise(p * 0.5 + 17.3 - slow));
	float contour = noise2(p + warp * 1.5 + vec2(slow * 2.0, slow)) * 4.0 + slow * 3.0;
	float line_w = max(fwidth(contour), 1e-5);
	// Distance to the nearest line in pixels, then a fixed width in metres:
	// where the noise flattens out the lines would otherwise swell into blobs.
	float from_line_px = abs(fract(contour + 0.5) - 0.5) / line_w;
	float metres_per_px = max(length(fwidth(world.xz)) * 0.7, 1e-4);
	float width_px = crest_width / metres_per_px;
	float crest = 1.0 - smoothstep(width_px - 0.75, width_px + 0.75, from_line_px);
	float patches = aa_step(1.0 - crest_amount, noise(p * 0.35 - slow * 0.5));
	// Gone before the lines get too fine to draw cleanly, and in the distance.
	float detail = 1.0 - smoothstep(0.15, 0.35, line_w);
	detail *= 1.0 - smoothstep(crest_fade_start, crest_fade_end, dist);
	col = mix(col, crest_color.rgb, crest * patches * detail);

	// Shore foam: a solid ragged edge, plus lines rolling in to it.
	float edge_noise = noise(world.xz / 6.0 + slow * 4.0);
	float foam = 1.0 - aa_step(foam_depth * (0.5 + edge_noise), depth);
	vec2 shore_p = world.xz / foam_wobble_scale;
	float bend = (noise2(shore_p + vec2(slow, -slow)) - 0.5) * foam_wobble;
	float phase = depth / foam_reach + TIME * foam_speed + bend;
	float thickness = foam_line_width * (0.4 + 1.2 * noise(shore_p * 1.7 + 11.0));
	float rolling = 1.0 - aa_step(thickness, fract(phase));
	rolling *= aa_step(foam_gaps, noise(shore_p * 0.8 + vec2(-slow * 3.0, 23.0)));
	rolling *= 1.0 - aa_step(0.75 + 0.25 * edge_noise, depth / foam_reach);
	// Splash rings and wakes (WaterMarks): foam like the shore's.
	float marks = max(ring_foam(world.xz, metres_per_px), wake_foam(world.xz, metres_per_px));
	foam = max(foam, marks);
	col = mix(col, foam_color.rgb, max(foam, rolling));

	// Sky at grazing angles (on the flat surface, so it's a smooth gradient).
	float fresnel = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 5.0);
	col = mix(col, sky_color.rgb, fresnel * sky_reflection * (1.0 - max(foam, rolling)));

	// Ripples flatten out where they'd be smaller than a pixel, so the
	// sparkles far away merge into one sun path instead of flickering.
	float ripple_px = metres_per_px / ripple_scale;
	float strength = ripple_strength * (1.0 - smoothstep(0.04, 0.2, ripple_px));
	// No sparkles on foam.
	strength *= 1.0 - max(foam, rolling);
	v_ripple = normalize((VIEW_MATRIX * vec4(ripple_normal(world.xz, strength), 0.0)).xyz);

	ALBEDO = col;
	ALPHA *= 1.0;  // transparent pass: no ink outlines (see the top)
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
}

void light() {
	// Flat surface: only shadows (ships, clouds) change the light on it.
	float ndl = clamp(dot(NORMAL, LIGHT), 0.0, 1.0) * ATTENUATION;
	float floor_tone = LIGHT_IS_DIRECTIONAL ? shadow_tone : 0.0;
	DIFFUSE_LIGHT += mix(floor_tone, 1.0, aa_step(lit_threshold, ndl)) * LIGHT_COLOR / PI;

	float h = pow(clamp(dot(v_ripple, normalize(LIGHT + VIEW)), 0.0, 1.0), sparkle_size);
	SPECULAR_LIGHT += sparkle * aa_step(0.5, h) * ATTENUATION * LIGHT_COLOR / PI;
}
