shader_type spatial;
render_mode unshaded, depth_draw_never, depth_test_disabled, cull_disabled, shadows_disabled, fog_disabled;

// Screen-space ink outlines for the cel-shaded look. Drawn on a quad that
// covers the screen (see InkOutline). Finds edges by comparing each pixel's
// depth and normal with its neighbours: a depth jump draws the silhouette,
// a normal change draws creases between panels (at crease_strength).
// Lines are a darkened copy of the colour of the object they outline
// (ink_from_scene), so they read as a deeper shade of it rather than black ink.
// Only opaque geometry is outlined; transparent things (lasers, explosions,
// shields, space dust, a destroyer that is still fading in) never write depth,
// so they are left alone.

uniform sampler2D depth_tex : hint_depth_texture, filter_nearest;
uniform sampler2D normal_tex : hint_normal_roughness_texture, filter_nearest;
uniform sampler2D screen_tex : hint_screen_texture, filter_nearest;

// Line colour where it isn't taken from the scene; alpha = line opacity.
uniform vec4 ink_color : source_color = vec4(0.01, 0.01, 0.03, 0.9);
// 0 = lines are ink_color, 1 = the outlined object's own colour times ink_shade.
uniform float ink_from_scene : hint_range(0.0, 1.0) = 0.8;
// How dark the scene-coloured lines are (fraction of the object's colour).
uniform float ink_shade : hint_range(0.0, 1.0) = 0.3;
// Line width in pixels at 720p; scaled with the screen height.
uniform float thickness = 1.0;
// Relative depth jump that counts as an edge (0.05 = 5%).
uniform float depth_threshold = 0.05;
// How different two normals must be to draw a crease (1 - cosine).
uniform float normal_threshold = 0.4;
// Opacity of crease lines next to silhouettes: 0 = silhouettes only.
uniform float crease_strength : hint_range(0.0, 1.0) = 0.0;
// Lines fade out with distance, so far-away ships stay readable instead of
// turning into dark specks, and distant scenery is drawn by colour alone.
uniform float fade_start = 150.0;
uniform float fade_end = 400.0;

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
	// Where the outlined object's colour is read: the nearer neighbour for a
	// silhouette (this pixel is the background behind it), here for a crease.
	vec2 object_uv = SCREEN_UV;
	float edge = 0.0;
	for (int i = 0; i < 4; i++) {
		vec2 uv = SCREEN_UV + offsets[i];
		float d = linear_depth(uv, INV_PROJECTION_MATRIX);
		// Only the nearer side of a depth jump draws, so lines sit on the
		// object's silhouette rather than on whatever is behind it.
		if (center - d > depth_threshold * d) {
			edge = 1.0;
			if (d < nearest) {
				nearest = d;
				object_uv = uv;
			}
		} else if (abs(center - d) < depth_threshold * center
				&& 1.0 - dot(n, normal_at(uv)) > normal_threshold) {
			edge = max(edge, crease_strength);
		}
	}
	float fade = 1.0 - smoothstep(fade_start, fade_end, nearest);
	vec3 scene_ink = texture(screen_tex, object_uv).rgb * ink_shade;
	ALBEDO = mix(ink_color.rgb, scene_ink, ink_from_scene);
	ALPHA = edge * fade * ink_color.a;
}
