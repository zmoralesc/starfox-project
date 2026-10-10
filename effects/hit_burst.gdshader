shader_type spatial;
render_mode unshaded, blend_premul_alpha, cull_disabled, depth_draw_never, shadows_disabled, fog_disabled;

// A bolt's hit (HitBurst): an impact flash in the style of hand-drawn effects
// animation, on a quad facing the camera. A white-hot core that flares and
// shrinks, thin tapered rays that shoot out from it and thin away, and a
// shock ring that races out and fades, coloured from the core through
// `mid_color` to `rim_color` towards the edge. Crisp shapes painted over what's
// behind (premultiplied alpha), with a soft halo of added light; transparent,
// so no ink outlines.
//
// Per burst (instance uniforms): `age` 0 to 1 over its life, `seed` for its
// ray pattern. The node's scale is the flash's radius in metres.

instance uniform float age = 0.0;
instance uniform float seed = 0.0;

uniform vec4 core_color : source_color = vec4(1.0, 1.0, 0.9, 1.0);
uniform vec4 mid_color : source_color = vec4(1.0, 0.86, 0.22, 1.0);
uniform vec4 rim_color : source_color = vec4(1.0, 0.45, 0.1, 1.0);
// Overall strength; above 1 blooms.
uniform float brightness = 1.4;
// Core: radius at the start (fraction of the flash's).
uniform float core_size = 0.24;
// Rays: how many, how much their lengths vary, and their width at the root
// (fraction of a ray's angular slot).
uniform float rays = 9.0;
uniform float ray_variety = 0.5;
uniform float ray_width = 0.22;
// Shock ring: how bright (0 = none) and how thick (fraction of the radius).
uniform float ring_strength = 0.8;
uniform float ring_width = 0.035;
// Poses per life, like animation drawn on twos; 0 = smooth.
uniform float frames = 0.0;
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
	float t = frames > 0.0 ? floor(age * frames) / frames : age;
	vec2 uv = UV * 2.0 - 1.0;
	float r = length(uv);
	float aa = fwidth(r) * 1.5;
	// Fast out, slow settle: most of the motion in the first frames.
	float burst = 1.0 - pow(1.0 - t, 3.0);

	// Shapes are drawn as hand-drawn effects are: crisp edges, filled with
	// smooth colour, and they go by shrinking and thinning rather than by
	// fading. Core: a disc that flares, then shrinks to nothing.
	float core_r = core_size * (1.0 - smoothstep(0.0, 0.65, t)) * mix(1.0, 1.25, smoothstep(0.0, 0.1, t));
	float core = 1.0 - smoothstep(core_r - aa, core_r, r);

	// Rays: one per angular slot, at a random angle in it and of random
	// length. Each is a needle, widest at the root and tapering to its tip;
	// they shoot out (burst) while their roots pull away from the middle and
	// they thin, so late in its life a ray is a fine streak flying off.
	float turns = atan(uv.y, uv.x) / TAU * rays + seed;
	float slot = floor(turns);
	float across = abs(fract(turns) - mix(0.3, 0.7, hash(slot + seed * 3.1)));
	float reach = (1.0 - ray_variety * hash(slot * 1.7 + seed * 7.0)) * burst;
	float root = reach * smoothstep(0.1, 0.9, t);
	float along = clamp((r - root) / max(reach - root, 0.001), 0.0, 1.0);
	float width = ray_width * (1.0 - along) * (1.0 - t);
	// Angular width to screen distance, for the edge's antialiasing.
	float across_aa = aa * rays / (TAU * max(r, 0.05));
	// (`rays` 0 = none: the smoothstep's edges would meet.)
	float ray = smoothstep(width + across_aa, width, across) * step(root, r) * step(r, reach) * step(0.5, rays);

	// Shock ring racing out, thinning to nothing.
	float ring_r = mix(0.2, 1.0, burst);
	float ring_half = ring_width * (1.0 - t) * step(0.001, ring_strength);
	float ring = 1.0 - smoothstep(ring_half - aa, ring_half, abs(r - ring_r));

	// Colour: the core from `core_color` out to `mid_color` at its edge, the
	// rays from `mid_color` to `rim_color` at their tips, the ring `rim_color`
	// lightened. Painted over what's behind (premultiplied alpha), so the
	// colours hold even against a bright sky; only the halo adds light.
	vec3 core_col = mix(core_color.rgb, mid_color.rgb, smoothstep(0.3, 1.0, r / max(core_r, 0.001)));
	vec3 ray_col = mix(mid_color.rgb, rim_color.rgb, smoothstep(0.2, 0.9, along));
	vec3 ring_col = mix(rim_color.rgb, mid_color.rgb, 0.4);
	vec3 col = ring_col;
	float cover = ring * ring_strength;
	col = mix(col, ray_col, ray);
	cover = max(cover, ray);
	col = mix(col, core_col, core);
	cover = max(cover, core);
	// Halo: soft light round the core, early on.
	float halo = exp(-r * r / 0.18) * pow(1.0 - t, 3.0) * 0.6;
	vec3 light = col * cover * brightness + mid_color.rgb * halo;
	if (cover < 0.002 && halo < 0.002) {
		discard;
	}
	ALBEDO = light;
	ALPHA = cover;
}
