shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_back, shadows_disabled, fog_disabled;

// Laser bolts: pure light, added on top of the scene. Being transparent, they
// write no depth, so the ink outline pass leaves them alone (an opaque bolt
// got outlined like a hull and read as a solid tube once bloom no longer
// covered the line). A white-hot core runs down the middle, fading to the
// bolt's colour at the edges. Far away it keeps a minimum width on screen
// (about a pixel) so it doesn't flicker as it thins out.
// Expects a mesh lying along its local Y axis: the open, tapered CylinderMesh
// in each laser scene (no end caps, which seen end-on showed as a bead or a
// ring), with its head (bottom) radius in `radius`; the shader brings the
// head to a point (head_point).

uniform vec4 color : source_color = vec4(0.25, 1.0, 0.3, 1.0);
// Brightness; above 1 it blooms.
uniform float energy = 16.0;
// Colour of the core, at the brightness of `core_energy`.
uniform vec4 core_color : source_color = vec4(1.0, 1.0, 1.0, 1.0);
uniform float core_energy = 24.0;
// How much of the width is core (0..1, from the middle out).
uniform float core_width = 0.3;
// The mesh's radius in metres, for the minimum width.
uniform float radius = 0.1;
// Thinnest the bolt gets on screen, in pixels at 720p (scaled with the
// screen height).
uniform float min_width_px = 1.0;
// Fraction of the length, from the tail, over which the bolt fades in, so it
// reads as a streak with a hot head rather than a uniform rod.
uniform float tail_fade = 0.6;
// Fraction of the length, from the head, over which the bolt narrows to a
// point, so it reads as a sharp spike rather than a pellet. Needs rings in
// the mesh to bend along (the laser scenes give it 12).
uniform float head_point = 0.15;
// How far in from the edges the light fades up (0..1 of the facing); small
// = crisp edges.
uniform float edge_softness = 0.2;
// The mesh's height (the bolt's length before stretching), in metres: the
// position along the bolt comes from VERTEX.y (the cylinder's UVs don't run
// a clean 0..1 along it).
uniform float bolt_length = 8.0;

varying float v_widen;
// 0 at the tail, 1 at the head.
varying float v_along;

void vertex() {
	// The minimum width in metres at the bolt's distance: min_width_px of a
	// 720 px tall screen, which covers 2 / abs(PROJECTION_MATRIX[1][1]) metres per
	// metre of distance. (Worked out from the projection alone: VIEWPORT_SIZE
	// isn't set in vertex(), and dividing by it gave NaN.)
	vec3 axis_point = (MODELVIEW_MATRIX * vec4(0.0, VERTEX.y, 0.0, 1.0)).xyz;
	float want = min_width_px / 720.0 * 2.0 * -axis_point.z / abs(PROJECTION_MATRIX[1][1]);
	v_widen = max(1.0, want / (2.0 * radius));
	// The laser scenes turn the mesh's +Y backwards: -Y is the head.
	v_along = clamp(0.5 - VERTEX.y / bolt_length, 0.0, 1.0);
	float point = clamp((1.0 - v_along) / max(head_point, 0.0001), 0.0, 1.0);
	VERTEX.xz *= v_widen * sqrt(point);
}

void fragment() {
	// 1 down the middle of the bolt as seen, 0 at its edges.
	float facing = clamp(abs(dot(NORMAL, VIEW)), 0.0, 1.0);
	float core = smoothstep(1.0 - core_width, 1.0, facing);
	vec3 c = mix(color.rgb * energy, core_color.rgb * core_energy, core);
	float along = smoothstep(0.0, tail_fade, v_along);
	ALBEDO = c * smoothstep(0.0, edge_softness, facing) * along;
}
