shader_type spatial;
render_mode depth_draw_always;

// Frozen lakes (Fichina): the water plane and the map's high water drawn as
// ice. Use it as Terrain's water_material with Terrain.frozen_water on (no
// splashes, wakes or foam rings; bolts spark on it like on ground).
//
// - Colour by depth (the same height texture Terrain gives the water shader,
//   Terrain._feed_water()): white-dusted ice in the shallows and along the
//   shores, clear blue ice over deeper water, a darker blue over the deepest.
// - Cracks: a fine network (Voronoi cell edges) and a coarse one of pressure
//   cracks, drawn as thin dark-blue lines with a pale edge, fading out where
//   they'd get finer than a few pixels.
// - Snow: drifted patches with ragged edges.
// - Lit by the shared toon light model, with a glint for the low sun.
//
// No ink outlines, like the water: ALPHA (always 1, `ALPHA *= 1.0`) puts it
// in the transparent pass, after the outline quad and out of the depth
// texture the outlines read; depth_draw_always still writes depth there.

#define TOON_NO_BACK_RIM
#include "res://effects/toon_light.gdshaderinc"
#include "res://effects/noise.gdshaderinc"

group_uniforms colour;
uniform vec4 shallow_color : source_color = vec4(0.84, 0.91, 0.97, 1.0);
uniform vec4 ice_color : source_color = vec4(0.55, 0.77, 0.93, 1.0);
uniform vec4 deep_color : source_color = vec4(0.33, 0.56, 0.82, 1.0);
// Depths (metres of water under the ice) where ice_color and then
// deep_color take over, and how gradually.
uniform float mid_depth = 2.5;
uniform float deep_depth = 14.0;
uniform float depth_blend = 3.0;
// Ragged band edges: how far (metres of depth) noise shifts them.
uniform float depth_wobble = 2.5;
group_uniforms;

group_uniforms cracks;
uniform vec4 crack_color : source_color = vec4(0.2, 0.38, 0.62, 1.0);
uniform vec4 crack_edge_color : source_color = vec4(0.92, 0.96, 1.0, 1.0);
// Cell size of the fine and the coarse networks (metres), and line widths.
uniform float fine_scale = 26.0;
uniform float coarse_scale = 150.0;
uniform float fine_width = 0.35;
uniform float coarse_width = 0.9;
// How strongly each network shows (0..1).
uniform float fine_strength : hint_range(0.0, 1.0) = 0.55;
uniform float coarse_strength : hint_range(0.0, 1.0) = 0.9;
group_uniforms;

group_uniforms snow;
uniform vec4 snow_color : source_color = vec4(0.93, 0.95, 0.99, 1.0);
// Drift patches: noise size (metres) and the share of the ice they cover.
uniform float drift_scale = 170.0;
uniform float drift_cover : hint_range(0.0, 1.0) = 0.16;
// Snow lies over shallow ice: the depth under which it's all white.
uniform float shore_snow_depth = 0.6;
group_uniforms;

group_uniforms ground;
uniform sampler2D ground_heights : filter_linear, repeat_disable;
uniform vec4 ground_grid = vec4(0.0, 0.0, 1.0, 1.0);
uniform bool has_ground = false;
uniform float open_depth = 100.0;
group_uniforms;

varying vec3 world_position;

void vertex() {
	world_position = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

float water_depth(vec3 world) {
	if (!has_ground) {
		return open_depth;
	}
	vec2 cell = (world.xz - ground_grid.xy) / ground_grid.z;
	if (any(lessThan(cell, vec2(0.0))) || any(greaterThan(cell, vec2(ground_grid.w - 1.0)))) {
		return open_depth;
	}
	vec2 uv = (cell + 0.5) / ground_grid.w;
	return world.y - texture(ground_heights, uv).r;
}

// Distance (in cells) to the nearest Voronoi cell edge: second-nearest
// minus nearest feature point, which is about twice the distance to the edge.
float cell_edge(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	float d1 = 8.0;
	float d2 = 8.0;
	for (int y = -1; y <= 1; y++) {
		for (int x = -1; x <= 1; x++) {
			vec2 g = vec2(float(x), float(y));
			vec2 o = vec2(hash(i + g), hash(i + g + vec2(37.0, 91.0)));
			float d = length(g + 0.15 + 0.7 * o - f);
			if (d < d1) {
				d2 = d1;
				d1 = d;
			} else if (d < d2) {
				d2 = d;
			}
		}
	}
	return (d2 - d1) * 0.5;
}

// A crack line (0..1) of `width` metres in a network of cells `scale` metres,
// with a pale edge either side; faded where a line would be under ~1.5 px.
vec2 crack(vec2 xz, float scale, float width, float px) {
	// Bend the network so its edges aren't straight.
	vec2 p = xz / scale + (vec2(noise(xz / (scale * 0.7)), noise(xz / (scale * 0.7) + 13.0)) - 0.5) * 0.6;
	float d = cell_edge(p) * scale;
	float w = max(px, 0.0001);
	float line = 1.0 - smoothstep(width - w, width + w, d);
	float edge = 1.0 - smoothstep(width * 2.5 - w, width * 2.5 + w, d);
	float fade = 1.0 - smoothstep(width * 0.5, width * 1.5, px);
	return vec2(line, max(edge - line, 0.0)) * fade;
}

void fragment() {
	vec2 xz = world_position.xz;
	// Metres per pixel here, for fading fine detail out.
	float px = length(fwidth(xz));
	float wobble = noise2(xz / 40.0) * 2.0 - 1.0;
	float depth = water_depth(world_position) + wobble * depth_wobble;

	vec3 color = mix(shallow_color.rgb, ice_color.rgb, smoothstep(mid_depth - depth_blend * 0.5, mid_depth + depth_blend * 0.5, depth));
	color = mix(color, deep_color.rgb, smoothstep(deep_depth - depth_blend, deep_depth + depth_blend, depth));
	// A slow mottle so a big lake isn't one flat tone.
	color *= 0.94 + 0.12 * noise(xz / 220.0);

	vec2 fine = crack(xz, fine_scale, fine_width, px) * fine_strength;
	vec2 coarse = crack(xz + 31.0, coarse_scale, coarse_width, px) * coarse_strength;
	color = mix(color, crack_edge_color.rgb, max(fine.y, coarse.y) * 0.5);
	color = mix(color, crack_color.rgb, max(fine.x, coarse.x));

	// Snow: drifts, and the shallows near the shores.
	float drift = noise2(xz / drift_scale + 3.7) + (noise(xz / 9.0) - 0.5) * 0.08;
	float snow = smoothstep(1.0 - drift_cover - 0.01, 1.0 - drift_cover + 0.01, drift);
	snow = max(snow, 1.0 - smoothstep(shore_snow_depth - 0.3, shore_snow_depth + 0.3, depth));
	color = mix(color, snow_color.rgb, snow);

	ALBEDO = color;
	ALPHA *= 1.0;
	ROUGHNESS = 0.4;
	SPECULAR = 0.0;
}
