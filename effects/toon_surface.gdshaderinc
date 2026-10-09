// The toon surface (flat colour, optional colour texture and glow), shared by
// toon.gdshader, toon_clip.gdshader and toon_unlined.gdshader. Define TOON_CLIP
// before including it to add a clip plane (see toon_clip.gdshader), or
// TOON_UNLINED to draw it in the transparent pass, without ink outlines (see
// toon_unlined.gdshader). TOON_WEAR adds worn paint (see toon_worn.gdshader).
// TOON_INSTANCED corrects the normals of MultiMesh instances (see
// toon_instanced.gdshader).

uniform vec4 albedo : source_color = vec4(0.8, 0.8, 0.8, 1.0);
// Multiplied with `albedo`. White (no change) when unset.
uniform sampler2D albedo_texture : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
// Glow, added on top of the lighting: emission colour × emission texture × energy.
uniform vec4 emission : source_color = vec4(0.0, 0.0, 0.0, 1.0);
uniform sampler2D emission_texture : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float emission_energy : hint_range(0.0, 16.0) = 1.0;
// Flash when hit (HitReaction): rgb the colour, a how much (0 = none). Per
// instance, so every shot target flashes on its own with shared materials. It
// glows rather than tints, so it reads on the shadow side too.
instance uniform vec4 hit_flash = vec4(0.0);

#ifdef TOON_CLIP
// World-space plane (normal, distance): fragments behind it (dot(normal, p) <
// distance) aren't drawn. Per instance; the default (all zero) clips nothing.
instance uniform vec4 clip_plane = vec4(0.0);
varying vec3 world_position;
#endif

#if defined(TOON_CLIP) || defined(TOON_INSTANCED)
void vertex() {
#ifdef TOON_CLIP
	world_position = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
#endif
#ifdef TOON_INSTANCED
	// Godot turns a MultiMesh instance's normals by the instance's matrix M
	// itself, not its inverse transpose, so a non-uniformly scaled instance
	// (a stretched kit tower) gets its sloped faces' normals wrong. Pre-turned
	// by inverse(MᵀM), M then brings them to the inverse transpose's result.
	// MODEL_MATRIX includes the instance's transform here.
	mat3 m = mat3(MODEL_MATRIX);
	NORMAL = inverse(transpose(m) * m) * NORMAL;
#endif
}
#endif

#ifdef TOON_WEAR
// Worn paint (see toon_worn.gdshader): the surface colour wears through to
// `wear_color` in ragged patches drawn from noise laid out on UV, which the
// model must map at `uv_metres` per unit (the Juggernaut's plating UVs), so
// the wear is sized in metres, sticks to the hull and never repeats. The
// albedo texture is read as plating: where it's dark (seams, hatch edges) the
// paint wears more.
#include "res://effects/noise.gdshaderinc"
// Bare metal under the paint (multiplied by the albedo texture like the paint).
uniform vec4 wear_color : source_color = vec4(0.2, 0.22, 0.26, 1.0);
// Metres of surface per UV unit (the model's UV scale).
uniform float uv_metres = 16.0;
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
	if (dot(clip_plane.xyz, world_position) < clip_plane.w) {
		discard;
	}
#endif
	ALBEDO = albedo.rgb * texture(albedo_texture, UV).rgb;
#ifdef TOON_WEAR
	ALBEDO = mix(ALBEDO, wear_color.rgb * texture(albedo_texture, UV).rgb, wear_mask(UV));
#endif
	EMISSION = emission.rgb * texture(emission_texture, UV).rgb * emission_energy;
	ALBEDO = mix(ALBEDO, hit_flash.rgb, hit_flash.a);
	EMISSION = mix(EMISSION, hit_flash.rgb, hit_flash.a);
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
#ifdef TOON_UNLINED
	// Not `= 1.0`: ALPHA starts at 1 minus the node's transparency, and keeping
	// it keeps fades working.
	ALPHA *= 1.0;
#endif
}
