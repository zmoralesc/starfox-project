shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_back, shadows_disabled, fog_disabled;

// The Arwing's engine glow (Model/Glow in player/ship.tscn, a flattened
// sphere at the tail), drawn as a rocket's exhaust: the sphere's back half
// (local +Z) is stretched into a plume `plume_length` metres long, white-hot
// at the nozzle and fading through `glow_color` to nothing at its tip, with
// streaks rushing back along it and a few faint shock diamonds (seen end-on
// from the chase camera, rings). Every point fades towards the silhouette, so
// it reads as light rather than as a solid blob; a fast shimmer and a slower
// pulse keep it alive. Added on top of the scene, so it gets no ink outlines
// and blooms where it's brightest.
//
// Brightness and plume length follow speed through the instance uniform
// `strength` (1 at cruise; set each frame by Fighter._update_engine_glow(),
// which also scales the node), so every ship shares this material. The plume
// reaches past the mesh's own bounds: the node needs an extra_cull_margin.

instance uniform float strength = 1.0;

uniform vec4 glow_color : source_color = vec4(0.35, 0.65, 1.0, 1.0);
uniform vec4 core_color : source_color = vec4(0.85, 0.95, 1.0, 1.0);
// Overall brightness at strength 1; above 1 blooms.
uniform float energy = 2.5;
// How far out the white core reaches (0 = none, 1 = all of it), and how
// tight the glow round it is (higher = darker towards the edge).
uniform float core_size = 0.3;
uniform float falloff = 1.6;
// Shimmer: how much the brightness wavers (fraction), and how fast (Hz).
uniform float flicker = 0.12;
uniform float flicker_speed = 24.0;
// The core swells and shrinks a little at this rate (Hz).
uniform float pulse_speed = 3.0;

group_uniforms plume;
// Plume length behind the nozzle at strength 1 (m), and how much it wavers
// with the shimmer (fraction).
uniform float plume_length = 1.4;
uniform float plume_flicker = 0.1;
// Width at the tip, as a fraction of the nozzle's (before the sphere's own
// rounding off).
uniform float plume_taper = 0.55;
// How far along the plume (0 nozzle .. 1 tip) the white core reaches, and
// where it has faded out completely.
uniform float hot_length = 0.35;
uniform float fade_start = 0.3;
// Streaks rushing back: how strong (fraction of brightness), how many round
// the plume, and how fast they flow (plume lengths per second).
uniform float streaks = 0.35;
uniform float streak_count = 7.0;
uniform float streak_speed = 3.0;
// Shock diamonds: how strong, and how many along the plume.
uniform float diamonds = 0.25;
uniform float diamond_count = 3.0;
group_uniforms;

// 0 on the front half, 0..1 from the nozzle to the tip on the plume; and the
// angle round the plume (turns).
varying float v_along;
varying float v_angle;
// How side-on the plume is to the camera: 1 across the view, 0 end-on.
varying float v_side;

float hash(float n) {
	return fract(sin(n * 127.1 + 311.7) * 43758.5453);
}

// Smooth random wave in 0..1, `t` in cycles.
float wave(float t) {
	float i = floor(t);
	float f = fract(t);
	return mix(hash(i), hash(i + 1.0), f * f * (3.0 - 2.0 * f));
}

// Each ship its own phase, so a formation doesn't flicker in step.
float phase_of(vec3 node_position) {
	return dot(node_position, vec3(0.37, 0.71, 0.53));
}

void vertex() {
	float radius = length(VERTEX);
	float along = radius > 0.0 ? max(VERTEX.z, 0.0) / radius : 0.0;
	v_along = along;
	v_angle = atan(VERTEX.y, VERTEX.x) / TAU;
	vec3 axis = (MODELVIEW_MATRIX * vec4(0.0, 0.0, 1.0, 0.0)).xyz;
	v_side = length(axis.xy) / max(length(axis), 0.0001);
	// The plume's length in the mesh's units: metres over the node's Z scale
	// (which already grows with strength).
	float scale_z = length(MODEL_MATRIX[2].xyz);
	float shimmer = 1.0 + plume_flicker * (2.0 * wave(TIME * flicker_speed + phase_of(NODE_POSITION_WORLD)) - 1.0);
	float stretch = max(plume_length * strength * shimmer / max(scale_z * radius, 0.0001), 1.0);
	if (VERTEX.z > 0.0) {
		VERTEX.z *= stretch;
		VERTEX.xy *= mix(1.0, plume_taper, along);
		// NORMAL is left the sphere's: it stands for how much plume the eye
		// looks through. Side-on, bright along the middle and fading at the
		// edges and towards the tip; end-on, bright in the middle, where the
		// whole length lines up. (The stretched surface's true normals point
		// sideways all along it, which dimmed it to nothing seen end-on.)
	}
}

void fragment() {
	// 1 where the surface faces the camera (the middle of the glow as seen),
	// 0 at its silhouette: soft edges from any side.
	float facing = clamp(dot(NORMAL, VIEW), 0.0, 1.0);
	float phase = phase_of(NODE_POSITION_WORLD);
	float shimmer = 1.0 - flicker + 2.0 * flicker * wave(TIME * flicker_speed + phase);
	float pulse = 0.5 + 0.5 * sin(TIME * TAU * pulse_speed + phase);

	float glow = pow(facing, falloff);
	// A stronger engine has a bigger white core.
	float core_edge = 1.0 - core_size * clamp(strength, 0.5, 1.5) * mix(0.9, 1.1, pulse);
	float core = smoothstep(core_edge, mix(core_edge, 1.0, 0.6), facing);
	// Along the plume, the core cools to the glow colour and the whole fades.
	// Only as much as the plume is side-on: seen end-on (the chase camera),
	// the light of the whole plume lines up, so its middle stays white-hot.
	core *= 1.0 - smoothstep(0.0, hot_length, v_along) * v_side;
	float fade = 1.0 - smoothstep(fade_start, 1.0, v_along) * v_side;

	// Streaks: bands round the plume of random brightness, flowing back.
	float lane = floor(v_angle * streak_count);
	float flow = wave(v_along * 3.0 - TIME * streak_speed + hash(lane) * 7.0 + phase);
	float streak = mix(1.0, mix(1.0 - streaks, 1.0 + streaks, flow), smoothstep(0.0, 0.15, v_along));
	// Shock diamonds: standing bright bands, fading out down the plume.
	float diamond = 1.0 + diamonds * pow(0.5 + 0.5 * cos(v_along * diamond_count * TAU), 4.0)
		* step(0.001, v_along) * (1.0 - v_along);

	vec3 col = mix(glow_color.rgb, core_color.rgb, core);
	ALBEDO = col * glow * fade * streak * diamond * energy * strength * shimmer;
	// Keeps the node's `transparency` fade (a wingman fading out by the
	// camera): ALPHA starts at 1 minus it, and blend_add scales by it.
	ALPHA *= 1.0;
}
