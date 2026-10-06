shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_disabled, shadows_disabled, fog_disabled;

// Soft glow round a laser bolt (the Glow quad under each laser scene's Bolt),
// added on top of the scene: a bolt this thin covers too few pixels for the
// screen-wide bloom to show much. The quad is laid out on screen as a soft
// capsule round the bolt's length, even along most of it and fading towards
// the tail (a round glow at the head alone looked like a lollipop); seen
// end-on it comes out round. It shrinks with distance like the bolt (with a
// minimum size, far bolts lingered on screen as glowing dots).
// Transparent, so the ink outlines skip it.
// Lives under Bolt, so it shares the bolt's length axis (local Y, head at
// -bolt_length/2) and its stretching as the trail grows.

uniform vec4 color : source_color = vec4(0.25, 1.0, 0.3, 1.0);
uniform float energy = 3.0;
// The Bolt mesh's height (its length before stretching), in metres.
uniform float bolt_length = 8.0;
// Glow width (diameter) in metres.
uniform float size = 0.35;
// Higher = tighter glow round the bolt.
uniform float falloff = 2.5;
// Fraction of the length, from the tail, over which the glow fades in; even
// along the rest, like the bolt itself (fading all the way from the head
// made it read as a blob of light on the front of the bolt).
uniform float tail_fade = 0.6;

// Position in the capsule, in glow radii: x along the bolt from the head,
// y across it; and the bolt's length on screen in glow radii.
varying vec2 v_pos;
varying float v_span;

void vertex() {
	vec3 head = (MODELVIEW_MATRIX * vec4(0.0, -bolt_length * 0.5, 0.0, 1.0)).xyz;
	vec3 tail = (MODELVIEW_MATRIX * vec4(0.0, bolt_length * 0.5, 0.0, 1.0)).xyz;
	// Keep the tail in front of the camera (a bolt just fired past it).
	const float NEAR = 0.1;
	if (tail.z > -NEAR && head.z < -NEAR) {
		tail = mix(head, tail, (head.z + NEAR) / (head.z - tail.z));
	}
	// Laid out on screen: in view space the sideways offset ignores
	// perspective, and a bolt angled away from the camera got a sheath at a
	// different angle from the bolt (an X). Screen units are half the screen
	// height, with x scaled by the aspect ratio so they're square. (Only the
	// projection matrix is used: VIEWPORT_SIZE isn't set in vertex(), and
	// dividing by it made the quad vanish.)
	// abs(): the y scale is negative here (Vulkan flips y), which made the
	// radius negative and turned the quad inside out (a bar across the bolt).
	float y_scale = abs(PROJECTION_MATRIX[1][1]);
	vec2 aspect = vec2(y_scale / abs(PROJECTION_MATRIX[0][0]), 1.0);
	vec4 head_clip = PROJECTION_MATRIX * vec4(head, 1.0);
	vec4 tail_clip = PROJECTION_MATRIX * vec4(tail, 1.0);
	vec2 head_px = head_clip.xy / head_clip.w * aspect;
	vec2 tail_px = tail_clip.xy / tail_clip.w * aspect;
	// Radius in screen units: `size` at the head's distance.
	float r = 0.5 * size * y_scale / -head.z;
	// The bolt's direction across the screen. Seen end-on it has no length,
	// and the capsule is a circle round the head.
	vec2 across = tail_px - head_px;
	float span = length(across);
	vec2 dir = span > 0.0001 ? across / span : vec2(1.0, 0.0);
	vec2 side = vec2(-dir.y, dir.x);
	// The quad's x (-0.5..0.5) runs from a radius before the head to a radius
	// past the tail, its y across two radii.
	float s = mix(-r, span + r, VERTEX.x + 0.5);
	float k = span > 0.0001 ? clamp(s / span, 0.0, 1.0) : 0.0;
	vec2 p = head_px + dir * s + side * VERTEX.y * 2.0 * r;
	float depth = mix(head_clip.z / head_clip.w, tail_clip.z / tail_clip.w, k);
	// w = 1, so the varyings interpolate evenly across the screen.
	POSITION = vec4(p / aspect, depth, 1.0);
	v_pos = vec2(s, VERTEX.y * 2.0 * r) / r;
	v_span = span / r;
}

void fragment() {
	// Distance from the bolt's line on screen, in glow radii.
	float along = clamp(v_pos.x, 0.0, v_span);
	float d = length(v_pos - vec2(along, 0.0));
	// 0 at the head, 1 at the tail.
	float t = v_span > 0.0 ? along / v_span : 0.0;
	float fade = smoothstep(0.0, tail_fade, 1.0 - t);
	ALBEDO = color.rgb * energy * pow(max(1.0 - d, 0.0), falloff) * fade;
}
