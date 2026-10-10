shader_type spatial;
render_mode unshaded, cull_disabled, shadows_disabled, depth_draw_never;

// A warp portal on a flat quad (see WarpPortal): a glowing well of energy,
// a white-hot core blooming out through a hot haze that churns slowly and
// throws soft rays, fading to dark towards a thin white-hot rim crackling
// with energy, bleeding crimson inwards, plus a soft halo outside.
// `open` grows it from nothing to full size (and past it, for the overshoot).

// Current size, as a fraction of the full radius (0 = shut).
uniform float open = 1.0;
// Half the quad's size over the full radius (room for the overshoot and halo).
uniform float extent = 1.3;
uniform vec4 rim_color : source_color = vec4(1.0, 0.12, 0.18, 1.0);
// The haze round the core.
uniform vec4 glow_color : source_color = vec4(1.0, 0.3, 0.45, 1.0);
uniform vec4 core_color : source_color = vec4(1.0, 0.85, 0.9, 1.0);
uniform vec4 void_color : source_color = vec4(0.05, 0.0, 0.09, 1.0);
// Brightness of the rim and core (above 1 they bloom), and of the haze as a
// fraction of that.
uniform float glow = 2.5;
uniform float haze_glow = 0.7;
// Radius of the white-hot core and of the haze round it (fractions of the
// portal's radius: the brightness falls to 1/e there).
uniform float core_size = 0.13;
uniform float haze_size = 0.36;
// How much the haze churns (0 = a smooth glow), and the size of its churn
// (cells per radius).
uniform float churn = 0.5;
uniform float churn_scale = 2.5;
// Soft rays of light drifting round the core: strength and sharpness.
uniform float rays = 0.6;
uniform float ray_sharpness = 4.0;
// Breathing of the glow: depth (fraction of brightness) and rate (rad/s).
uniform float pulse = 0.08;
uniform float pulse_rate = 2.5;
// Half-width of the white-hot rim line (fraction of the radius).
uniform float rim_width = 0.012;
// Opacity of the hole: below 1, stars show faintly through the dark.
uniform float hole_opacity : hint_range(0.0, 1.0) = 0.92;

#include "res://effects/noise.gdshaderinc"

// Value noise on a float hash for the rim (its wobble, crackle and rays: small
// coordinates, where it holds up). The churn uses the shared gradient noise:
// this one broke into hard-edged cells there.
float rim_hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float rim_noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(rim_hash(i), rim_hash(i + vec2(1.0, 0.0)), u.x),
			mix(rim_hash(i + vec2(0.0, 1.0)), rim_hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

float rim_fbm(vec2 p) {
	return 0.5 * rim_noise(p) + 0.3 * rim_noise(p * 2.1 + 3.7) + 0.2 * rim_noise(p * 4.3 + 9.1);
}

void fragment() {
	if (open < 0.001) {
		discard;
	}
	vec2 p = (UV - 0.5) * 2.0 * extent;  // 1 = the full radius
	float r = length(p) / open;          // 1 = the current edge
	vec2 q = p / open;                   // position inside the disc, 1 = its edge
	vec2 dir = p / max(length(p), 0.0001);
	// The edge wobbles (noise on the direction, so there's no seam).
	float edge = 1.0 + (rim_fbm(dir * 2.5 + vec2(TIME * 0.6, -TIME * 0.4)) - 0.5) * 0.08;
	float aa = fwidth(r) * 1.5;

	// The glow: a white-hot core blooming out through the haze, which churns
	// slowly (two drifting layers of noise, so it never settles) and throws
	// soft rays round the core (noise on the direction, seamless round the
	// circle, drifting round), the whole breathing gently.
	float breath = 1.0 + pulse * sin(TIME * pulse_rate);
	float core = exp(-r * r / (core_size * core_size));
	float haze = exp(-r * r / (haze_size * haze_size));
	float churned = noise2(q * churn_scale + vec2(TIME * 0.17, -TIME * 0.11))
			+ noise2(q * churn_scale * 1.7 - vec2(TIME * 0.09, TIME * 0.14)) - 1.0;
	haze *= 1.0 + churn * churned * 2.0;
	float ray = pow(rim_fbm(dir * 3.0 + vec2(TIME * 0.12, TIME * 0.07)), ray_sharpness) * 8.0;
	haze *= 1.0 + rays * ray * smoothstep(0.0, 0.4, r);

	vec3 color = void_color.rgb;
	color += glow_color.rgb * glow * haze_glow * breath * max(haze, 0.0);
	// The core, with a pinpoint of pure light in the middle.
	color += core_color.rgb * glow * breath * (core * 1.3 + exp(-r * r * 160.0) * 0.8);

	// Rim: a thin white-hot line, crimson bleeding inwards from it, and energy
	// crackling along it in bright arcs.
	float rim_line = 1.0 - smoothstep(rim_width, rim_width + aa, abs(r - edge));
	float bleed = smoothstep(edge - 0.22, edge, r) * 0.55;
	float crackle = smoothstep(0.62, 0.8, rim_fbm(dir * 7.0 + vec2(TIME * 2.3, -TIME * 1.7)))
			* (1.0 - smoothstep(0.0, 0.07, abs(r - edge)));
	color = mix(color, rim_color.rgb * glow, clamp(bleed, 0.0, 1.0));
	color = mix(color, mix(rim_color.rgb, core_color.rgb, 0.7) * glow * 1.4, max(rim_line, crackle));

	float alpha;
	if (r < edge) {
		// Solid where the glow is bright; the dark lets stars through faintly.
		alpha = clamp(hole_opacity + haze, 0.0, 1.0);
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
