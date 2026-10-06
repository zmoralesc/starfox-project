shader_type spatial;
render_mode cull_disabled, depth_draw_always;

// One sheet of spray thrown up beside a ship skimming the water (WaterWake
// draws one each side): a curtain whose foot runs back and out from under the
// ship along one arm of the wake's V, and whose top edge arcs up and back
// down to the water. Churning holes and a ragged top edge stream back along
// it. Toon-lit white, solid, with no ink outlines (like the water itself).
//
// Expects a PlaneMesh of size 1 × 1 with subdivisions: x across is along the
// sheet (−0.5 at the ship, +0.5 at its far end), z is up the sheet (−0.5 on
// the water, +0.5 at the top edge).

#include "res://effects/toon_light.gdshaderinc"

// Set per sheet by WaterWake: −1 left, 1 right; strength 0..1 (height and
// reach scale with it).
instance uniform float side = 1.0;
instance uniform float strength = 1.0;

// Length back along the track (metres), how far out it spreads over that
// length, and how far out from the track it starts.
uniform float sheet_length = 14.0;
uniform float spread = 5.0;
uniform float start_offset = 1.2;
// How far ahead of the ship the sheet starts (metres): from the chase camera
// the water behind the ship is out of sight below, so the spray has to rise
// beside it to be seen.
uniform float ahead = 3.0;
// Tallest point of the top edge (metres) and where along the sheet it is
// (fraction of the length).
uniform float sheet_height = 3.5;
uniform float peak_at = 0.3;
// How far the top leans outwards (metres at the top edge).
uniform float lean = 1.5;
// The churning streams back at this speed (m/s), in blobs this big (metres).
uniform float churn_speed = 30.0;
uniform float churn_scale = 2.0;
// The foot, where the sheet meets the water: how far it wobbles in and out
// (metres) and how much of the sheet's height it frays into gaps (0..1). A
// straight foot drew a hard seam along the water from the chase camera.
uniform float foot_wobble = 0.9;
uniform float foot_fray = 0.3;
uniform vec4 water_color : source_color = vec4(0.93, 0.97, 1.0, 1.0);

varying vec2 v_sheet;

float hash(vec2 p) {
	uvec2 q = uvec2(ivec2(floor(p + 0.5)));
	q = q * uvec2(1597334673u, 3812015801u);
	uint n = (q.x ^ q.y) * 1597334673u;
	n ^= n >> 16u;
	return float(n) * (1.0 / 4294967295.0);
}

float noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
		mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

// Height of the top edge along the sheet (0 to 1): up to the peak, then an
// easing fall back to the water.
float profile(float u) {
	if (u < peak_at) {
		float k = u / peak_at;
		return sqrt(k * (2.0 - k));
	}
	float k = (u - peak_at) / (1.0 - peak_at);
	return 1.0 - k * k;
}

void vertex() {
	float u = VERTEX.x + 0.5;
	float v = VERTEX.z + 0.5;
	float s = clamp(strength, 0.0, 1.0);
	float h = sheet_height * s * profile(u);
	float out_dist = start_offset + spread * u * (0.5 + 0.5 * s) + lean * v * v * s;
	// The foot wobbles in and out, streaming back like the churn.
	float wobble = noise(vec2((u * sheet_length - TIME * churn_speed) / 2.5, side * 5.0)) - 0.5;
	out_dist += wobble * foot_wobble * 2.0 * (1.0 - v);
	VERTEX = vec3(side * out_dist, v * h, u * sheet_length * (0.6 + 0.4 * s) - ahead);
	// Facing out at the foot, turning to face up at the top, so the cel bands
	// shade it (a flat sheet lit evenly read as a strip of paper).
	NORMAL = normalize(vec3(side * (1.0 - v), 0.3 + v * 1.5, 0.0));
	v_sheet = vec2(u, v);
}

void fragment() {
	float u = v_sheet.x;
	float v = v_sheet.y;
	// Blobs streaming back along the sheet.
	vec2 p = vec2(u * sheet_length - TIME * churn_speed, v * sheet_height) / churn_scale;
	float n = noise(p) * 0.7 + noise(p * 2.3 + 7.0) * 0.3;
	// Ragged, lumpy top edge, and holes all through, growing towards the far end.
	// The foot frays into gaps above the water.
	float fray = noise(p * 1.7 + 3.0);
	if (v > 0.3 + 0.7 * n || n < 0.22 + u * u * 0.6 || v < foot_fray * fray) {
		discard;
	}
	ALBEDO = water_color.rgb;
	// Transparent pass, so no ink outlines (like the water itself; ALPHA stays 1).
	ALPHA *= 1.0;
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
	NORMAL = FRONT_FACING ? NORMAL : -NORMAL;
}
