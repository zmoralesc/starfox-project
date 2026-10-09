shader_type spatial;
render_mode unshaded, cull_disabled, shadows_disabled, depth_draw_never;

// A warp portal on a flat quad (see WarpPortal): a tear into a dark tunnel,
// with fine spiral filaments flowing inwards into it, faint speed lines
// streaming to a far-off pinpoint core, and a thin white-hot rim crackling
// with energy, bleeding crimson inwards, plus a soft halo outside.
// `open` grows it from nothing to full size (and past it, for the overshoot).

// Current size, as a fraction of the full radius (0 = shut).
uniform float open = 1.0;
// Half the quad's size over the full radius (room for the overshoot and halo).
uniform float extent = 1.3;
uniform vec4 rim_color : source_color = vec4(1.0, 0.12, 0.18, 1.0);
uniform vec4 swirl_color : source_color = vec4(0.55, 0.18, 1.0, 1.0);
uniform vec4 core_color : source_color = vec4(1.0, 0.8, 1.0, 1.0);
uniform vec4 void_color : source_color = vec4(0.05, 0.0, 0.09, 1.0);
// Brightness of the rim, swirls and core (above 1 they bloom).
uniform float glow = 2.5;
// Number of spiral filaments (whole numbers keep the pattern seamless).
uniform float arms = 15.0;
// How tightly they wind (turns per step into the tunnel).
uniform float twist = 1.4;
// How fast their pieces and the speed lines flow inwards.
uniform float flow = 0.9;
// Faint speed lines streaming to the core (lanes round the circle).
uniform float streaks = 40.0;
// Half-width of the white-hot rim line (fraction of the radius).
uniform float rim_width = 0.012;
// How fast the arms turn (radians per second).
uniform float spin = 1.2;
// Opacity of the hole: below 1, stars show faintly through.
uniform float hole_opacity : hint_range(0.0, 1.0) = 0.92;

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
			mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

float fbm(vec2 p) {
	return 0.5 * noise(p) + 0.3 * noise(p * 2.1 + 3.7) + 0.2 * noise(p * 4.3 + 9.1);
}

void fragment() {
	if (open < 0.001) {
		discard;
	}
	vec2 p = (UV - 0.5) * 2.0 * extent;  // 1 = the full radius
	float r = length(p) / open;          // 1 = the current edge
	vec2 dir = p / max(length(p), 0.0001);
	float a = atan(p.y, p.x);
	// The edge wobbles (noise on the direction, so there's no seam).
	float edge = 1.0 + (fbm(dir * 2.5 + vec2(TIME * 0.6, -TIME * 0.4)) - 0.5) * 0.08;
	float aa = fwidth(r) * 1.5;

	// Tunnel coordinates: `depth` is 0 at the rim and grows towards the
	// middle (logarithmically, so equal steps look like equal steps into a
	// tunnel), the angle in turns.
	float depth = -log(max(r, 0.015));
	float turns = a / TAU;

	// Spiral filaments: many fine arms, each its own brightness and width,
	// breaking into pieces that flow inwards and fading into the dark.
	float s = turns * arms + depth * twist - TIME * spin * 0.25;
	float strand = mod(floor(s), arms);  // whole arms: no seam where the angle wraps
	float strand_rand = hash(vec2(strand, 3.1));
	float half_w = mix(0.06, 0.2, strand_rand);
	float filament = 1.0 - smoothstep(half_w, half_w + aa * arms * 0.5, abs(fract(s) - 0.5));
	filament *= smoothstep(0.35, 0.65, noise(vec2(strand * 5.3, depth * 2.5 - TIME * flow)));
	filament *= exp(-depth * 1.1) * mix(0.5, 1.0, strand_rand);

	// Speed lines streaming in towards the core, faint.
	float lane = floor(turns * streaks);
	float lane_rand = hash(vec2(lane, 8.7));
	float dash = fract(depth * 0.6 + TIME * flow * (0.6 + lane_rand) + lane_rand * 5.0);
	float streak = (1.0 - smoothstep(0.02, 0.06, abs(fract(turns * streaks) - 0.5) * (1.0 + depth)))
			* smoothstep(0.75, 0.95, dash) * step(0.55, lane_rand) * smoothstep(0.1, 0.6, depth);

	vec3 color = void_color.rgb;
	color += swirl_color.rgb * glow * filament;
	color += core_color.rgb * glow * 0.5 * streak;
	// Core: a far-off pinpoint of light.
	color += core_color.rgb * glow * (exp(-r * r * 160.0) * 1.5 + exp(-r * r * 18.0) * 0.15);

	// Rim: a thin white-hot line, crimson bleeding inwards from it, and energy
	// crackling along it in bright arcs.
	float rim_line = 1.0 - smoothstep(rim_width, rim_width + aa, abs(r - edge));
	float bleed = smoothstep(edge - 0.22, edge, r) * 0.55;
	float crackle = smoothstep(0.62, 0.8, fbm(dir * 7.0 + vec2(TIME * 2.3, -TIME * 1.7)))
			* (1.0 - smoothstep(0.0, 0.07, abs(r - edge)));
	color = mix(color, rim_color.rgb * glow, clamp(bleed, 0.0, 1.0));
	color = mix(color, mix(rim_color.rgb, core_color.rgb, 0.7) * glow * 1.4, max(rim_line, crackle));

	float alpha;
	if (r < edge) {
		alpha = hole_opacity;
	} else {
		// Outside: the rim line's edge, then a soft halo.
		float out_d = r - edge;
		float halo = exp(-out_d * 16.0) * 0.4;
		float line = max(rim_line, crackle);
		color = mix(rim_color.rgb * glow, color, line);
		// Faded to nothing before the quad's edge, so its square never shows.
		halo *= 1.0 - smoothstep(0.7 * extent, 0.97 * extent, length(p));
		alpha = clamp(max(halo, line), 0.0, 1.0);
	}
	ALBEDO = color;
	ALPHA = alpha;
}
