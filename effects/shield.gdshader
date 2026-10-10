shader_type spatial;
// Both sides are drawn so a hit on the far side (e.g. the nose, seen from the
// chase camera behind the ship) still shows through the bubble.
render_mode unshaded, blend_add, depth_draw_never, cull_disabled, shadows_disabled;

// Energy shield bubble, drawn like 2D effects animation draws an energy
// field: invisible at rest; on a hit a crisp white-blue disc pops at the
// impact and shrinks away, a ring with a hard edge races out across the
// bubble (a thinner second ring behind it) and the bubble's cells light up
// as it passes, each with a bright edge, then switch off one by one. The
// cells are a seamless crackle (3D Worley noise cut by the sphere), so they
// read as a crystal lattice with no seams. For collapse and reboot (`coverage`
// 1) every cell lights, with a hard-banded rim, and they drop out at random
// (collapse) or light up at random (reboot, `fill_in` 1). Everything goes by
// shapes switching off, not by fading. Additive and HDR-bright, so it picks
// up glow. ShieldEffect drives the uniforms.

uniform vec4 shield_color : source_color = vec4(0.3, 0.6, 1.0, 1.0);
// The impact disc and the cell edges.
uniform vec4 core_color : source_color = vec4(0.85, 0.95, 1.0, 1.0);
// Overall brightness; above 1 blooms.
uniform float brightness = 1.5;
// Overall strength this play, animated by ShieldEffect (0 = off).
uniform float intensity = 0.0;
// Where the shot landed, as a direction from the bubble's centre (object space).
uniform vec3 hit_direction = vec3(0.0, 0.0, -1.0);
// 0..1 progress of this play: the ring spreading out from the hit, or the
// cells dropping out / lighting up over the whole bubble. Runs on past 1
// while ShieldEffect fades the bubble out.
uniform float ripple = 0.0;
// 0 = only around the hit, 1 = the whole bubble lights up (collapse / reboot).
uniform float coverage = 0.0;
// With coverage 1: 0 = the cells drop out over the play (collapse), 1 = they
// light up over it (reboot).
uniform float fill_in = 0.0;
// Cells across the bubble's radius, and how thick their edges are (fraction
// of a cell).
uniform float cells = 4.0;
uniform float cell_edge = 0.08;
// The impact disc's radius (surface distance, 0..2 across the bubble) and
// how far the ring reaches by the end of the play.
uniform float disc_size = 0.3;
uniform float ring_reach = 1.7;
// Brightness of a lit cell's fill, against its edge at 1.
uniform float cell_fill = 0.25;
// How long each cell takes to go out (or come on), as a fraction of the
// play's progress: 0 = a hard cut.
uniform float cell_fade = 0.25;

varying vec3 object_pos;

void vertex() {
	object_pos = VERTEX;
}

// Integer hash of a grid corner, 0..1 in each axis.
vec3 hash3(vec3 p) {
	uvec3 q = uvec3(ivec3(floor(p + 0.5)) + 1024);
	q = q * uvec3(1597334673u, 3812015801u, 2798796415u);
	uint n = (q.x ^ q.y ^ q.z) * 1597334673u;
	uvec3 r = uvec3(n, n * 16807u, n * 48271u);
	r ^= r >> 16u;
	return vec3(r) * (1.0 / 4294967295.0);
}

// Hard edge, blended over about a pixel.
float step_aa(float edge, float x) {
	float w = max(fwidth(x), 0.001);
	return smoothstep(edge - w, edge + w, x);
}

void fragment() {
	vec3 n = normalize(object_pos);
	vec3 hit = normalize(hit_direction);
	// Distance across the surface from the impact, 0 (impact) .. 2 (opposite side).
	float d = distance(n, hit);

	// The cells: 3D Worley noise on the unit sphere. Nearest and second
	// nearest seed, the nearest's id and its distance from the hit.
	vec3 q = n * cells;
	vec3 cell = floor(q);
	float f1 = 10.0;
	float f2 = 10.0;
	vec3 id = vec3(0.0);
	vec3 seed_pos = n;
	for (int z = -1; z <= 1; z++) {
		for (int y = -1; y <= 1; y++) {
			for (int x = -1; x <= 1; x++) {
				vec3 c = cell + vec3(float(x), float(y), float(z));
				vec3 s = c + hash3(c);
				float dist = distance(q, s);
				if (dist < f1) {
					f2 = f1;
					f1 = dist;
					id = c;
					seed_pos = s;
				} else if (dist < f2) {
					f2 = dist;
				}
			}
		}
	}
	float edge = 1.0 - step_aa(cell_edge * 1.0, f2 - f1);
	vec3 cell_rand = hash3(id * 3.0 + 7.0);
	float cell_d = distance(normalize(seed_pos), hit);

	// A hit: the disc pops and shrinks away over the first part of the play.
	float disc_r = disc_size * (1.0 - smoothstep(0.0, 0.45, ripple)) * mix(1.0, 1.2, smoothstep(0.0, 0.08, ripple));
	float disc = 1.0 - step_aa(disc_r, d);
	// The ring racing out, thinning, a thinner one behind it.
	float reach = ripple * ring_reach;
	// (`ripple` runs past 1 while ShieldEffect fades the bubble out: keep a
	// minimum width, or the ring vanishes when the formula goes negative.)
	float ring_w = max(0.07 * (1.0 - ripple * 0.7), 0.015);
	float ring = 1.0 - step_aa(ring_w, abs(d - reach));
	ring += (1.0 - step_aa(ring_w * 0.5, abs(d - reach + 0.22))) * 0.7;
	// Cells light as the ring passes them, and go out one by one after, each
	// over a short fade (`cell_fade`), so the end is a flicker-out, not a cut.
	float off_at = cell_d + 0.4 + cell_rand.x * 0.5;
	float cell_on = step(cell_d, reach) * (1.0 - smoothstep(off_at, off_at + cell_fade, reach));
	float local_glow = disc * 1.2 + ring + cell_on * (cell_fill + edge);

	// Collapse / reboot: every cell, dropping out (or lighting up) at random
	// over the play, with a hard-banded rim.
	float facing = 1.0 - abs(dot(NORMAL, VIEW));
	float rim = step_aa(0.6, facing);
	float drop = 1.0 - smoothstep(cell_rand.y, cell_rand.y + cell_fade, ripple);
	float light = smoothstep(cell_rand.y - cell_fade, cell_rand.y, ripple);
	float full_on = mix(drop, light, fill_in);
	float full_glow = full_on * (cell_fill + edge + rim * 0.4);

	float glow = mix(local_glow, full_glow, coverage) * intensity;
	// The far side of the bubble shows through the near one and adds to it:
	// at half strength, or the two together blow out to white.
	glow *= FRONT_FACING ? 1.0 : 0.5;
	if (glow < 0.002) {
		discard;
	}
	vec3 col = shield_color.rgb * glow;
	col = mix(col, core_color.rgb * glow, clamp(disc + edge * (cell_on + full_on * coverage) * 0.6, 0.0, 1.0));
	ALBEDO = col * brightness;
}
