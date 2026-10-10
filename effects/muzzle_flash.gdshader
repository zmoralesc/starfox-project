shader_type spatial;
render_mode unshaded, blend_add, cull_disabled, depth_draw_never, shadows_disabled, fog_disabled;

// A gun's muzzle flash (MuzzleFlash), on a quad facing the camera: a
// white-hot core, a plume thrown forward along the barrel (as long as the
// barrel is side-on to the camera, shrinking to nothing seen end-on), and a
// four-pointed star of thin spikes at a random angle. Everything shrinks and
// dims over the flash's life. Added light, so no ink outlines. Depth-tested:
// the ship's own hull hides it where it covers the muzzle (from the chase
// camera, partly the upper fins), rather than the flash showing through it.
//
// Per flash (instance uniforms): `age` 0 to 1 over its life, `seed` for the
// star's angle, `color` the bolt's impact colour. The node's scale is the
// flash's size in metres; its -Z is the barrel.

instance uniform float age = 0.0;
instance uniform float seed = 0.0;
instance uniform vec4 color : source_color = vec4(0.4, 1.0, 0.5, 1.0);

uniform vec4 core_color : source_color = vec4(1.0, 1.0, 0.95, 1.0);
// Overall brightness; above 1 blooms.
uniform float energy = 1.6;
// Core radius at the start, in flash sizes.
uniform float core_size = 0.35;
// Plume: length (side-on) and half-width, in flash sizes.
uniform float plume_length = 1.6;
uniform float plume_width = 0.32;
// Star: spike length and half-width at the root, in flash sizes.
uniform float spike_length = 1.1;
uniform float spike_width = 0.07;
// The quad's half-size, in flash sizes: must hold the plume and the spikes.
uniform float extent = 2.0;
// How far the quad is pulled towards the camera (m), so the barrel it sits
// in doesn't cut it in half. Kept small: further, and it would show through
// hull just in front of the muzzle.
uniform float pull = 0.15;

// The barrel's direction on screen (view-space x/y, unit) and how side-on it
// is (1 = across the view, 0 = pointing at or away from the camera).
varying vec2 v_dir;
varying float v_side;

float hash(float n) {
	return fract(sin(n * 127.1 + 311.7) * 43758.5453);
}

void vertex() {
	// Billboard round the node, pulled `pull` metres towards the camera so it
	// sits in front of the muzzle's own geometry.
	vec3 centre = (VIEW_MATRIX * vec4(NODE_POSITION_WORLD, 1.0)).xyz;
	float size = length(MODEL_MATRIX[0].xyz);
	vec3 p = centre + vec3(VERTEX.xy * 2.0 * extent * size, 0.0);
	p.z = min(p.z + pull, -0.05);
	POSITION = PROJECTION_MATRIX * vec4(p, 1.0);
	vec3 barrel = normalize((VIEW_MATRIX * vec4(-MODEL_MATRIX[2].xyz, 0.0)).xyz);
	v_side = length(barrel.xy);
	v_dir = v_side > 0.001 ? barrel.xy / v_side : vec2(1.0, 0.0);
}

void fragment() {
	// Position in flash sizes, y up on screen; then along/across the barrel.
	vec2 uv = (UV * 2.0 - 1.0) * vec2(1.0, -1.0) * extent;
	float r = length(uv);
	float along = dot(uv, v_dir);
	float across = dot(uv, vec2(-v_dir.y, v_dir.x));
	float aa = fwidth(r) * 1.5;
	float fade = 1.0 - age;

	// Core: a disc that shrinks away, white in the middle.
	float core_r = core_size * mix(1.0, 0.3, age);
	float core = 1.0 - smoothstep(core_r - aa, core_r, r);
	float halo = exp(-r * r / (core_r * core_r * 4.0)) * fade;

	// Plume: a teardrop ahead of the muzzle, widest a third of the way out,
	// that shoots forward and narrows.
	float len = plume_length * v_side * mix(0.7, 1.0, smoothstep(0.0, 0.4, age));
	float k = len > 0.01 ? along / len : -1.0;
	float half_w = plume_width * sin(clamp(k, 0.0, 1.0) * PI) * mix(1.0, 0.4, age);
	half_w = max(half_w, plume_width * 0.6 * (1.0 - smoothstep(0.0, 0.25, k)) * step(-0.2, k));
	float plume = (1.0 - smoothstep(half_w - aa, half_w, abs(across))) * step(-0.2, k) * step(k, 1.0);

	// Star: four tapered spikes at a random angle.
	float angle = atan(uv.y, uv.x) + hash(seed) * TAU;
	float spoke = abs(fract(angle / TAU * 4.0) - 0.5) * 2.0;
	float reach = spike_length * mix(0.6, 1.0, hash(seed + 1.0)) * mix(1.0, 0.5, age);
	float taper = 1.0 - clamp(r / reach, 0.0, 1.0);
	// The spike's half-width as an angle at radius r, against the angle to
	// its centre line (1 - spoke, in eighths of a turn).
	float w = spike_width * taper * fade / max(r, 0.02) * 4.0 / PI;
	float spike = (1.0 - smoothstep(w * 0.6, w, 1.0 - spoke)) * step(r, reach);

	float shape = max(max(plume, spike) * fade, core);
	vec3 col = mix(color.rgb, core_color.rgb, max(core, 0.6 * (1.0 - smoothstep(0.0, 0.8, r))));
	vec3 light = col * shape * energy + color.rgb * halo;
	if (max(shape, halo) < 0.002) {
		discard;
	}
	ALBEDO = light;
}
