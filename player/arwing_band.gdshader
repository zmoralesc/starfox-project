shader_type spatial;

// The toon shader (toon.gdshader) plus a painted band in the pilot's colour,
// for the Arwing's blue fins (see ShipModel). The band is a shell at
// `band_radius` around `band_hub`, mirrored left/right, so it cuts straight
// across every fin blade at the same distance from the fins' root, with a thin
// pinstripe along each edge (so a blue band, Falco's, still reads on the blue
// fins). Positions are in the ship's Model space; `to_ship` takes this mesh's
// vertices there.

uniform vec4 albedo : source_color = vec4(0.8, 0.8, 0.8, 1.0);
uniform vec4 band_color : source_color = vec4(0.95, 0.78, 0.12, 1.0);
uniform vec4 pinstripe_color : source_color = vec4(0.95, 0.95, 0.95, 1.0);
// Mesh-local to ship Model space (set per mesh by ShipModel).
uniform mat4 to_ship = mat4(1.0);
// Centre of the shell, on the right side (x is mirrored).
uniform vec3 band_hub = vec3(1.0, 0.3, -0.1);
// Distance from the hub to the middle of the band, its width, and the width
// of each pinstripe outside it (metres).
uniform float band_radius = 2.3;
uniform float band_width = 0.4;
uniform float pinstripe_width = 0.06;

#include "res://effects/toon_light.gdshaderinc"

varying vec3 ship_pos;

void vertex() {
	ship_pos = (to_ship * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec3 p = vec3(abs(ship_pos.x), ship_pos.y, ship_pos.z);
	// Distance from the band's middle line, across the fin.
	float d = abs(distance(p, band_hub) - band_radius);
	float aa = max(fwidth(d), 0.001);
	float half_width = band_width * 0.5;
	float in_band = 1.0 - smoothstep(half_width - aa, half_width + aa, d);
	float in_stripes = 1.0 - smoothstep(half_width + pinstripe_width - aa, half_width + pinstripe_width + aa, d);
	vec3 color = mix(albedo.rgb, pinstripe_color.rgb, in_stripes);
	ALBEDO = mix(color, band_color.rgb, in_band);
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
}
