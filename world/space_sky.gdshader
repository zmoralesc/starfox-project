shader_type sky;

// Procedural starfield with faint nebulae and a sun glow from the first
// DirectionalLight3D in the scene.

uniform vec3 space_color : source_color = vec3(0.004, 0.005, 0.012);
uniform vec3 nebula_color_a : source_color = vec3(0.10, 0.03, 0.18);
uniform vec3 nebula_color_b : source_color = vec3(0.02, 0.08, 0.16);
uniform float nebula_strength = 0.8;
uniform float star_brightness = 3.0;
// Fraction of possible stars that are shown. 1.0 = very dense.
uniform float star_density : hint_range(0.0, 1.0) = 0.4;

float hash13(vec3 p) {
	p = fract(p * 0.1031);
	p += dot(p, p.zyx + 31.32);
	return fract((p.x + p.y) * p.z);
}

float value_noise(vec3 p) {
	vec3 i = floor(p);
	vec3 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(
		mix(mix(hash13(i + vec3(0, 0, 0)), hash13(i + vec3(1, 0, 0)), f.x),
			mix(hash13(i + vec3(0, 1, 0)), hash13(i + vec3(1, 1, 0)), f.x), f.y),
		mix(mix(hash13(i + vec3(0, 0, 1)), hash13(i + vec3(1, 0, 1)), f.x),
			mix(hash13(i + vec3(0, 1, 1)), hash13(i + vec3(1, 1, 1)), f.x), f.y),
		f.z);
}

float fbm(vec3 p) {
	float v = 0.0;
	float a = 0.5;
	for (int i = 0; i < 4; i++) {
		v += a * value_noise(p);
		p *= 2.03;
		a *= 0.5;
	}
	return v;
}

float star_layer(vec3 dir, float scale, float threshold) {
	vec3 p = dir * scale;
	vec3 cell = floor(p);
	float h = hash13(cell);
	if (h < threshold) {
		return 0.0;
	}
	vec3 jitter = vec3(hash13(cell + 11.7), hash13(cell + 23.1), hash13(cell + 37.9)) - 0.5;
	vec3 star_pos = normalize(cell + 0.5 + jitter * 0.3) * scale;
	float d = length(p - star_pos);
	float intensity = (h - threshold) / (1.0 - threshold);
	return smoothstep(0.3, 0.0, d) * (0.3 + intensity);
}

void sky() {
	vec3 dir = EYEDIR;
	vec3 col = space_color;

	// Nebula clouds, concentrated along a tilted "galactic" band.
	float band = pow(1.0 - abs(dot(dir, normalize(vec3(0.3, 1.0, 0.2)))), 3.0);
	float clouds = smoothstep(0.35, 0.8, fbm(dir * 2.5));
	vec3 tint = mix(nebula_color_a, nebula_color_b, fbm(dir * 4.0 + 7.0));
	col += tint * clouds * (0.4 + band) * nebula_strength;

	// At density 1.0, 3% of the large-star cells and 1.5% of the small-star cells hold a star.
	float stars = star_layer(dir, 180.0, 1.0 - 0.03 * star_density)
		+ star_layer(dir, 300.0, 1.0 - 0.015 * star_density) * 0.6;
	vec3 star_tint = mix(vec3(1.0, 0.85, 0.7), vec3(0.7, 0.8, 1.0), hash13(floor(dir * 180.0) + 5.0));
	col += stars * star_brightness * star_tint;

	if (LIGHT0_ENABLED) {
		float s = max(dot(dir, LIGHT0_DIRECTION), 0.0);
		col += LIGHT0_COLOR * (pow(s, 2000.0) * 20.0 + pow(s, 30.0) * 0.15);
	}

	COLOR = col;
}
