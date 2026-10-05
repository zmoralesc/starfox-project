shader_type spatial;
render_mode unshaded, cull_disabled, shadows_disabled, depth_draw_never;

// A warp portal on a flat quad (see WarpPortal): a dark swirling hole with
// spiral arms, a hot core and a bright, wobbling rim, plus a soft halo outside.
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
// Number of spiral arms (whole numbers keep the pattern seamless).
uniform float arms = 5.0;
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

	// Swirling bands, twisted more towards the middle.
	float twist = TIME * spin + (1.0 - clamp(r, 0.0, 1.0)) * 3.0;
	vec2 q = mat2(vec2(cos(twist), sin(twist)), vec2(-sin(twist), cos(twist))) * (p / open);
	float arm = 0.5 + 0.5 * sin(arms * a + 7.0 * log(r + 0.03) - TIME * spin * 2.0);
	float swirl = smoothstep(0.35, 0.95, arm) * (0.45 + 0.8 * fbm(q * 3.0));
	swirl *= smoothstep(0.08, 0.55, r);

	vec3 color = mix(void_color.rgb, swirl_color.rgb * glow, clamp(swirl, 0.0, 1.0));
	color += core_color.rgb * glow * exp(-r * r * 40.0);
	// Rim: brightest right at the edge, bleeding a little inwards.
	float rim = exp(-pow((r - edge) / 0.045, 2.0)) + 0.6 * smoothstep(edge - 0.3, edge, r);
	color = mix(color, rim_color.rgb * glow, clamp(rim, 0.0, 1.0));

	float alpha;
	if (r < edge) {
		alpha = hole_opacity;
	} else {
		// Outside: the rim's sharp falloff, then a soft halo.
		float out_d = r - edge;
		float halo = exp(-out_d * 14.0) * 0.55 + exp(-pow(out_d / 0.03, 2.0));
		color = rim_color.rgb * glow;
		// Faded to nothing before the quad's edge, so its square never shows.
		halo *= 1.0 - smoothstep(0.7 * extent, 0.97 * extent, length(p));
		alpha = clamp(halo, 0.0, 1.0);
	}
	ALBEDO = color;
	ALPHA = alpha;
}
