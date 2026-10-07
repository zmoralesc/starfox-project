// Gradient noise on an integer hash, for world-space patterns in shaders:
// water.gdshader (foam, crests, ripples) and terrain.gdshader (ground colour
// patches and ragged boundaries).

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
