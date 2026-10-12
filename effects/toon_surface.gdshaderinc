// The toon surface (flat colour, optional colour texture and glow), shared by
// toon.gdshader, toon_clip.gdshader and toon_unlined.gdshader. Define TOON_CLIP
// before including it to add a clip plane (see toon_clip.gdshader), or
// TOON_UNLINED to draw it in the transparent pass, without ink outlines (see
// toon_unlined.gdshader). TOON_WEAR adds worn paint (see toon_worn.gdshader).
// The clip plane also glows where the surface meets it (the seam_* uniforms).
// TOON_INSTANCED corrects the normals of MultiMesh instances (see
// toon_instanced.gdshader), and TOON_FOLIAGE rounds off faceted trees (see
// toon_unlined_instanced.gdshader). TOON_DETAIL (with TOON_INSTANCED) draws
// the map kit's surface detail: windows, wall panels, roofing.

uniform vec4 albedo : source_color = vec4(0.8, 0.8, 0.8, 1.0);
// Multiplied with `albedo`. White (no change) when unset.
uniform sampler2D albedo_texture : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
// Glow, added on top of the lighting: emission colour × emission texture × energy.
uniform vec4 emission : source_color = vec4(0.0, 0.0, 0.0, 1.0);
uniform sampler2D emission_texture : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float emission_energy : hint_range(0.0, 16.0) = 1.0;
// Flash when hit (HitReaction): rgb the colour, a how much (0 = none). Per
// instance, so every shot target flashes on its own with shared materials. It
// glows rather than tints, so it reads on the shadow side too. Not on
// instanced map props (TOON_INSTANCED): scenery never flashes, and Godot
// reserves 16 slots of the global shader buffer (rendering/limits/
// global_shader_variables/buffer_size, 4096 instances by default) for every
// instance whose material has an instance uniform; Corneria has ~5,800 of them.
#ifndef TOON_INSTANCED
instance uniform vec4 hit_flash = vec4(0.0);
#endif

#ifdef TOON_INSTANCED
// Glow strength that vertex alpha 0 stands for (export_corneria.py's KIT_GLOW).
uniform float vertex_glow_energy = 8.0;
#endif

#ifdef TOON_FOLIAGE
// How far faceted foliage (7- or 8-sided cones and lumps, built round the
// piece's vertical axis) shades as if round: 0 = flat facets, 1 = each normal
// turned to point straight out from the trunk, keeping its facet's slope. Flat
// bases (normals straight down) are unchanged.
uniform float foliage_round : hint_range(0.0, 1.0) = 1.0;
// Metres from the axis inside which the rounding fades out (the pines' tips
// lean up to 0.3 m off it).
uniform float foliage_axis_margin = 0.8;
#endif

#if defined(TOON_CLIP) || defined(TOON_WEAR) || defined(TOON_DETAIL)
#include "res://effects/noise.gdshaderinc"
#endif

#ifdef TOON_DETAIL
// Surface detail on the map kit (Corneria's and Fichina's buildings), drawn
// here rather than modelled or textured: the pieces have no texture UVs, and
// their faces are flat palette colours (vertex colours). The export tags each
// face with its kind of surface in UV.x (export_corneria.py's bake_palette(),
// from the map's SURFACES): 0 none, 1 glass, 2 wall panels, 3 metal roofing,
// 4 roof tiles. Patterns are laid out in metres on the piece as placed (its
// own x and z times the instance's stretch, and world height, so a tower's
// stacked parts carry on each other's storeys), so a storey is the same height
// on every building however its piece was stretched. Every pattern fades to
// its average colour once it's finer than a few pixels: far towers keep the
// tone of their windows without shimmering.
const float SURFACE_GLASS = 1.0;
const float SURFACE_WALL = 2.0;
const float SURFACE_METAL = 3.0;
const float SURFACE_TILES = 4.0;

group_uniforms windows;
// Height of a storey, which sets the window rows and the wall panels (m).
uniform float storey_height = 3.6;
// Width of a window pane (m).
uniform float pane_width = 2.4;
// Half-width of the frames between panes, and of the band between storeys (m).
uniform float frame_width = 0.1;
uniform float spandrel_width = 0.3;
uniform vec4 frame_color : source_color = vec4(0.82, 0.85, 0.9, 1.0);
// How far the frames go from the glass's colour to `frame_color`.
uniform float frame_amount : hint_range(0.0, 1.0) = 0.85;
// Sky seen in the glass: brighter where the glass reflects the sky (seen from
// below or level) and at glancing angles; the ground's darker shade from above.
uniform vec4 reflect_sky_color : source_color = vec4(0.78, 0.88, 1.0, 1.0);
uniform float reflect_amount : hint_range(0.0, 1.0) = 0.3;
// Panes lighter at the top than the bottom (a stylised sheen), and varying in
// shade from pane to pane (blinds, tint).
uniform float pane_sheen : hint_range(0.0, 1.0) = 0.25;
uniform float pane_variation : hint_range(0.0, 1.0) = 0.15;
// Share of panes lit from inside (0 none), their colour and glow.
uniform float lit_windows : hint_range(0.0, 1.0) = 0.0;
uniform vec4 lit_window_color : source_color = vec4(1.0, 0.82, 0.55, 1.0);
uniform float lit_window_energy = 2.5;
// How much a glowing glass colour's panes vary in brightness (0 all alike).
uniform float lit_pane_variation : hint_range(0.0, 1.0) = 0.45;
group_uniforms walls;
// Wall panels: seams between panels `panel_width` wide and a storey high,
// darkened by `panel_seam` (the vertical ones half as much); each panel's
// shade varies by `panel_variation`; large blotches (`mottle_size` m) of
// weathering by `wall_mottle`.
uniform float panel_width = 3.0;
uniform float seam_width_m = 0.06;
uniform float panel_seam : hint_range(0.0, 1.0) = 0.08;
uniform float panel_variation : hint_range(0.0, 1.0) = 0.04;
uniform float mottle_size = 14.0;
uniform float wall_mottle : hint_range(0.0, 1.0) = 0.06;
group_uniforms roofs;
// Metal roofing: standing seams every `metal_seam_spacing` m.
uniform float metal_seam_spacing = 1.2;
uniform float metal_seam : hint_range(0.0, 1.0) = 0.12;
uniform float roof_mottle : hint_range(0.0, 1.0) = 0.1;
// Tiled roofs: rows `tile_row` m high (measured in height, so they run level
// along any slope), tiles `tile_width` wide, each row's lower edge darkened.
uniform float tile_row = 0.3;
uniform float tile_width = 0.35;
uniform float tile_shade : hint_range(0.0, 1.0) = 0.2;
group_uniforms;

// Position in metres (piece x and z as stretched, world y), the face's normal
// in that space, and a seed for the instance (where it stands), so identical
// pieces don't share their panes' shades and lit windows.
varying vec3 surface_pos;
varying vec3 surface_normal;
varying flat vec2 surface_seed;

// How much of a pattern repeating every `period` metres to keep at `px`
// metres per pixel: all of it while a period spans 6 pixels or more, none
// once it's down to 2.
float detail_keep(float period, float px) {
	return clamp(period / max(px, 1e-4) * 0.25 - 0.5, 0.0, 1.0);
}

// Lines at every whole multiple of `period` along x, `half_width` either side,
// antialiased (px metres per pixel) and faded to their average coverage when
// too fine to draw. 0 away from a line, 1 on one.
float grid_line(float x, float period, float half_width, float px) {
	float d = abs(fract(x / period + 0.5) - 0.5) * period;
	float line = 1.0 - smoothstep(half_width - px * 0.5, half_width + px * 0.5, d);
	float average = min(2.0 * half_width / period, 1.0);
	return mix(average, line, detail_keep(period, px));
}

// The surface's coordinates across a face, in metres: along the wall and up
// it for walls; x and z for flat roofs.
vec2 surface_coords(vec3 p, vec3 n) {
	if (abs(n.y) > 0.7) {
		return p.xz;
	}
	vec2 along = normalize(vec2(-n.z, n.x));
	return vec2(dot(p.xz, along), p.y);
}
#endif

#ifdef TOON_CLIP
// World-space plane (normal, distance): fragments behind it (dot(normal, p) <
// distance) aren't drawn. Per instance; the default (all zero) clips nothing.
instance uniform vec4 clip_plane = vec4(0.0);
varying vec3 world_position;
// The seam where the surface comes through the plane (the destroyer's warp
// portal): a band of portal energy, white-hot at the cut and fading to
// `seam_color` over `seam_width` metres, flickering and licking up the hull in
// tongues. The cut itself is ragged (it eats up to `seam_ragged` metres into
// the surface in front of the plane, never behind it), so the hull seems to
// form out of the energy rather than slide through a clean slice. Set per
// destroyer by Destroyer.seam_* (zero energy: a clean cut, no glow).
uniform vec4 seam_color : source_color = vec4(1.0, 0.3, 0.45, 1.0);
uniform vec4 seam_hot_color : source_color = vec4(1.0, 0.85, 0.9, 1.0);
uniform float seam_width = 45.0;
uniform float seam_energy = 5.0;
uniform float seam_ragged = 6.0;
// Size (m) of the flicker's tongues and ragged bites.
uniform float seam_scale = 14.0;
// How fast the energy churns.
uniform float seam_speed = 1.5;

// How far (m) in front of the cut `p` is, after the ragged bites (negative:
// cut away), and the seam's glow there (0 to 1). (0, 0) far from the plane.
// No glow when there's no plane (all zero).
vec2 clip_seam(vec3 p) {
	if (dot(clip_plane.xyz, clip_plane.xyz) < 0.5) {
		return vec2(1.0, 0.0);
	}
	float d = dot(clip_plane.xyz, p) - clip_plane.w;
	// Past the longest tongue (reach below is at most 1.35 × seam_width).
	if (d > seam_width * 1.4 + seam_ragged) {
		return vec2(d, 0.0);
	}
	// Noise laid out on the plane: across it and up it.
	vec3 across = normalize(cross(clip_plane.xyz, abs(clip_plane.y) < 0.9 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0)));
	vec3 up = cross(across, clip_plane.xyz);
	vec2 q = vec2(dot(p, across), dot(p, up)) / seam_scale;
	float t = TIME * seam_speed;
	float bite = noise2(q + vec2(t * 0.7, -t * 0.4));
	d -= seam_ragged * smoothstep(0.3, 0.8, bite);
	// Tongues: the band's reach varies along the cut and churns.
	float reach = seam_width * (0.45 + 0.9 * clamp(noise2(q * 0.6 - vec2(t * 0.3, t * 0.9)), 0.0, 1.0));
	// Falls off from the cut, then fades smoothly to exactly nothing at the
	// tongue's tip: the exponential alone still had a fifth of its brightness
	// where the band stopped, which showed as a hard edge.
	float x = max(d, 0.0) / max(reach, 0.01);
	float glow = exp(-x * 2.0) * (1.0 - smoothstep(0.35, 1.0, x));
	// Crackle: bright flecks dancing in the band.
	glow *= 0.7 + 0.6 * noise(q * 3.0 + vec2(-t * 2.3, t * 1.9));
	return vec2(d, clamp(glow, 0.0, 1.5));
}
#endif

#if defined(TOON_CLIP) || defined(TOON_INSTANCED) || defined(TOON_FOLIAGE)
void vertex() {
#ifdef TOON_CLIP
	world_position = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
#endif
#ifdef TOON_FOLIAGE
	// In the piece's own space, before the instance turns it. Neighbouring
	// facets share their edge vertices' positions, so they get the same
	// outward direction there and the shading runs on across the seam.
	// Near the axis (a cone's tip, leaning a little off it) the outward
	// direction means nothing, and every facet's tip would point the same way:
	// a bright or dark streak. Fade the rounding out there.
	vec2 out_dir = VERTEX.xz;
	float from_axis = length(out_dir);
	float round_amount = foliage_round * smoothstep(foliage_axis_margin * 0.5, foliage_axis_margin, from_axis);
	if (round_amount > 0.0) {
		vec3 round_normal = vec3(out_dir / from_axis * length(NORMAL.xz), NORMAL.y);
		NORMAL = normalize(mix(NORMAL, round_normal, round_amount));
	}
#endif
#ifdef TOON_INSTANCED
	// Godot turns a MultiMesh instance's normals by the instance's matrix M
	// itself, not its inverse transpose, so a non-uniformly scaled instance
	// (a stretched kit tower) gets its sloped faces' normals wrong. Pre-turned
	// by inverse(MᵀM), M then brings them to the inverse transpose's result.
	// MODEL_MATRIX includes the instance's transform here.
	mat3 m = mat3(MODEL_MATRIX);
#ifdef TOON_DETAIL
	// Before NORMAL is changed below: the piece's own normal, in metres.
	vec3 stretch = vec3(length(m[0]), length(m[1]), length(m[2]));
	surface_pos = vec3(VERTEX.x * stretch.x, (MODEL_MATRIX * vec4(VERTEX, 1.0)).y, VERTEX.z * stretch.z);
	surface_normal = NORMAL / stretch;
	surface_seed = floor(MODEL_MATRIX[3].xz * 0.37);
#endif
	NORMAL = inverse(transpose(m) * m) * NORMAL;
#endif
}
#endif

#ifdef TOON_DETAIL
// The glass: panes in frames, storey bands, sky reflected, a few lit from
// inside. `base` is the glass's palette colour. Returns the colour; adds any
// light from inside to `glow`. Glass that glows already (a palette colour
// with emission: Fichina's lit windows) is split into panes too: its glow
// varies pane to pane by `lit_pane_variation` and stops at the frames.
vec3 glass_detail(vec3 base, vec2 c, float px, vec3 view_normal, vec3 view_dir, mat4 inv_view, inout vec3 glow) {
	vec2 cell = floor(vec2(c.x / pane_width, c.y / storey_height));
	vec2 f = vec2(fract(c.x / pane_width), fract(c.y / storey_height));
	float r = hash(cell + surface_seed);
	float keep = detail_keep(min(pane_width, storey_height), px);
	// Shade per pane and the sheen up each pane, both faded out at range.
	float shade = 1.0 + ((r - 0.5) * 2.0 * pane_variation + (f.y - 0.5) * pane_sheen) * keep;
	vec3 colour = base * shade;
	// Sky in the glass: where the reflected ray points up, more at a glancing
	// angle.
	vec3 reflected = (inv_view * vec4(reflect(-view_dir, view_normal), 0.0)).xyz;
	float sky = smoothstep(-0.3, 0.6, reflected.y);
	float fresnel = pow(1.0 - clamp(dot(view_normal, view_dir), 0.0, 1.0), 3.0);
	colour = mix(colour, reflect_sky_color.rgb * mix(0.55, 1.0, sky), reflect_amount * sky * (0.35 + 0.65 * fresnel));
	// Lit panes (a hash of the pane, independent of its shade).
	float lit = step(1.0 - lit_windows, hash(cell + surface_seed + vec2(7919.0, 104729.0)));
	lit = mix(lit_windows, lit, keep);
	colour = mix(colour, lit_window_color.rgb, lit * 0.6);
	// Frames and storey bands: on top of everything else.
	float frame = max(grid_line(c.x, pane_width, frame_width, px),
			grid_line(c.y, storey_height, spandrel_width, px));
	glow *= (1.0 + (r - 0.5) * 2.0 * lit_pane_variation * keep) * (1.0 - frame * frame_amount);
	glow += lit_window_color.rgb * lit * lit_window_energy * (1.0 - frame);
	return mix(colour, mix(colour, frame_color.rgb, frame_amount), frame);
}

// Wall panels: seams, a shade per panel, weathering blotches.
vec3 wall_detail(vec3 base, vec2 c, float px) {
	float seam = max(grid_line(c.x, panel_width, seam_width_m, px) * 0.5,
			grid_line(c.y, storey_height, seam_width_m, px));
	vec2 cell = floor(vec2(c.x / panel_width, c.y / storey_height));
	float keep = detail_keep(min(panel_width, storey_height), px);
	float shade = 1.0 + (hash(cell + surface_seed) - 0.5) * 2.0 * panel_variation * keep;
	shade += (noise(c / mottle_size + surface_seed * 0.01) - 0.5) * 2.0 * wall_mottle * detail_keep(mottle_size, px);
	return base * shade * (1.0 - seam * panel_seam);
}

// Metal roofing: standing seams along the face's first axis, blotches.
vec3 metal_detail(vec3 base, vec2 c, float px) {
	float seam = grid_line(c.x, metal_seam_spacing, seam_width_m, px);
	float shade = 1.0 + (noise(c / mottle_size * 1.7 + 3.1) - 0.5) * 2.0 * roof_mottle * detail_keep(mottle_size, px);
	return base * shade * (1.0 - seam * metal_seam);
}

// Roof tiles: level rows (by height), tiles staggered row to row, each row
// darker at its lower edge where the next row overlaps it.
vec3 tile_detail(vec3 base, vec3 p, vec3 n, float px_height, float px) {
	// Rows go by height: a flat face would be one row. Plain there.
	if (abs(n.y) > 0.95) {
		return base;
	}
	float row = p.y / tile_row;
	float row_index = floor(row);
	vec2 along = normalize(vec2(-n.z, n.x) + vec2(1e-5, 0.0));
	float x = dot(p.xz, along) / tile_width + row_index * 0.5;
	float keep = detail_keep(tile_row, px_height);
	float edge = 1.0 - smoothstep(0.0, 0.35, fract(row));
	float split = grid_line(x * tile_width, tile_width, 0.02, px);
	float shade = 1.0 - (edge * tile_shade + split * tile_shade * 0.6) * keep - tile_shade * 0.25 * (1.0 - keep);
	shade *= 1.0 + (noise(p.xz / mottle_size * 2.0) - 0.5) * 2.0 * roof_mottle * detail_keep(mottle_size, px);
	return base * shade;
}
#endif

#ifdef TOON_WEAR
// Worn paint (see toon_worn.gdshader): the surface colour wears through to
// `wear_color` in ragged patches drawn from noise laid out on UV, which the
// model must map at `uv_metres` per unit (the Juggernaut's plating UVs), so
// the wear is sized in metres, sticks to the hull and never repeats. The
// albedo texture is read as plating: where it's dark (seams, hatch edges) the
// paint wears more. (noise.gdshaderinc is included above.)
// Bare metal under the paint (multiplied by the albedo texture like the paint).
uniform vec4 wear_color : source_color = vec4(0.2, 0.22, 0.26, 1.0);
// Metres of surface per UV unit (the model's UV scale).
uniform float uv_metres = 48.0;
// Size of the larger worn patches, in metres.
uniform float wear_size : hint_range(0.1, 10.0) = 1.4;
// How much is worn: 0 none, about 0.3 a weathered look, 1 most of it.
uniform float wear_amount : hint_range(0.0, 1.0) = 0.3;
// How ragged the patch edges are (weight of the finer noise).
uniform float wear_ragged : hint_range(0.0, 1.0) = 0.6;
// Extra wear near the albedo texture's dark lines (plate seams).
uniform float wear_seams : hint_range(0.0, 1.0) = 0.35;
// Scattered small chips, 0 none.
uniform float wear_specks : hint_range(0.0, 1.0) = 0.5;
// How unevenly it wears: regions several metres across range from heavily
// worn to almost clean (0 = the same everywhere).
uniform float wear_variation : hint_range(0.0, 1.0) = 0.6;

// 0 = paint, 1 = bare metal, with an antialiased edge. Each finer octave fades
// out as it shrinks below a few pixels, so the wear never shimmers at range:
// what's left there is the coarse patches, their edges blurred by fwidth.
float wear_mask(vec2 uv) {
	const mat2 turn = mat2(vec2(0.8, 0.6), vec2(-0.6, 0.8));
	vec2 p = uv * uv_metres / wear_size;
	float px = length(fwidth(p));
	float n = noise(p);
	n += (noise(p * 0.17 + 3.3) - 0.5) * 0.9 * wear_variation;
	float w1 = 1.0 - smoothstep(0.15, 0.5, px * 3.7);
	n += (noise(turn * p * 3.7 + 5.2) - 0.5) * 0.45 * wear_ragged * w1;
	float w2 = 1.0 - smoothstep(0.15, 0.5, px * 11.0);
	n += (noise(turn * turn * p * 11.0 + 1.7) - 0.5) * 0.25 * wear_ragged * w2;
	// Plating seams: a blurred read of the texture is darker near them.
	float plating = textureLod(albedo_texture, uv, 3.0).r;
	n += smoothstep(0.85, 0.45, plating) * wear_seams;
	float edge = 0.86 - 0.36 * wear_amount;
	float aa = max(fwidth(n), 0.002);
	float mask = smoothstep(edge - aa, edge + aa, n);
	// Specks: small chips scattered over the paint.
	float w3 = 1.0 - smoothstep(0.15, 0.5, px * 9.0);
	float s = noise(p * 9.0 + 11.3);
	float speck_edge = 0.86 - 0.08 * wear_specks;
	float saa = max(fwidth(s), 0.002);
	mask = max(mask, smoothstep(speck_edge - saa, speck_edge + saa, s) * w3 * step(0.001, wear_specks));
	return mask;
}
#endif

#include "res://effects/toon_light.gdshaderinc"

void fragment() {
#ifdef TOON_CLIP
	vec2 seam = clip_seam(world_position);
	if (seam.x < 0.0) {
		discard;
	}
#endif
	ALBEDO = albedo.rgb * texture(albedo_texture, UV).rgb;
#ifdef TOON_WEAR
	ALBEDO = mix(ALBEDO, wear_color.rgb * texture(albedo_texture, UV).rgb, wear_mask(UV));
#endif
	EMISSION = emission.rgb * texture(emission_texture, UV).rgb * emission_energy;
#ifdef TOON_CLIP
	if (seam.y > 0.0 && seam_energy > 0.0) {
		// White-hot at the cut, the portal's colour further up the band; the
		// surface's own colour darkens under it so the glow reads as heat.
		vec3 heat = mix(seam_color.rgb, seam_hot_color.rgb, smoothstep(0.6, 1.2, seam.y));
		ALBEDO *= 1.0 - 0.8 * min(seam.y, 1.0);
		EMISSION += heat * seam.y * seam_energy;
	}
#endif
#ifdef TOON_INSTANCED
	// Map kit pieces carry their palette colours as vertex colours (one
	// material, one draw per piece; see export_corneria.py's bake_palette()),
	// the glow in alpha as 1 - strength / vertex_glow_energy. A mesh without
	// vertex colours reads white and opaque: no change, no glow. The colours
	// are linear (glTF's, kept as they are by Godot's import), like albedo.
	ALBEDO *= COLOR.rgb;
	EMISSION += COLOR.rgb * (1.0 - COLOR.a) * vertex_glow_energy;
#endif
#ifdef TOON_DETAIL
	// The kind is the same across a face: compare with a margin.
	float kind = floor(UV.x + 0.5);
	if (kind > 0.5) {
		vec3 n = normalize(surface_normal);
		vec2 c = surface_coords(surface_pos, n);
		vec2 width = fwidth(c);
		float px = max(width.x, width.y);
		if (kind == SURFACE_GLASS) {
			ALBEDO = glass_detail(ALBEDO, c, px, NORMAL, VIEW, INV_VIEW_MATRIX, EMISSION);
		} else if (kind == SURFACE_WALL) {
			ALBEDO = wall_detail(ALBEDO, c, px);
		} else if (kind == SURFACE_METAL) {
			ALBEDO = metal_detail(ALBEDO, c, px);
		} else if (kind == SURFACE_TILES) {
			ALBEDO = tile_detail(ALBEDO, surface_pos, n, fwidth(surface_pos.y), px);
		}
	}
#endif
#ifndef TOON_INSTANCED
	ALBEDO = mix(ALBEDO, hit_flash.rgb, hit_flash.a);
	EMISSION = mix(EMISSION, hit_flash.rgb, hit_flash.a);
#endif
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
#ifdef TOON_UNLINED
	// Not `= 1.0`: ALPHA starts at 1 minus the node's transparency, and keeping
	// it keeps fades working.
	ALPHA *= 1.0;
#endif
}
