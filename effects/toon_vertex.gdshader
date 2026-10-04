shader_type spatial;

// Cel shading with the colour taken from the mesh's vertex colours (times
// `albedo`), for meshes built in code that colour each face, such as the
// planet terrain. Same light model as toon.gdshader.

uniform vec4 albedo : source_color = vec4(1.0, 1.0, 1.0, 1.0);

#include "res://effects/toon_light.gdshaderinc"

void fragment() {
	ALBEDO = albedo.rgb * COLOR.rgb;
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
}
