shader_type spatial;
render_mode cull_disabled, depth_draw_always;

// One sheet of spray thrown up beside a ship skimming the water (WaterWake
// draws one each side), drawn like 2D effects animation draws a bow wave: a
// solid curtain whose foot runs back and out from under the ship along one
// arm of the wake's V, and whose top edge arcs up and back down to the
// water, cut into rounded lobes (a cosine scallop, not noise) that stream
// back along it. Toon-lit white with one blue-tinted shadow band, solid, no
// holes, with no ink outlines (like the water itself).
//
// Expects a PlaneMesh of size 1 × 1 with subdivisions: x across is along the
// sheet (−0.5 at the ship, +0.5 at its far end), z is up the sheet (−0.5 on
// the water, +0.5 at the top edge).

// Drawn-looking effect: keep the hard bands (see toon_light.gdshaderinc).
#define TOON_HARD
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
// The lobes along the top edge: their length (metres), how deep the dips
// between them cut (fraction of the height), and how fast they stream back
// (m/s).
uniform float lobe_length = 3.5;
uniform float lobe_depth = 0.35;
uniform float churn_speed = 30.0;
// How far the foot, where the sheet meets the water, wobbles in and out
// (metres), in step with the lobes: a straight foot drew a hard seam along
// the water from the chase camera.
uniform float foot_wobble = 0.5;
uniform vec4 water_color : source_color = vec4(0.93, 0.97, 1.0, 1.0);
// A painted shade along the base of the sheet, where it meets the water: its
// colour and how far up it reaches (fraction of the height), its edge wavy in
// step with the lobes.
uniform vec4 base_color : source_color = vec4(0.62, 0.8, 1.0, 1.0);
uniform float base_height = 0.45;

varying vec2 v_sheet;
varying float v_phase;

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
	// Lobes streaming back along the sheet (the two sides out of step).
	float phase = (u * sheet_length - TIME * churn_speed) / max(lobe_length, 0.1) * 6.2831853 + side * 2.0;
	// Broad rounded lobes with narrow dips between them.
	float lobe = pow(0.5 + 0.5 * cos(phase), 0.5);
	float h = sheet_height * s * profile(u) * (1.0 - lobe_depth * (1.0 - lobe));
	float out_dist = start_offset + spread * u * (0.5 + 0.5 * s) + lean * v * v * s;
	// The foot wobbles in and out in step with the lobes.
	out_dist += sin(phase * 0.5 + 1.0) * foot_wobble * (1.0 - v);
	VERTEX = vec3(side * out_dist, v * h, u * sheet_length * (0.6 + 0.4 * s) - ahead);
	// Facing out at the foot, turning to face up at the top, so the cel bands
	// shade it (a flat sheet lit evenly read as a strip of paper).
	NORMAL = normalize(vec3(side * (1.0 - v), 0.3 + v * 1.5, 0.0));
	v_sheet = vec2(u, v);
	v_phase = phase;
}

void fragment() {
	// The shade along the base, its edge rising and falling with the lobes.
	float shade_top = base_height * (0.8 + 0.4 * (0.5 + 0.5 * sin(v_phase + 0.7)));
	float w = max(fwidth(v_sheet.y), 0.002);
	ALBEDO = mix(base_color.rgb, water_color.rgb, smoothstep(shade_top - w, shade_top + w, v_sheet.y));
	// Transparent pass, so no ink outlines (like the water itself; ALPHA stays 1).
	ALPHA *= 1.0;
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
	NORMAL = FRONT_FACING ? NORMAL : -NORMAL;
}
