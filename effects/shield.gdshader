shader_type spatial;
// Both sides are drawn so a hit on the far side (e.g. the nose, seen from the
// chase camera behind the ship) still shows through the bubble.
render_mode unshaded, blend_add, depth_draw_never, cull_disabled, shadows_disabled;

// Energy shield bubble. Invisible at rest; ShieldEffect drives `intensity`
// and `ripple` after a hit. Additive and HDR-bright, so it picks up glow.

uniform vec4 shield_color : source_color = vec4(0.3, 0.6, 1.0, 1.0);
// Overall brightness, animated from the hit strength down to 0.
uniform float intensity = 0.0;
// Where the shot landed, as a direction from the bubble's centre (object space).
uniform vec3 hit_direction = vec3(0.0, 0.0, -1.0);
// 0..1 progress of the ring spreading out from the hit.
uniform float ripple = 0.0;
// 0 = only around the hit, 1 = the whole bubble lights up (collapse / reboot).
uniform float coverage = 0.0;

varying vec3 object_pos;

void vertex() {
	object_pos = VERTEX;
}

void fragment() {
	float rim = pow(1.0 - abs(dot(NORMAL, VIEW)), 2.5);
	// Distance across the surface from the impact, 0 (impact) .. 2 (opposite side).
	float d = distance(normalize(object_pos), normalize(hit_direction));
	float spot = smoothstep(0.9, 0.0, d);
	float ring = smoothstep(0.2, 0.0, abs(d - ripple * 1.6)) * (1.0 - ripple);
	// Subtle moving interference pattern so the energy looks like it's dissipating.
	vec3 p = normalize(object_pos) * 9.0;
	float bands = 0.8 + 0.2 * sin(p.x * 3.0 + TIME * 14.0) * sin(p.y * 3.0 - TIME * 11.0) * sin(p.z * 3.0 + TIME * 9.0);
	float local_glow = spot * 1.4 + ring * 1.0 + rim * spot * 1.5;
	float full_glow = rim * 1.2 + 0.15;
	float energy = mix(local_glow, full_glow + local_glow * 0.5, coverage) * bands * intensity;
	ALBEDO = shield_color.rgb * energy * 3.0;
}
