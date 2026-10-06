// The toon surface (flat colour, optional colour texture and glow), shared by
// toon.gdshader, toon_clip.gdshader and toon_unlined.gdshader. Define TOON_CLIP
// before including it to add a clip plane (see toon_clip.gdshader), or
// TOON_UNLINED to draw it in the transparent pass, without ink outlines (see
// toon_unlined.gdshader).

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

void vertex() {
	world_position = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
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
