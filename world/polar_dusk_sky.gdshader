shader_type sky;
render_mode use_half_res_pass;

// A polar dusk sky (Fichina): deep blue-violet overhead, a warm orange-pink
// glow along the horizon towards the low sun, dusky lilac away from it, faint
// stars, and an aurora: curtains of green light fading to magenta at their
// tops, drifting slowly.
//
// The aurora: looking along a view ray, `aurora_layers` slices between
// aurora_height.x and .y (metres, as if the sky were flat) each sample a
// ribbon pattern (where a warped noise crosses aurora_level: soft bright
// lines, only where a much larger noise allows), so one ribbon seen from
// below stacks into a hanging curtain. Too few slices and the curtains break
// into parallel stripes near the horizon (16 did); a small per-pixel shift
// of the slices blends them. It is drawn in the half-resolution pass, the
// stars at full resolution, at least star_min_pixels wide so they don't
// blink as the camera turns (see stars()). Both are left out of the radiance
// cubemap (ambient light, reflections and the fog's sky colour), which then
// holds only the smooth gradient and stays cheap to update.
//
// Below the horizon the sky is the horizon colour, so it matches the fog
// where distant ground fades into it.

#include "res://effects/noise.gdshaderinc"

group_uniforms gradient;
uniform vec4 zenith_color : source_color = vec4(0.05, 0.07, 0.2, 1.0);
uniform vec4 upper_color : source_color = vec4(0.16, 0.18, 0.4, 1.0);
uniform vec4 horizon_color : source_color = vec4(0.45, 0.4, 0.6, 1.0);
// The horizon towards the sun, and right round it.
uniform vec4 sunset_color : source_color = vec4(1.0, 0.56, 0.36, 1.0);
uniform vec4 sun_glow_color : source_color = vec4(1.0, 0.78, 0.55, 1.0);
// Elevation (0..1 of straight up) where upper_color gives way to the zenith,
// and how high the horizon colour reaches.
uniform float upper_height : hint_range(0.0, 1.0) = 0.45;
uniform float horizon_height : hint_range(0.0, 1.0) = 0.18;
// How far round the horizon the sunset colour spreads (higher = narrower).
uniform float sunset_spread = 2.0;
// The glow round the sun: strength and tightness.
uniform float sun_glow = 1.2;
uniform float sun_glow_size = 10.0;
// The sun's disc: angular radius (radians) and brightness.
uniform float sun_size = 0.022;
uniform float sun_energy = 6.0;
group_uniforms;

group_uniforms stars;
uniform float star_density : hint_range(0.0, 0.1, 0.0005) = 0.0025;
uniform float star_brightness = 1.4;
// Cells round the sky per unit of direction: bigger = smaller, more stars.
uniform float star_scale = 260.0;
// A star's radius, in cells; the least it is drawn across, in screen pixels;
// and how much a star spread to that width is dimmed (see stars()).
uniform float star_size = 0.12;
uniform float star_min_pixels = 1.5;
uniform float star_spread_dimming : hint_range(0.0, 1.0) = 0.5;
group_uniforms;

group_uniforms aurora;
// Off skips the aurora altogether (none of its slices are sampled).
uniform bool aurora_enabled = true;
uniform vec4 aurora_low_color : source_color = vec4(0.25, 1.0, 0.55, 1.0);
uniform vec4 aurora_high_color : source_color = vec4(0.75, 0.3, 1.0, 1.0);
uniform float aurora_strength = 1.4;
// Heights of the curtains' bottom and top (metres; the sky is taken as flat).
uniform vec2 aurora_height = vec2(1000.0, 3200.0);
uniform int aurora_layers : hint_range(4, 64) = 40;
// The ribbons' size (metres), thinness and drift (metres a second).
uniform float aurora_scale = 8000.0;
uniform float aurora_thinness = 16.0;
// The noise level the ribbons follow, and how much the slices are dithered.
uniform float aurora_level : hint_range(0.0, 1.0) = 0.62;
uniform float aurora_jitter : hint_range(0.0, 1.0) = 0.15;
uniform float aurora_drift = 60.0;
// Mostly on the side away from the sun: 0 = all round, 1 = only opposite it.
uniform float aurora_away : hint_range(0.0, 1.0) = 0.7;
// Fades out towards the horizon below this elevation (0..1 of straight up).
uniform float aurora_fade = 0.12;
group_uniforms;

vec3 gradient(vec3 dir, vec3 sun) {
	float up = clamp(dir.y, 0.0, 1.0);
	vec3 col = mix(upper_color.rgb, zenith_color.rgb, smoothstep(upper_height * 0.5, upper_height * 1.6, up));
	// Towards the sun round the horizon: warm.
	vec2 flat_dir = normalize(dir.xz + vec2(1e-5));
	vec2 flat_sun = normalize(sun.xz + vec2(1e-5));
	float toward = pow(clamp(dot(flat_dir, flat_sun) * 0.5 + 0.5, 0.0, 1.0), sunset_spread);
	vec3 horizon = mix(horizon_color.rgb, sunset_color.rgb, toward);
	col = mix(horizon, col, smoothstep(0.0, horizon_height, up));
	// The glow round the sun.
	float near = clamp(dot(dir, sun), 0.0, 1.0);
	col += sun_glow_color.rgb * sun_glow * pow(near, sun_glow_size) * (0.4 + 0.6 * toward);
	return col;
}

// `px` is the size of a screen pixel in star cells. A star is far smaller
// than a pixel, so drawn at its own size it lit only the pixels whose centre
// happened to land on it, and blinked as the camera turned. Below
// star_min_pixels it is spread over that many pixels instead, dimmed to keep
// most of its light (star_spread_dimming: 1 keeps exactly the same light,
// which reads too faint; 0 doesn't dim).
float stars(vec3 dir, float px) {
	vec3 p = dir * star_scale;
	vec3 cell = floor(p);
	vec3 f = fract(p) - 0.5;
	// A star per cell, only in some cells (hash of two faces of the cell).
	float h = hash(cell.xy + cell.z * 17.0);
	float h2 = hash(cell.yz + cell.x * 31.0 + 7.0);
	if (h > star_density) {
		return 0.0;
	}
	float radius = max(star_size, px * star_min_pixels);
	// Kept inside its cell even at its widest, so no star is cut off at a
	// cell's edge.
	float room = max(0.5 - radius, 0.0) * 2.0;
	vec3 offset = (vec3(h2, hash(cell.zx + 3.0), fract(h2 * 7.3)) - 0.5) * min(room, 0.6);
	float d = length(f - offset);
	float dim = pow(star_size / radius, 2.0 * star_spread_dimming);
	return smoothstep(radius, 0.0, d) * (0.4 + 0.6 * h2) * dim;
}

// The aurora's ribbons at a point on the flat sky (metres): 0..1. A few
// soft lines (where a warped noise crosses 0.5), only where a much larger
// noise lets them (so the sky has a few curtains, not a pattern all over).
float ribbons(vec2 p) {
	vec2 q = p / aurora_scale;
	float where = smoothstep(0.5, 0.68, noise(q * 0.45 + 7.0));
	if (where <= 0.0) {
		return 0.0;
	}
	// Warped, so the ribbons fold and wander.
	q += vec2(noise(q * 1.3 + 3.0), noise(q * 1.3 + 11.0)) * 0.9;
	// A level off 0.5: gradient noise is exactly 0.5 at every lattice corner,
	// so its 0.5 contour would blot round each one.
	float n = noise(q * 1.6);
	float off = (n - aurora_level) * aurora_thinness;
	return exp(-off * off) * where;
}

vec3 aurora(vec3 dir, vec3 sun, vec2 pixel) {
	if (!aurora_enabled || dir.y < 0.01) {
		return vec3(0.0);
	}
	float away = mix(1.0, smoothstep(0.3, -0.6, dot(normalize(dir.xz + vec2(1e-5)), normalize(sun.xz + vec2(1e-5)))), aurora_away);
	float fade = smoothstep(0.0, aurora_fade, dir.y) * away;
	if (fade <= 0.001) {
		return vec3(0.0);
	}
	vec2 drift = vec2(TIME * aurora_drift, TIME * aurora_drift * 0.3);
	// Vertical rays: brightness varying along the curtain, read at its foot.
	vec2 foot = dir.xz / dir.y * aurora_height.x + drift;
	float rays = 0.6 + 0.4 * noise(foot / (aurora_scale * 0.03));
	// A small per-pixel shift of the slices (aurora_jitter of one), so
	// neighbouring slices blend instead of banding.
	float jitter = 0.5 + (hash(floor(pixel)) - 0.5) * aurora_jitter;
	vec3 total = vec3(0.0);
	for (int i = 0; i < aurora_layers; i++) {
		float t = (float(i) + jitter) / float(aurora_layers);
		float height = mix(aurora_height.x, aurora_height.y, t);
		vec2 p = dir.xz / dir.y * height + drift;
		// Brightest near the curtain's foot, fading up it.
		float strength = ribbons(p) * (1.0 - t) * (1.0 - t) * 2.5;
		total += mix(aurora_low_color.rgb, aurora_high_color.rgb, smoothstep(0.1, 0.8, t)) * strength;
	}
	return total / float(aurora_layers) * aurora_strength * fade * rays;
}

void sky() {
	vec3 sun = LIGHT0_ENABLED ? LIGHT0_DIRECTION : normalize(vec3(0.0, 0.1, -1.0));
	vec3 dir = EYEDIR;
	if (AT_HALF_RES_PASS) {
		// The aurora, composited over the gradient below.
		COLOR = aurora(dir, sun, FRAGCOORD.xy);
		ALPHA = 1.0;
	} else {
		vec3 col = gradient(dir, sun);
		if (!AT_CUBEMAP_PASS) {
			// The sun's disc, the stars (at full resolution: at half, a star
			// spread wide enough not to blink would be a blob), and the
			// half-res pass's aurora.
			float disc = smoothstep(cos(sun_size), cos(sun_size * 0.8), dot(dir, sun));
			col = mix(col, sun_glow_color.rgb * sun_energy, disc);
			float night = smoothstep(0.05, 0.5, dir.y) * (1.0 - smoothstep(-0.2, 0.8, dot(dir, sun)));
			float px = length(fwidth(dir)) * star_scale;
			col += vec3(stars(dir, px)) * star_brightness * night;
			col += HALF_RES_COLOR.rgb;
		}
		COLOR = col;
	}
}
