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

// A distant planet (Corneria on the Asteroid Field), drawn into the sky so it
// sits infinitely far away. Lit by the first DirectionalLight3D, like the sun glow.
group_uniforms planet;
uniform bool planet_enabled = false;
// Where it is in the sky (pointing from the viewer to its centre).
uniform vec3 planet_direction = vec3(-0.62, -0.42, -0.66);
// Apparent size: angle (degrees) from its centre to its edge.
uniform float planet_angular_radius : hint_range(0.5, 60.0) = 17.0;
// Its north pole, and how far it's turned about it (radians): which side faces us.
uniform vec3 planet_axis = vec3(-0.3, 1.0, -0.5);
uniform float planet_spin = 0.0;
// Changes the continents and clouds without changing anything else.
uniform float planet_seed = 3.0;
uniform float continent_scale = 1.4;
uniform float land_amount : hint_range(0.0, 1.0) = 0.42;
uniform vec3 ocean_deep : source_color = vec3(0.03, 0.12, 0.36);
uniform vec3 ocean_shallow : source_color = vec3(0.08, 0.34, 0.60);
uniform vec3 land_low : source_color = vec3(0.20, 0.46, 0.18);
uniform vec3 land_high : source_color = vec3(0.52, 0.47, 0.30);
uniform vec3 ice_color : source_color = vec3(0.88, 0.93, 1.0);
// Ice caps start at this |sin(latitude)|.
uniform float ice_latitude : hint_range(0.0, 1.0) = 0.9;
uniform vec3 cloud_color : source_color = vec3(1.0, 1.0, 1.0);
uniform float cloud_amount : hint_range(0.0, 1.0) = 0.55;
uniform vec3 atmosphere_color : source_color = vec3(0.35, 0.62, 1.0);
// Thickness of the glow beyond the edge, as a fraction of the planet's radius.
uniform float atmosphere_width : hint_range(0.0, 0.3) = 0.05;
uniform float atmosphere_strength = 1.6;
// Cities glowing on the night side.
uniform vec3 city_light_color : source_color = vec3(1.0, 0.72, 0.32);
uniform float city_light_strength = 0.8;
uniform float planet_brightness = 1.0;
// Light on the night side (0 = black).
uniform float night_brightness : hint_range(0.0, 0.2) = 0.025;
group_uniforms;

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

// More octaves than fbm(): the planet is big enough on screen to show them.
float fbm6(vec3 p) {
	float v = 0.0;
	float a = 0.5;
	for (int i = 0; i < 6; i++) {
		v += a * value_noise(p);
		p *= 2.03;
		a *= 0.5;
	}
	return v;
}

// Rotates v by angle about the unit axis k (Rodrigues).
vec3 rotate_about(vec3 v, vec3 k, float angle) {
	float c = cos(angle);
	float s = sin(angle);
	return v * c + cross(k, v) * s + k * dot(k, v) * (1.0 - c);
}

// The planet's colour where the view ray `dir` hits it, at surface normal n.
vec3 planet_surface(vec3 dir, vec3 n, vec3 sun, bool has_sun) {
	vec3 up = normalize(planet_axis);
	// Surface coordinates: the normal, turned with the planet.
	vec3 s = rotate_about(n, up, planet_spin) + planet_seed * 7.13;
	float latitude = abs(dot(n, up));

	// Continents: warped noise above a sea level set by land_amount.
	vec3 q = s * continent_scale;
	vec3 warp = vec3(fbm(q * 1.7 + 1.3), fbm(q * 1.7 + 5.1), fbm(q * 1.7 + 9.7)) - 0.5;
	float height = fbm6(q + warp * 1.2);
	float sea = mix(0.62, 0.38, land_amount);
	float land = smoothstep(sea - 0.004, sea + 0.004, height);
	vec3 ocean = mix(ocean_deep, ocean_shallow, smoothstep(sea - 0.09, sea, height));
	vec3 ground = mix(land_low, land_high, smoothstep(sea + 0.04, sea + 0.2, height));
	vec3 albedo = mix(ocean, ground, land);
	float ice = smoothstep(ice_latitude, ice_latitude + 0.03, latitude + (fbm(s * 6.0) - 0.5) * 0.12);
	albedo = mix(albedo, ice_color, ice);

	// Clouds: streaked along the latitude lines, like weather bands.
	vec3 cq = s * 3.0 + up * dot(s, up) * 2.5 + warp * 2.0;
	float cloud_edge = 1.0 - cloud_amount * 0.7;
	float cloud = smoothstep(cloud_edge, cloud_edge + 0.05, fbm6(cq + 21.0));
	albedo = mix(albedo, cloud_color, cloud * 0.9);

	// Daylight with a soft terminator; without a sun the planet is evenly lit.
	float ndl = has_sun ? dot(n, sun) : 1.0;
	float day = smoothstep(-0.03, 0.12, ndl);
	vec3 col = albedo * (night_brightness + day * (1.0 - night_brightness)) * planet_brightness;

	// Sun glint on open water.
	vec3 to_eye = -dir;
	float glint = pow(max(dot(reflect(-sun, n), to_eye), 0.0), 400.0) * (1.0 - land) * (1.0 - cloud);
	col += vec3(1.0, 0.95, 0.85) * glint * 0.5 * float(has_sun);

	// Cities on the night side, clustered by a second noise.
	float cell = hash13(floor(s * 160.0));
	float cluster = smoothstep(0.55, 0.75, fbm(s * 9.0 + 3.0));
	float lights = step(0.86, cell) * cluster * land * (1.0 - ice) * (1.0 - cloud * 0.8);
	col += city_light_color * lights * city_light_strength * (1.0 - smoothstep(-0.15, 0.05, ndl));

	// Atmosphere thickening towards the rim, on the lit side.
	float rim = pow(1.0 - max(dot(n, to_eye), 0.0), 3.0);
	col = mix(col, atmosphere_color * planet_brightness, rim * 0.7 * smoothstep(-0.3, 0.4, ndl));
	return col;
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

	if (planet_enabled) {
		vec3 centre = normalize(planet_direction);
		float radius = radians(planet_angular_radius);
		float angle = acos(clamp(dot(dir, centre), -1.0, 1.0));
		vec3 sun = LIGHT0_ENABLED ? LIGHT0_DIRECTION : vec3(0.0);
		// A pixel's worth of angle, for an antialiased edge.
		float aa = max(fwidth(angle), 1e-4);
		if (angle < radius + aa) {
			// Ray against a sphere one unit away whose edge is `radius` off-centre.
			float r = sin(radius);
			float b = dot(dir, centre);
			float t = b - sqrt(max(b * b - (1.0 - r * r), 0.0));
			vec3 n = normalize(dir * t - centre);
			float cover = 1.0 - smoothstep(radius - aa, radius + aa, angle);
			col = mix(col, planet_surface(dir, n, sun, LIGHT0_ENABLED), cover);
		}
		// Glow beyond the edge, bright on the sun's side and fading outwards.
		float outside = (angle - radius) / max(radius * atmosphere_width, 1e-4);
		if (outside > 0.0 && outside < 1.0) {
			vec3 limb = normalize(dir - centre * dot(dir, centre));
			float lit = LIGHT0_ENABLED ? smoothstep(-0.5, 0.6, dot(limb, sun)) : 1.0;
			col += atmosphere_color * atmosphere_strength * pow(1.0 - outside, 2.5) * lit * planet_brightness;
		}
	}

	COLOR = col;
}
