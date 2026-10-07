shader_type spatial;

// The planet ground (Terrain), cel-shaded with its colour chosen per pixel
// rather than per triangle: sand near the water, rock on steep slopes, snow up
// high, light and dark grass in broad patches, paved where the map says so.
// Every boundary is a hard edge (the cel look) made ragged by world-space
// noise, so none of them follow the mesh's 25 m triangles. The mesh has smooth
// normals, so the light bands follow the shape of the land (rock can be lit
// partly per triangle instead, `rock_facets`).
//
// Terrain sets the colours, thresholds and paint map from its own exports
// (Terrain._feed_ground()); the rest here is tuned on the material.

#include "res://effects/toon_light.gdshaderinc"
#include "res://effects/noise.gdshaderinc"

group_uniforms colours;
// Set by Terrain (its Colours exports).
uniform vec4 sand_color : source_color = vec4(0.86, 0.79, 0.55, 1.0);
uniform vec4 grass_color : source_color = vec4(0.42, 0.66, 0.3, 1.0);
uniform vec4 grass_dark_color : source_color = vec4(0.3, 0.52, 0.24, 1.0);
uniform vec4 rock_color : source_color = vec4(0.5, 0.47, 0.44, 1.0);
uniform vec4 snow_color : source_color = vec4(0.94, 0.96, 1.0, 1.0);
uniform vec4 paved_color : source_color = vec4(0.55, 0.55, 0.58, 1.0);
uniform float sea_level = 0.0;
// Sand below this many metres above sea level, snow above `snow_height`.
uniform float sand_height = 6.0;
uniform float snow_height = 260.0;
// Rock where the normal's up component is below this.
uniform float rock_slope = 0.78;
group_uniforms;

group_uniforms paint;
// Set by Terrain from its map: one texel per map cell, 1 where paved. Linear
// filtering rounds the corners of the paved areas instead of stepping round
// each cell. `paint_grid` is (x, z of the grid's corner, cell size, cells).
uniform sampler2D paint_map : filter_linear, repeat_disable;
uniform vec4 paint_grid = vec4(0.0, 0.0, 1.0, 1.0);
uniform bool has_paint = false;
group_uniforms;

group_uniforms patches;
// Size (metres) of the light and dark grass patches.
uniform float patch_scale = 350.0;
// Higher = less dark grass (the noise is mostly 0.15 to 0.85).
uniform float patch_threshold = 0.55;
// Small patches a shade lighter or darker, to break up large areas of one
// colour near the camera: how much brighter/darker, and their size (metres).
uniform float mottle : hint_range(0.0, 0.3) = 0.04;
uniform float mottle_scale = 60.0;
group_uniforms;

group_uniforms boundaries;
// Size (metres) of the wiggles along every boundary.
uniform float edge_scale = 40.0;
// How far the wiggles move each boundary: metres of height for the beach and
// snow lines, normal's up component for rock, paint value (0..1) for paving.
uniform float sand_wobble = 2.5;
uniform float snow_wobble = 30.0;
uniform float slope_wobble = 0.06;
uniform float paint_wobble = 0.15;
// How faceted rock is lit: 0 smooth like the grass, 1 flat per triangle. Off
// by default: from about 0.2 the light bands step round single triangles,
// saw-toothed, where they cross a slope.
uniform float rock_facets : hint_range(0.0, 1.0) = 0.0;
group_uniforms;

group_uniforms textures;
// Optional hand-drawn detail, greyscale, multiplied with the colours above
// (white, the default, changes nothing). Grass is projected from above, rock
// from three sides so it doesn't stretch down cliffs. Scales are metres per
// repeat.
uniform sampler2D grass_texture : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float grass_texture_scale = 20.0;
uniform sampler2D rock_texture : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float rock_texture_scale = 30.0;
group_uniforms;

varying vec3 world_position;
varying vec3 world_normal;

void vertex() {
	world_position = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	world_normal = (MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz;
}

// Hard edge, blended over about one pixel.
float aa_step(float edge, float x) {
	float w = max(fwidth(x), 0.0005);
	return smoothstep(edge - w, edge + w, x);
}

// A texture projected along the three world axes, blended by the normal.
vec3 triplanar(sampler2D tex, vec3 p, vec3 n) {
	vec3 w = pow(abs(n), vec3(4.0));
	w /= w.x + w.y + w.z;
	return texture(tex, p.zy).rgb * w.x + texture(tex, p.xz).rgb * w.y + texture(tex, p.xy).rgb * w.z;
}

void fragment() {
	vec3 n = normalize(world_normal);
	vec2 xz = world_position.xz;
	float above = world_position.y - sea_level;
	// One noise (-1..1) shifts every boundary, so they wiggle together.
	float wobble = noise2(xz / edge_scale) * 2.0 - 1.0;

	float dark = aa_step(patch_threshold, noise2(xz / patch_scale));
	vec3 color = mix(grass_color.rgb, grass_dark_color.rgb, dark);
	color *= 1.0 + mottle * (aa_step(0.5, noise(xz / mottle_scale + 17.0)) * 2.0 - 1.0);
	color *= texture(grass_texture, xz / grass_texture_scale).rgb;

	// Layered in order of priority, as Terrain used to choose per face:
	// paving over sand over rock over snow over grass.
	color = mix(color, snow_color.rgb, aa_step(snow_height, above + wobble * snow_wobble));
	float rock = 1.0 - aa_step(rock_slope, n.y + wobble * slope_wobble);
	vec3 rock_albedo = rock_color.rgb * triplanar(rock_texture, world_position / rock_texture_scale, n);
	color = mix(color, rock_albedo, rock);
	color = mix(color, sand_color.rgb, 1.0 - aa_step(sand_height, above + wobble * sand_wobble));
	vec2 uv = (xz - paint_grid.xy) / (paint_grid.z * paint_grid.w);
	// Only on the map: the backdrop beyond it would get the edge cells' paint.
	if (has_paint && uv == clamp(uv, 0.0, 1.0)) {
		float paved = texture(paint_map, uv).r;
		color = mix(color, paved_color.rgb, aa_step(0.5, paved + wobble * paint_wobble));
	}
	ALBEDO = color;

	// Rock lit partly by its triangle's own (flat) normal: crags, not dunes.
	vec3 flat_normal = normalize(cross(dFdx(VERTEX), dFdy(VERTEX)));
	if (dot(flat_normal, NORMAL) < 0.0) {
		flat_normal = -flat_normal;
	}
	NORMAL = normalize(mix(NORMAL, flat_normal, rock * rock_facets));
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
}
