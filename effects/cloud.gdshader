shader_type spatial;
render_mode cull_back, depth_draw_always;

// Cartoon clouds (Clouds, world/clouds.gd): the squashed sphere blobs of each
// cluster are pushed in and out by slowly drifting noise, so they read as
// billowing lumps rather than smooth ellipsoids, and the normals are bent with
// the lumps so each one catches the light. Lit in cel bands of their own: a
// white top, a pale blue middle and a soft blue-grey underside (the generic
// toon shadow made them look grey and dirty), a rim on the lit side and a
// silver lining when the sun is behind them; flattened, shaded bottoms.
// No ink outlines: writing ALPHA (always 1) puts them in the transparent
// pass, after the outline quad and out of the depth texture it reads, so they
// are soft white shapes against the sky and cover the lines of whatever is
// behind them. depth_draw_always still writes depth there, so the blobs of a
// cluster hide each other properly. Clouds fades a cluster out
// (transparency) when the camera is close.
// Everything below is in the cluster's own space (metres at scale 1), so a
// cluster Clouds scales up is the same cloud, bigger: lumps, their height and
// the flat base all grow with it.

// Lump size (metres between bumps) and how far they push in and out (metres).
uniform float lump_scale = 16.0;
uniform float lump_height = 12.0;
// How strongly the lumps bend the normals (shading across each lump).
uniform float lump_shading = 0.5;
// How fast the lumps drift and churn (metres per second, through the noise).
uniform vec3 drift = vec3(1.2, 0.35, 0.6);
// Flattened bottoms: anything more than this far below the cluster's centre
// (metres, in its own space) is squashed to `base_squash` of its depth, so
// the underside is a broad, gently lumpy base in the shade band, like a
// cartoon cloud's. Pressing it fully flat (0) looked like a sheet of glass
// under every cloud. Negative flat_base = off.
uniform float flat_base = 8.0;
uniform float base_squash : hint_range(0.0, 1.0) = 0.3;
// Crevices on the underside: faces turned downwards more than `crevice_from`
// (0 = sideways, 1 = straight down) shade towards `crevice_color` in the
// hollows between lumps, fading from full below `crevice_threshold` minus
// `crevice_softness` (0..1 noise) to none above it plus `crevice_softness`.
// A gradient, so the hollows read as rounded bulges (a hard band drew
// blotches like a cow's spots).
uniform vec4 crevice_color : source_color = vec4(0.72, 0.78, 0.92, 1.0);
uniform float crevice_threshold : hint_range(0.0, 1.0) = 0.45;
uniform float crevice_softness : hint_range(0.0, 0.5) = 0.2;
uniform float crevice_from : hint_range(0.0, 1.0) = 0.2;

// Colours of the three bands, from the sunlit top down to the underside.
uniform vec4 lit_color : source_color = vec4(1.0, 1.0, 1.0, 1.0);
uniform vec4 mid_color : source_color = vec4(0.86, 0.9, 0.98, 1.0);
uniform vec4 shade_color : source_color = vec4(0.56, 0.64, 0.83, 1.0);
// Where the bands split, on the N·L (times shadow) scale.
uniform float mid_threshold : hint_range(0.0, 1.0) = 0.12;
uniform float lit_threshold : hint_range(0.0, 1.0) = 0.65;
// Thin light rim on the lit side of the silhouette.
uniform float rim : hint_range(0.0, 1.0) = 0.25;
// Bright edge when the sun is behind the cloud.
uniform float silver : hint_range(0.0, 2.0) = 0.6;

// Integer hash (float hashes break into straight seams at world-scale
// coordinates; see world/space_sky.gdshader).
float corner_hash(vec3 p) {
	uvec3 q = uvec3(ivec3(floor(p + 0.5)));
	uint n = q.x * 1597334673u ^ q.y * 3812015801u ^ q.z * 2798796415u;
	n = (n ^ (n >> 15u)) * 2246822519u;
	n ^= n >> 13u;
	return float(n) * (1.0 / 4294967295.0);
}

float value_noise(vec3 p) {
	vec3 i = floor(p);
	vec3 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(
		mix(mix(corner_hash(i + vec3(0, 0, 0)), corner_hash(i + vec3(1, 0, 0)), f.x),
			mix(corner_hash(i + vec3(0, 1, 0)), corner_hash(i + vec3(1, 1, 0)), f.x), f.y),
		mix(mix(corner_hash(i + vec3(0, 0, 1)), corner_hash(i + vec3(1, 0, 1)), f.x),
			mix(corner_hash(i + vec3(0, 1, 1)), corner_hash(i + vec3(1, 1, 1)), f.x), f.y),
		f.z);
}

// Lumps: big bumps with smaller ones on top, 0..1.
float lumps(vec3 world) {
	vec3 p = world / lump_scale;
	return value_noise(p) * 0.8 + value_noise(p * 2.3 + 17.0) * 0.2;
}

// Anti-aliased step: hard edge, but blended over about one pixel.
float band(float edge, float x) {
	float w = max(fwidth(x), 0.002);
	return smoothstep(edge - w, edge + w, x);
}

// Where the lumps are sampled (the cluster's own space, shifted by where it is
// so no two clusters share a pattern, plus drift, before the push), the blob's
// own smooth normal (cluster space), and 1 on the flat base.
varying vec3 v_lump_pos;
varying vec3 v_blob_normal;
varying float v_base;

void vertex() {
	v_lump_pos = VERTEX + NODE_POSITION_WORLD + drift * TIME;
	v_blob_normal = NORMAL;
	// Mostly outward, so the blobs swell into lumps rather than shrink.
	VERTEX += NORMAL * (lumps(v_lump_pos) - 0.3) * lump_height;
	v_base = 0.0;
	if (flat_base >= 0.0 && VERTEX.y < -flat_base) {
		VERTEX.y = -flat_base + (VERTEX.y + flat_base) * base_squash;
		v_base = 1.0;
	}
}

void fragment() {
	ALBEDO = vec3(1.0);
	// Using ALPHA puts the clouds in the transparent pass: no ink outlines
	// (see the top). Multiply, never assign: ALPHA starts at 1 - the node's
	// `transparency`, which is how Clouds fades a cluster near the camera
	// (ALPHA = 1.0 overwrote it and the clouds stayed solid).
	ALPHA *= 1.0;
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
	// Bend the normal down the lump's slope (finite differences of the
	// noise), per pixel: per vertex, the bands followed the sphere's
	// triangles in angular patches.
	vec3 blob = normalize(v_blob_normal);
	float h = lumps(v_lump_pos);
	float e = lump_scale * 0.2;
	vec3 grad = vec3(lumps(v_lump_pos + vec3(e, 0, 0)) - h, lumps(v_lump_pos + vec3(0, e, 0)) - h,
		lumps(v_lump_pos + vec3(0, 0, e)) - h) / e;
	vec3 n = normalize(blob - (grad - blob * dot(grad, blob)) * lump_height * lump_shading);
	// On the squashed base, squash the normal the same way (dividing its y by
	// base_squash): it turns mostly downwards, into the shade, but keeps the
	// lumps, so the underside reads as low rounded bulges rather than a sheet.
	n = normalize(mix(n, vec3(n.x, n.y / max(base_squash, 0.001), n.z), v_base));
	// Clusters are scaled evenly, so the model matrix keeps normals' directions.
	vec3 world_n = normalize(mat3(MODEL_MATRIX) * n);
	NORMAL = normalize((VIEW_MATRIX * vec4(world_n, 0.0)).xyz);
	// Crevices: on the faces turned downwards (all in the shade, sun or not,
	// so one even tone that read as a flat sheet from below), the hollows
	// between lumps get a darker band, which draws the lumps on the underside.
	float down = smoothstep(crevice_from, 1.0, -world_n.y);
	float hollow = 1.0 - smoothstep(crevice_threshold - crevice_softness, crevice_threshold + crevice_softness, h);
	ALBEDO = mix(ALBEDO, crevice_color.rgb, hollow * down);
}

void light() {
	float ndl = clamp(dot(NORMAL, LIGHT), 0.0, 1.0) * ATTENUATION;
	if (!LIGHT_IS_DIRECTIONAL) {
		// Explosions and other lights nearby: a plain banded glow.
		DIFFUSE_LIGHT += band(mid_threshold, ndl) * LIGHT_COLOR / PI;
	} else {
		vec3 tone = mix(shade_color.rgb, mid_color.rgb, band(mid_threshold, ndl));
		tone = mix(tone, lit_color.rgb, band(lit_threshold, ndl));
		DIFFUSE_LIGHT += tone * LIGHT_COLOR / PI;
		float facing = 1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0);
		DIFFUSE_LIGHT += rim * band(0.72, facing) * band(mid_threshold, ndl) * LIGHT_COLOR / PI;
		// Silver lining: the edge glows where we look towards the sun through it.
		float behind = clamp(dot(-VIEW, LIGHT), 0.0, 1.0);
		DIFFUSE_LIGHT += silver * band(0.6, facing) * behind * behind * LIGHT_COLOR / PI;
	}
}
