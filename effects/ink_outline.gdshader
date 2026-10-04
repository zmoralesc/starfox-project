shader_type spatial;
render_mode unshaded, depth_draw_never, depth_test_disabled, cull_disabled, shadows_disabled, fog_disabled;

// Screen-space ink outlines for the cel-shaded look. Drawn on a quad that
// covers the screen (see InkOutline). Finds edges by comparing each pixel's
// depth and normal with its neighbours: a depth jump draws the silhouette,
// a normal change draws creases between panels.
// Only opaque geometry is outlined; transparent things (lasers, explosions,
// shields, space dust, a destroyer that is still fading in) never write depth,
// so they are left alone.

uniform sampler2D depth_tex : hint_depth_texture, filter_nearest;
uniform sampler2D normal_tex : hint_normal_roughness_texture, filter_nearest;

uniform vec4 ink_color : source_color = vec4(0.01, 0.01, 0.03, 1.0);
// Line width in pixels at 720p; scaled with the screen height.
uniform float thickness = 1.0;
// Relative depth jump that counts as an edge (0.05 = 5%).
uniform float depth_threshold = 0.05;
// How different two normals must be to draw a crease (1 - cosine).
uniform float normal_threshold = 0.4;
// Lines fade out with distance, so far-away ships stay readable instead of
// turning into black specks.
uniform float fade_start = 220.0;
uniform float fade_end = 520.0;

void vertex() {
	POSITION = vec4(VERTEX.xy, 1.0, 1.0);
}

float linear_depth(vec2 uv, mat4 inv_projection) {
	float d = texture(depth_tex, uv).r;
	vec4 view = inv_projection * vec4(uv * 2.0 - 1.0, d, 1.0);
	return -view.z / view.w;
}

vec3 normal_at(vec2 uv) {
	return texture(normal_tex, uv).xyz * 2.0 - 1.0;
}

void fragment() {
	vec2 px = thickness * (VIEWPORT_SIZE.y / 720.0) / VIEWPORT_SIZE;
	vec2 offsets[4] = { vec2(px.x, 0.0), vec2(-px.x, 0.0), vec2(0.0, px.y), vec2(0.0, -px.y) };

	float center = linear_depth(SCREEN_UV, INV_PROJECTION_MATRIX);
	vec3 n = normal_at(SCREEN_UV);
	float nearest = center;
	float edge = 0.0;
	for (int i = 0; i < 4; i++) {
		vec2 uv = SCREEN_UV + offsets[i];
		float d = linear_depth(uv, INV_PROJECTION_MATRIX);
		// Only the nearer side of a depth jump draws, so lines sit on the
		// object's silhouette rather than on whatever is behind it.
		if (center - d > depth_threshold * d) {
			edge = 1.0;
			nearest = min(nearest, d);
		} else if (abs(center - d) < depth_threshold * center
				&& 1.0 - dot(n, normal_at(uv)) > normal_threshold) {
			edge = 1.0;
		}
	}
	float fade = 1.0 - smoothstep(fade_start, fade_end, nearest);
	ALBEDO = ink_color.rgb;
	ALPHA = edge * fade * ink_color.a;
}
