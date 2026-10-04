shader_type canvas_item;
// Comms static: flickering blocky noise with scanlines and a rolling bright
// band, tinted towards the speaker's colour. Shown in the portrait square
// while the channel opens, closes or switches speaker (see comms.gd).

// Seconds, fed by comms.gd (not TIME), so the static freezes while paused.
uniform float time = 0.0;
// 0 = invisible, 1 = full static.
uniform float strength : hint_range(0.0, 1.0) = 1.0;
uniform vec4 tint : source_color = vec4(1.0);
// Noise blocks across the square.
uniform float cells = 28.0;
// New noise pattern this many times per second.
uniform float flicker_rate = 30.0;

// Sin-free hash (Dave Hoskins' hash12): sin-based ones show visible
// repeating patterns on the GPU at these input sizes.
float hash(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

void fragment() {
	vec2 cell = floor(UV * cells);
	float frame = mod(floor(time * flicker_rate), 997.0);
	// Coarse blocks mixed with fine per-pixel grain, both re-rolled every frame.
	float coarse = hash(cell + frame * vec2(17.0, 31.0));
	float fine = hash(floor(FRAGCOORD.xy) + frame * vec2(7.0, 13.0));
	float n = mix(coarse, fine, 0.45);
	// Thin scanlines (several per block, so they don't line up into a weave)
	// and a soft bright band rolling down the square.
	float scan = 0.85 + 0.15 * sin(UV.y * cells * 3.3 * 6.2832);
	float band = smoothstep(0.12, 0.0, abs(fract(UV.y - time * 0.7) - 0.5));
	vec3 grey = vec3(n) * scan + band * 0.25;
	vec3 color = mix(grey, grey * tint.rgb * 1.5, 0.35);
	COLOR = vec4(color, strength * (0.6 + 0.4 * n));
}
