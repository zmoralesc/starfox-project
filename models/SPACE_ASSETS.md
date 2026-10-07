# Space Station mission: asset brief

This file asks for new 3D models for the Space Station mission of **Star Fox: Ascent**, a Godot 4 fangame in the style of *Star Fox 64*. The mission is a dogfight in an asteroid field around a friendly Cornerian space station. Enemy fighters attack in waves, and every fifth wave an enemy destroyer warps in.

Today every model in this mission is built from code: Blender scripts make the destroyer, the station and the enemy fighter out of boxes, prisms and lathed profiles, and the asteroids are noise-pushed spheres made in the game. This brief replaces them with hand-designed models, in the same way you made the Corneria kit (`models/corneria/ASSETS.md`).

The work comes in three stages. **Do only the stage you are asked to do in each run, then stop and report.**

| Stage | What | Status |
|---|---|---|
| **A** | Destroyer: rough design proposals (blockouts) for the user to choose from | first |
| **B** | Space station, enemy fighter, asteroids; Great Fox optional | after A |
| **C** | Destroyer and its turret: full model of the chosen proposal | after the user picks |

Read the **global brief** first: every asset depends on it.

---

## Global brief (applies to every asset)

### How the models are seen
- **The player's view.** The player flies a small fighter (about 6 m long and 6 m wide) at 50–130 m/s, often boosting. Big objects are seen from 3 km away down to strafing passes 10–30 m off their surface.
- **Two distances matter.** From afar, silhouette and big colour areas are all that read. Up close, the surface needs detail at a real-world scale (windows, panels, lights about 1–3 m in size) so a 700 m ship *feels* 700 m long. Detail under about 1 m is invisible at speed.
- **Space lighting.** There's one sun, high overhead, and a dark starfield. The undersides of big ships sit in shadow, where close greys look the same: what reads there is shape, ink outlines and lights.

### Art style
- **Overall look.** Cel-shaded, like an animated film: *not cartoon-simple, but not very complex either*, somewhere between *Wind Waker* and *Breath of the Wild*. Bold forms, clear silhouettes, crisp creases.
- **Factions.**
  - **Corneria** (the station; friendly): clean, engineered, optimistic. Mid greys and off-whites, Cornerian blue, hazard yellow at docks and hangars, cool blue-white windows.
  - **Venom** (the destroyer and fighters; enemy): menacing, angular or insectile. Dark gunmetal, crimson, sickly accents, amber or red-orange glows. Enemies must never be mistaken for friendlies at a glance.
- **Shading.** The game cel-shades everything: three hard light bands and black ink outlines.
- **Where ink lines go.** On every silhouette, and on every edge where the surface normal changes sharply.
  - Each bevel, chamfer or small step adds another ink line, so a busy model turns into a tangle of black lines. Prefer **big clean planes and a few strong creases**, with detail grouped in deliberate areas.
  - **Curved surfaces** (cylinders, domes, rings) should be **smooth-shaded**: Shade Auto Smooth at about 30°, so only intended creases get lines. 12–32 segments are enough for most round shapes; very large rings may need more.
  - **Colour changes draw no ink line.** Paint windows, stripes and markings by giving coplanar faces another material, not by modelling recesses or raised strips.
- **Lines fade with distance** (from about 220 m to 520 m), so big objects must also read by colour and shape alone.

### Colours and materials
- **Flat-colour materials.** One flat colour per material. Each asset's section lists its material prefix and required names; add more with the same prefix as needed and list them in your report.
- **The light is bright.** A 0.46 grey renders near-white in the game. Keep large surfaces at or below about 0.45 sRGB, and enemy hulls dark (0.12–0.30).
- **Values are sRGB, 0–1**, as they should appear in the game. In Blender, set the Base Color so it shows that colour (Blender stores linear values; the colour picker's hex field is sRGB).
- **Glowing parts** use emission: Emission Color = Base Color, strength 3–10. Glows bloom in the game, so lights read from far away.
- **Textures** are allowed but not needed. The game keeps only the colour and emission textures; normal, roughness and metal maps are dropped.

### Technical rules
- **Units and axes.** Blender units are metres; Blender is Z-up, and glTF export converts.
- **Facing.** Ships and the station point their **bow/nose along Blender +Y** (the game's forward, −Z). (This is the opposite of the Corneria kit, whose fronts faced −Y.) Up is +Z.
- **Normals point outwards.** The game draws **only the front of each face**. Check every asset with **Viewport Shading → Backface Culling** on. Thin parts (panels, fins, dishes) need real thickness.
- **Closed meshes.** Solid parts are closed: no holes, no loose internal faces, no zero-area faces, seams merged.
- **Nothing floats.** Every piece touches or sinks into the body it belongs to, with no gap at all, not even centimetres. Work out the height and width of the surface under a piece at its exact position (lofts narrow and slope, chamfers cut corners) rather than reusing a nearby number; on a sloping surface, make the piece thick enough to sink in at both ends. Turret pads and anything a turret stands on must be fully supported. (The Juggernaut's first export had its stern castle 6 m above the deck, turret pads hovering 18 m up or hanging off an edge, and windows hanging in the air where the hull side sloped away beneath them.)
- **No shared face planes.** Two visible faces of different pieces must never lie in the same plane where they overlap: the game can't tell which is in front, and the spot flickers. When pieces meet face to face, make one stand slightly proud (0.3–0.5 m) or sink it in. Watch for boxes with equal depths at the same position (a lintel and its legs, a cowl and its lip) and for "recessed" panels whose front face sits exactly on the surface.
- **Apply all transforms** (scale 1, rotation 0) on mesh data, except where an object's origin is a required pivot (then the object origin sits at the pivot and the mesh is modelled around it).
- **Not included:** no unapplied modifiers, armatures, animation, lights or cameras in exported files.
- **Polygon budget:** each asset has one. Stay within it.

### Files and the shared Blender session
- **Blender is the user's live session** (through the Blender MCP). If the open file has unsaved changes, don't discard them: stop and report. Work in your own new `.blend` files at the paths given.
- **Never reset or reload Blender from a script:** no `wm.read_factory_settings`, `wm.read_homefile` or `wm.open_mainfile`. They stop the MCP server (it lives in the session) and throw away whatever the user has open. To start clean, remove objects, meshes and collections through `bpy.data`. To save, use `wm.save_as_mainfile`.
- **Godot imports anything in the project folder.** Keep `.blend` files and screenshots inside a `source/` folder that has a `.gdignore` file (create an empty `.gdignore` if one is missing). Only the exported `.glb` files go outside `source/`.
- **Don't overwrite what the game uses now.** Export to the new file names given here. Don't touch the existing `.glb` files, the `build_*.py` scripts, `proxies.txt`/`collision.txt`, or any `.tscn`/`.gd` file. Hooking the new models into the game is a separate step.
- **Don't commit.** The user reviews first.
- **Report:** for each asset, give its triangle count, bounding-box size, origin and pivots, the materials it uses (name, sRGB colour, emission), the screenshot paths, and anything in this brief you couldn't meet or chose to change, with the reason.

---

## Stage A: destroyer design proposals

### What the destroyer is
Venom's capital ship and the mission's boss. One warps in every fifth wave through a giant circular portal 3 km from the station, bow first, then crawls towards the station and parks about 900 m from it. It launches fighter squadrons from two hangars and defends itself with eight gun turrets. The player and three AI wingmen take it apart piece by piece:

| Part | Count | Role |
|---|---|---|
| **Bridge** | 1 | Weak point. Must be destroyed to kill the ship. |
| **Thrusters** | 3 | Weak points. All must be destroyed (plus the bridge) to kill the ship. Each one lost slows it down. |
| **Hangar doors** | 2 | Fighters launch from the bays behind them. Blowing a door off stops launches from that side. |
| **Turrets** | 8 | Shoot at the player. Deadly to anyone flying slowly near the hull. |

The hull itself can't be damaged: it's solid scenery that blocks shots. The parts are the targets. A destroyed part stays in place, charred and dark.

### What the user wants
A **complete redesign from scratch**. Don't base the proposals on the current ship (a broad armoured wedge splitting into two forward prongs, with a bridge tower amidships and three engines in a row). Explore genuinely different ideas.

### Deliverable for Stage A
**Three distinct concepts** (a fourth is welcome if you have a strong idea), as **rough blockouts**: primary and secondary volumes only, at true scale, in roughly the intended colours. No surface detail, no collision, no UVs. Spend the effort on silhouette, proportion and how the parts sit on the hull.

For each concept:
- **A Blender collection** `Concept_<Letter>_<ShortName>` (e.g. `Concept_A_Hammerhead`) in `models/destroyer/source/concepts/destroyer_concepts.blend`.
- **Parts as separate objects**, named `<Letter>_Bridge`, `<Letter>_Thruster_1..3`, `<Letter>_HangarDoor_L/R`, `<Letter>_TurretMount_1..8` (a flat disc 10 m across marking each turret mount), so the user can see where each sits.
- **Five screenshots** saved in `models/destroyer/source/concepts/`, named `<Letter>_<view>.png`, about 1600 × 900, backface culling on, solid shading with material colours on a dark background:
  - `hero`: three-quarter view from front and above, as the player sees it arriving;
  - `side`: orthographic side view;
  - `top`: orthographic top view;
  - `rear`: three-quarter view from behind and slightly below, showing the thrusters;
  - `scale`: the concept beside the **current** destroyer (import `models/destroyer/destroyer_hull.glb` into a separate `Reference_Current` collection, offset to one side; it's already at game scale) and a 6 m box for the player's fighter near the bow.
- **A write-up**, `models/destroyer/source/concepts/PROPOSALS.md`, with one section per concept:
  - name and one-line pitch;
  - the idea behind the shape (what it should make the player feel, what it evokes);
  - approximate size (length × width × height);
  - where each part sits and **how attacking it plays** (approach lines, cover, what the turrets cover, where the blind spots are);
  - colour scheme;
  - risks or open questions (e.g. "the bridge is hard to see from below").

  End with a short comparison table and your own recommendation, with the reason.

**Budget:** under 10,000 triangles per concept. **Then stop and report.** The user will pick a concept (or combine ideas) before Stage C.

### Gameplay constraints (every concept must meet these)
- **Size.** 600–800 m long (the current ship is 737 m long, 350 m wide, 278 m tall). Big enough to be a landmark, small enough to circle in under a minute.
- **The warp portal.** It arrives bow first through a circular portal. Keep the whole cross-section (seen from the bow) inside a circle of **220 m radius** centred 30 m above the ship's origin. (The portal can be resized if a concept really needs it; say so.)
- **Origin.** The ship's origin is on its centre line, roughly in the middle of its length, at about the level of the main hull's underside.
- **The bridge** is the main target. It must be **obvious from far away** (a distinct, lit structure), reachable from above and both sides, and big enough to hit (it's targeted as a sphere of about 50 m radius). Don't bury it in a trench.
- **The thrusters** face aft and are glowing nozzles the player attacks from behind. Each one must be visible and hittable from behind and from above or below (each is targeted as a sphere of about 30 m radius). They're separate objects, each with its origin at its nozzle centre, and ideally identical (the game uses one model three times; mirrored is fine).
- **The hangar doors.** Two, one on each side (left/right), or both underneath. Each door is a flat slab about **78 m long and 36 m tall** (up to ±25 %) over a recessed bay at least 20 m deep. The door slides **up** (along the hull side) to open, so leave room above it on the hull. Fighters (6 m) fly out of the bay sideways. The door is a separate object with its origin at its centre.
- **Turret mounts.** Eight, on the upper and side surfaces, spread along the whole length so their fire covers the hull. Each needs a flat, level pad about 10 m across with open sky above it (turrets pitch from −5° to 80°, so the hull must not block their view sideways). Avoid putting a turret where the hull would hide it from every approach.
- **Flyable shapes.** The AI steers around spheres, so big simple volumes work best. Avoid narrow slots, deep pockets and overhangs where a fighter could get trapped. A gap or tunnel the player can fly through is welcome as a set piece if it's at least **60 m wide and 40 m tall**.
- **Collision.** The final hull's collision will be built from about 10–20 convex pieces. Prefer shapes that split naturally into convex blocks.
- **Look.** Venom faction (see the global brief): dark gunmetal hull (0.12–0.30 sRGB), crimson markings, amber or red-orange windows and engine glow. Name materials `Destroyer_<Name>`.
- **Silhouette first.** It must read as hostile and as a capital ship from 3 km away in silhouette alone, and look different from the friendly station and the Great Fox (a long white carrier with two forward prongs).

### Freedoms
- Anything not listed above is open: the shape language (blade, insect, fortress, ring, asymmetry...), where the bridge sits, how the engines group, whether it has prongs or a spine.
- A concept may propose a **different part count** (e.g. 2 or 4 thrusters, a second bridge-like weak point) if the design is better for it. Mark it clearly in the write-up: the game's code would need changing.

### Stage A2: Manticore revision
The user likes the **general style of Concept A (Manticore)**: the spearhead beak, the forward-reaching outrigger claws, the stepped dorsal spine with the bridge on top, the exposed thruster cluster. One thing must change: **the hangar doors must be unobstructed.** In Concept A they sit on the fuselage sidewalls at the mouth of the channels under the outriggers, so the booms hide them from the side and above, and fighters launch into a 50 m slot.

Make one revised blockout, `Concept_A2_Manticore`, in the same `destroyer_concepts.blend`. Leave the four original concepts untouched. Keep everything else about A's look and part layout unless moving the doors forces a change (say what changed and why).

**What "unobstructed" means** (each door must meet all of these):
- **Visible broadside.** From any point 300 m straight out from the door's side of the ship, and from 30° ahead or behind that, the whole door is in view with no hull in between.
- **Clear launch corridor.** A box 60 m wide and 50 m tall, straight out from the door for 200 m, contains no part of the ship. Fighters launch along it.
- **Room to open.** The door slides up along the hull by its own height (36 m) plus a margin. That strip of hull above it stays flat and clear of turrets, outriggers and other parts.
- **Attackable at speed.** A player flying a straight strafing pass along the ship's side, 40–100 m out, can keep the door in the crosshair for at least 2 seconds at 100 m/s (about 200 m of run) without having to fly into a channel.

How to get there is your call. For example: move the doors aft of the outrigger roots, put them on the outer faces of the outriggers, shorten or raise the outriggers, or move the outrigger roots forward. If you weigh several options, say briefly which you rejected and why.

**Deliverables** (same rules as Stage A):
- The collection, with the parts named `A2_Bridge`, `A2_Thruster_1..3`, `A2_HangarDoor_L/R`, `A2_TurretMount_1..8`.
- Screenshots `A2_hero.png`, `A2_side.png`, `A2_top.png`, `A2_rear.png`, `A2_scale.png`, plus **`A2_hangar.png`**: a view from about 300 m broadside, level with the left door, showing it unobstructed. Mark the launch corridor with a translucent box in that view only (a temporary object, not part of the collection).
- A new section at the end of `PROPOSALS.md`, **Concept A2: Manticore (revised)**, in the same format, stating where the doors are now, how each "unobstructed" check is met, and what else changed from A.

**Then stop and report.**

### Stage A3: a second round of concepts
The user wants **another set of all-new concepts**, `E` to `H` (a fifth, `I`, is welcome). Everything in Stage A still applies (deliverables, constraints, freedoms). This section adds what the first round taught.

**Push the ideas further apart.** In round one, A, B and D were all variations of a central body with forward prongs or claws, and all four used the same faceted-box language and the same colours. This round:
- **No forward prongs, claws, mandibles or outriggers** reaching past the bow, and no hollow ring around a spine (concepts A, C and D already cover those). Don't revisit the current ship either.
- **Make each concept different on at least two of these axes**, and say which in its write-up:
  - overall mass: long and thin, wide and flat, tall and narrow, compact and blocky;
  - symmetry: symmetric, or deliberately asymmetric;
  - shape language: hard angular planes, smooth organic curves, stacked modular blocks, a spine with hung modules;
  - where the bridge is: high on a tower, at the bow, at the stern, slung underneath;
  - how the engines group: a single cluster, spread wide, stacked vertically, on pylons.
- **Vary the colour scheme** within the Venom palette: at least one concept leads with crimson rather than gunmetal, or uses a third accent colour (e.g. a sickly green or violet glow alongside the amber).

**Vary the height.** Round one was 110–170 m tall; the current ship is 278 m. **At least two concepts get a tall bridge tower or superstructure** (200 m or more overall) that reads as a landmark from 3 km, and at least one stays low. The portal limit still applies (cross-section inside a 220 m circle centred 30 m above the origin), so a tall ship needs a narrower beam or an origin placed to suit; report the measured clearance.

**The bridge is a substantial structure.** In round one every bridge was a small box. Make it a recognisable command structure, at least 40 m across, with a lit window band, that reads as the ship's head.

**Hangar doors are unobstructed.** Every concept must meet the four checks from Stage A2 (visible broadside, clear launch corridor, room to slide open, attackable at speed). Measure them in Blender and report the numbers.

**Clean blockouts.** Round one had a ragged dark patch beside concept A's bridge (probably a hole or a flipped face). Before rendering, check each mesh for non-manifold edges and inward-facing normals. Report the bounding box *including* the thrusters, and make the stated length match it.

**Deliverables:** as in Stage A: collections `Concept_<Letter>_<ShortName>` in the same `destroyer_concepts.blend`, leaving the existing collections untouched; the five screenshots per concept plus a `<Letter>_hangar.png` like A2's; and a new part at the end of `PROPOSALS.md`, **Round 2 (concepts E–H)**, with one section per concept, a comparison table covering all round-two concepts, and your recommendation. **Then stop and report.**

---

## Stage B: station, fighter and asteroids

### B1. `SpaceStation`: the Cornerian space station
**Used:** once, at the centre of the mission area. It's friendly scenery: solid (you crash into it), not shootable. It's the mission's landmark and the thing the player is defending. Later missions may make some of its components destructible.

**Today:** a wheel station 800 m across: a spindle along its axis, a wheel joined by four spokes (the open quarters are big enough to fly a formation through), docking arms and a lit hangar at the bow, solar wings and a dish at the stern.

**Redesign:** you're free to change the layout entirely, within these constraints:
- **Size:** fits inside a sphere of **450 m radius** around its origin. Origin at its centre.
- **Bow along +Y.** The game turns it so its bow and hangar face the player's arrival.
- **Fly-through.** At least **two openings the player and three wingmen can fly through in formation**: each at least **150 m** across in both directions, with clear lines straight through. Threading the station during a dogfight is the mission's signature move, so make these openings inviting and obvious.
- **A lit hangar** (a glowing bay opening at least 60 × 35 m) facing the bow. Fighters don't use it yet; it's for looks.
- **Components.** Build it from separate objects, one per major component (e.g. core, ring segments, spokes, hangar, solar arrays, dish), each with its origin at the point where it attaches to the rest, so a component could later be charred, hidden or blown off on its own. Name them `Station_<Component>` and list them with their pivots in the report.
- **Collision is built from the visible mesh.** Every mesh is solid except surfaces in the non-solid materials. Put windows, small lights and glow panels on materials whose names end in `Window`, `Glow` or start with `Station_Nav` (e.g. `Station_Window`, `Station_HangarGlow`, `Station_NavRed`) so they stay out of the collision, and list them.
- **AI.** The AI steers round spheres. Large smooth volumes and clear gaps work best; avoid lattices of thin struts the size of a fighter, and narrow slots.
- **Look.** Corneria faction. Today's palette, as a starting point:

  | Material | sRGB | Emission | Use |
  |---|---|---|---|
  | `Station_Hull` | 0.30, 0.32, 0.35 | | main hull |
  | `Station_HullLight` | 0.40, 0.42, 0.45 | | lighter panels |
  | `Station_Dark` | 0.08, 0.09, 0.11 | | recesses, vents |
  | `Station_Accent` | 0.08, 0.20, 0.50 | | Cornerian blue |
  | `Station_Trim` | 0.80, 0.58, 0.12 | | hazard yellow at docks and hangar |
  | `Station_Solar` | 0.05, 0.08, 0.22 | | solar cells |
  | `Station_Window` | 0.62, 0.85, 1.00 | 3 | windows |
  | `Station_HangarGlow` | 0.45, 0.75, 1.00 | 4 | hangar interior |
  | `Station_NavRed` / `NavGreen` / `NavWhite` | 1.0, 0.12, 0.08 / 0.15, 1.0, 0.3 / 1, 1, 1 | 6 | navigation lights (red on the left, green on the right) |

- **Budget:** 60,000 triangles total.
- **Delivery:** `models/space_station/source/space_station_v2.blend`; export `models/space_station/space_station_v2.glb` (glTF binary, +Y up, Apply Modifiers on, materials exported, one node per component, keeping the object names). Screenshots in `models/space_station/source/preview/`: a three-quarter hero view, front, side and top, and one view looking through each fly-through opening.

### B2. `EnemyFighter`: the Venom fighter
**Used:** every enemy fighter in the game, on this mission and on Corneria: dozens per mission, up to about 20 on screen. One model serves every fighter type; the game recolours two materials per type. When shot down, the model becomes a smoking wreck.

**Today:** an insectile "Mantis" with pincer forelegs carrying the guns, olive hull, purple markings, red glowing eye.

**Redesign:** a new design is welcome, keeping:
- **Size:** fits in a box **6.2 m wide × 2 m tall × 5.6 m long**, centred 0.5 m forward of the origin (from 2.3 m behind the origin to 3.3 m in front of it). Small protrusions (antennas, pincer tips) can poke out up to 0.5 m.
- **Origin** at the ship's centre; nose along +Y.
- **Guns:** two muzzles, symmetric about the centre line, **about 1.9 m apart** and near the nose. Report the muzzle positions (game coordinates are fine: x right, y up, z = −Blender Y).
- **Engine:** one engine exhaust at the tail, centred on the centre line about 2.35 m behind the origin. The game adds the glow itself (a stretched glowing sphere, 3.5 × 1.5 m); model a nozzle opening for it to sit in.
- **Smoke point:** the spot where a damaged fighter's smoke comes out, near the back on top. Report it.
- **Required material names** (the game recolours these by name, so keep them exactly):
  - `Fighter_Accent`: painted markings (stripes, tips, fin). Any colour in the file; the game sets it per type.
  - `Fighter_Lights`: glowing eye and running lights, emissive. Glows bloom, so this is what makes fighters visible from far away against space: use it generously enough to read at 500 m, on both the front and the sides.

  Other materials: `Fighter_<Name>`. Today's base colours: hull 0.36, 0.40, 0.30; dark 0.10, 0.11, 0.10; canopy 0.16, 0.10, 0.20.
- **Readability.** Clearly hostile and clearly different from the player's Arwing (white and blue, swept-forward wings, two vertical blue fins) from any angle. Readable as a dark silhouette with glowing lights at 300 m.
- **Budget:** 3,000 triangles.
- **Delivery:** `models/enemy_fighter/source/enemy_fighter_v2.blend`; export `models/enemy_fighter/enemy_fighter_v2.glb`. Screenshots in `models/enemy_fighter/source/preview/`: front three-quarter, rear three-quarter, side, top, and beside a 6 × 1.2 × 6.5 m box for the Arwing.

### B3. `Asteroid`: asteroid rocks (8 variants)
**Used:** 640 rocks spread through the mission area, 6 to 56 m across. Each picks one of the variants at random, gets a random rotation, and is stretched randomly per axis (0.7–1.25). They spin slowly and can be shot to pieces.

**Design:**
- **Eight variants**, `Asteroid_0` to `Asteroid_7`, each modelled at **radius 1** (roughly 2 m across, so the game scales it to size). The collision is a sphere of radius 0.85, so the rock should fill that sphere and not stick out far beyond radius 1.15.
- **Shape:** lumpy, chunky rocks with a few big facets, ledges and craters; some rounder, some elongated, one or two split or with a big bite out. No two alike. Flat shading is fine here if the facets stay big (about 8–20 per side of the rock), so the ink lines stay sparse.
- **Colour:** materials `Asteroid_Rock` (about 0.33, 0.30, 0.28) and `Asteroid_RockDark` (about 0.22, 0.20, 0.19) for craters and patches. Optional third accent, e.g. a pale mineral vein or a faint ice patch, `Asteroid_<Name>`.
- **Budget:** 400 triangles per variant.
- **Origin:** the centre of the rock.
- **Delivery:** `models/asteroid/source/asteroids.blend` (create the folder and its `.gdignore`); export `models/asteroid/asteroids.glb` with the eight objects as separate nodes, spread out so they don't overlap in the file (the game reads each node's mesh, not its position). One preview screenshot of all eight in `models/asteroid/source/preview/`.

### B4. `GreatFox` (optional, large job): the team mothership
Same as entry 30 of the Corneria brief (`models/corneria/ASSETS.md`): the current Great Fox model came without a licence, and it parks outside every mission. Do it only if time allows, after B1–B3, and say so in the report.

---

## Stage C: the destroyer and its turret (after the user's choice)

The user picked **Concept H, the Juggernaut**: a brutalist, modular siege dreadnought with a blunt, tiered battering-ram prow, a stern castle bridge looking forward over the whole ship, engines on pylons, and acid-green radiators down the spine. Build it properly now, starting from `Concept_H_Juggernaut` in `destroyer_concepts.blend` and its write-up in `PROPOSALS.md`.

Stage C runs in **two passes**, each followed by a stop for the user's review:
- **C1, the form pass:** the final shapes, parts and turret, with no surface detail yet.
- **C2, the detail pass:** surface detail, collision and export.

### Style: simple, but with substance
This is the most important part of Stage C. The user's style guide: *a cel-shaded, animated look, not cartoon-simple but not very complex either, between Wind Waker and Breath of the Wild.* In the user's words: **a relatively simple style, but not zero detail; simplicity without losing substance.**

The blockout is too simple: a hull of a few big boxes with a box on top doesn't say "700 m warship". A hull carpeted with greebles is too busy: under the ink outlines it turns into noise. Aim between the two, using three levels of form:

1. **Primary forms (the silhouette).** A few big, confident masses that read from 3 km: the battering prow, the main hull, the stern castle, the engine pylons. Give each a clear character: the prow's stepped tiers, the castle's overhanging brow, the pylons' heavy struts. Use strong angles and a few large chamfers, never a plain box. *Read test:* a black silhouette from the side, front three-quarter and top must each be recognisable.
2. **Secondary forms (the structure).** Medium shapes that explain how the ship is built, each about 10–60 m:
   - modules: armour blocks that step and overlap, a spine down the middle, ribs or buttresses;
   - working parts: the radiator banks, recessed hangar bays with frames, engine housings with intakes and cowls;
   - attachments: the pylon struts and how they join the hull.

   These give the ship its "industrial" substance. Most of the triangle budget goes here.
3. **Tertiary detail (the scale cues).** Small elements, 1–5 m, that tell the eye how big the ship is:
   - rows of lit windows (about 1.8 × 0.9 m, painted as faces);
   - running lights;
   - a few vents and hatches;
   - painted panel-colour variation on big flat areas;
   - small clusters of antennas, sensor domes or pipes.

   Use them **in deliberate places, not everywhere**.

Rules that make this work under the game's shading:
- **Focal areas and rest areas.** Concentrate detail where the player looks and attacks: the bridge, the engines and pylons, the hangar bays, the radiator spine and the prow's face. Leave calm stretches of plain armour between them. The contrast is what makes the detail read.
- **Ink-line budget.** Every sharp edge draws a black line. Put creases where the form changes, and paint the rest (colour changes draw no line). Don't bevel every edge; chamfer only the big ones that shape the silhouette.
- **Big flat areas get painted variation, not geometry noise.** Use two or three close greys in large panels, plus a few crimson bands or markings in strong, simple shapes (chevrons, stripes, a Venom emblem area). Avoid a uniform checkerboard of tiny plates.
- **The belly sits in shadow** (the sun is overhead), where close greys look the same. Underneath, what reads is shape and light: a few strong steps in the keel, window rows, a lit vent or two, running lights.
- **Glow is a highlight.** Use acid green on the radiators and a few conduits, amber or white-ish for windows, red-orange for engines and red for running lights. Keep each glow colour to its own job so the ship doesn't look like a light show.

### Size, layout and the game's needs
- **Keep the Juggernaut's layout** (proportions, part positions, turret mounts) unless the form pass needs a change; report any change. Its blockout size is 670 × 221 × 168 m. Stay within **600–800 m** long, and keep the cross-section inside the **220 m portal circle** (centred 30 m above the origin).
- **True scale.** Model in real metres. There's no `SCALE` factor this time, unlike the old build script.
- **Origin and facing:** as in Stage A. Origin on the centre line, mid-length, at about the level of the main hull's underside. Bow towards Blender +Y.
- **Parts:** separate objects, each modelled round its own pivot:

  | Object | Pivot | Notes |
  |---|---|---|
  | `Juggernaut_Hull` | ship origin | Everything that isn't a part. It can be several objects in a `Hull` collection if that's easier (`Juggernaut_Hull_*`); the export merges them. |
  | `Juggernaut_Bridge` | centre of its base | The whole stern castle block that can be destroyed: windows, antennas, sensors. It's charred and dark when destroyed, so it must look like a separate structure, with a recognisable "head". Targeted as a sphere of about 50 m radius, so keep it compact. |
  | `Juggernaut_ThrusterKeel`, `Juggernaut_ThrusterPod` | nozzle centre | The centre engine and the pylon engine; the pod model is used twice, mirrored. Nozzles face aft (−Y), with a glowing core (`Destroyer_EngineGlow`). Each is targeted as a sphere of about 30 m radius. The pylons belong to the hull, the engines to the parts. |
  | `Juggernaut_HangarDoor` | door centre | One door for the left side (mirrored for the right). About 78 × 36 m (±25 %), up to 4 m thick. Painted hazard or crimson stripes facing out. |
  | `Juggernaut_Launch_L/R` | (empty) | Empty objects at the mouth of each bay, where fighters appear. |

- **Hangar bays.** A real recess behind each door, at least 20 m deep, with dark walls (`Destroyer_Dark`), a frame round the opening, and the slide-up strip above the door left clear. The game adds the glow inside the bay itself, so don't make the bay glow. Keep the four Stage A2 checks passing, and **measure them on this model** (the round-two numbers were identical across all four concepts, which suggests they were copied rather than measured).
- **Turret mounts.** Eight flat, level pads, each 10 m across, with open sky above. Name them as empties `Juggernaut_TurretMount_1..8`, at the pad's centre on its surface. The game places a turret at each.
- **The model must be clean.** The blockout's top view shows a ragged dark patch on the left of the bridge (in concept A too): find and fix it. Report non-manifold edges and flipped normals: there should be none, except on intentionally open surfaces, which must face outwards.

### The turret: `Juggernaut_Turret`
A new turret in the Juggernaut's style, used 8 times. The current one is a cylinder base, a dome and two barrels. Make it chunky, industrial and readable from 300 m: a heavy armoured head with two barrels, and maybe a sensor eye in acid green or red.
- **Three objects, one per moving part:**
  - `Turret_Base`: fixed. Origin at the mount surface (Z = 0), about 8–10 m across.
  - `Turret_Yaw`: the head, which turns round Z. Origin on the yaw axis, about 3 m up.
  - `Turret_Pitch`: the barrels, which tilt from −5° to 80°. Origin on the pitch axis, about 1.8 m above the yaw origin.
- **Muzzles:** two empties `Turret_MuzzleL` and `Turret_MuzzleR` at the barrel tips, about 2 m apart and about 9–10 m forward (towards +Y) of the pitch axis, parented to `Turret_Pitch`.
- **Size:** it must fit in a sphere of about 5 m radius centred 3.75 m above the base (its collision), barrels excepted.
- **Pitch clearance:** the barrels must be able to pitch to 80° without passing through the head.
- **Budget:** 1,500 triangles.

### Colours
Keep the Juggernaut palette and prefix (`Destroyer_`). Hull greys 0.12–0.30 sRGB (the light is bright), crimson markings, `Destroyer_GlowGreen` for the radiators, amber `Destroyer_Window`, `Destroyer_EngineGlow`, red `Destroyer_RunningLight`. List every material with its colour and emission in the report.

### Budgets
- Hull: 60,000 triangles.
- Bridge: 6,000.
- Each thruster: 3,000.
- Door: 1,000.
- Turret: 1,500.

The old destroyer's hull was about 42,500 triangles, mostly a carpet of armour plates; spend yours on secondary forms instead.

### Pass C1: the form pass (do this first)
Primary and secondary forms for the hull, bridge, thrusters, doors and turret, at the final shapes, with materials roughly assigned. No windows, lights, panel painting or greebles yet; keep it under about half of each budget. This is where the user judges the shape, so get the silhouette and the structure right.
- **File:** `models/destroyer/source/juggernaut.blend`. Copy the Juggernaut blockout in as a starting point if useful; leave `destroyer_concepts.blend` unchanged.
- **Screenshots** in `models/destroyer/source/juggernaut_preview/` (with a `.gdignore` folder above it, as before), named `C1_<view>.png`:
  - `hero`, `side`, `top`, `rear`, `below` (three-quarter from below), `hangar` (as in A2, corridor box shown), `bridge` (a close view from 150 m), `turret` (the turret at 20 m, barrels raised to 45°), and `silhouette` (side, front three-quarter and top as pure black on white, side by side).
  - Render them in **Workbench** with **Flat** lighting, **Outline** on and material colours, so the look is close to the game's flat colours and ink lines.
- **Report** triangle counts per object, the bounding box, part pivots, turret mount positions, measured hangar checks and portal clearance, and any change from the blockout layout. **Then stop.**

### C1 review 1: redo the form pass
The user reviewed the first C1 screenshots and sent the form pass back. It's an improvement on the blockout: the radiator trench with its bridging arches, the framed hangar doors, the stepped deck and the prow chevron are all good. Keep those. But the forms are still weak, and most of the "structure" is flat slabs laid on a plain hull. Fix the following, then deliver C1 again (same deliverables, overwriting the `C1_*.png` screenshots).

1. **The silhouette must show the Juggernaut.** On `C1_silhouette.png` the side and top read as a plain capsule with a box on top. The ship's three signature features must each show in silhouette, from the side, the front three-quarter view and the top:
   - **the battering-ram prow:** stepped tiers and a jutting ram that break the outline at the bow;
   - **the stern castle:** a tall, distinct block with an overhanging brow, clearly separate from the hull;
   - **the engines hung on pylons:** visible struts carrying the pods clear of the hull, with a gap of open space between pod and hull that you can see through from the side or top.

   Re-render the silhouette sheet and check it yourself.
2. **Real volumes, not surface plates.** The armour belt, ribs and the grey rectangles on the flanks are thin plates on one smooth hull. Build the hull from several stepped and overlapping volumes instead: modules that change the cross-section, a raised spine, side sponsons, a keel that steps down in two or three tiers, buttresses that stand out several metres. The hull is at about 2,700 triangles of a 60,000 budget, so there's plenty of room; aim for roughly 10,000–20,000 in this pass, spent on these forms.
3. **The engines must look lit.** In `C1_rear.png` each nozzle is a thin orange ring around a flat grey disc, as if capped. Fill the throat with the glowing core (`Destroyer_EngineGlow`), set a little back inside a deep, flared bell, so the engines read as burning from behind and at an angle.
4. **The bridge needs a head.** It's still a box with a sloped orange face. Give it a recognisable command head: a distinct upper block with an overhanging brow or visor, a continuous lit window band (`Destroyer_Window`) wrapping the front and sides, and a neck or stepped base that separates it from the castle below. It's the main target, so it should be the most characterful shape on the ship.
5. **Fix the turret.** In `C1_turret.png` the barrels come out through the top of the head, as if passing through it, and the barrel housing is as big as the head. Mount the barrels in a mantlet on the **front face** of the head, on the pitch axis, so they pivot out of a slot. Keep the barrels slimmer than the head is tall, and make the sensor eye part of the head's form (a recessed slit or lens), not a decal. Show it at −5°, 45° and 80° pitch in the turret screenshot, to prove there's no clipping.
6. **Measure the hangar checks on this model.** Every concept so far, and this pass, reported exactly 38.0 m above the door and a 395 m strafing run, whatever the hull shape. Measure all four checks fresh on the final C1 geometry, show the method (ray counts, the corridor box bounds, the strafing line and where the clear run starts and ends) and report the actual numbers, even if they're uneven.

Leave the parts' names, pivots and the turret mount layout as they are unless a fix needs a change, and report any change.

### C1 review 2: one change, the stern
The user likes the second C1 form pass. **Keep everything as it is**, except one thing: the detached side thrusters. The keel thruster is fine. The pylon-mounted pods are out. Instead, make two changes:

- **Move the side thrusters inward** from X = ±96 m to about **X = ±62 m**, keeping their height (Z ≈ 36 m, so the keel thruster still sits slightly lower, in a shallow V). That leaves a gap of about 20 m between nozzle rims, so the three stay separate targets. Their targeting spheres (about 30 m radius each) may touch, but the rims must not.
- **Widen the stern into an armoured engine block** about **170 m across** (X ≈ ±85 m), flaring out from the hull over roughly the last 100 m of its length, so all three engines are built into one heavy stern mass. Remove the pylons and struts. Give the block the same treatment as the rest of the hull (stepped volumes, a few strong creases, structural ribs or cowls round each engine housing), so it reads as part of the barge, not a box bolted on.

Constraints:
- **The nozzles stay exposed.** Each nozzle and its glowing core sticks out at least **15 m** past the back face of the engine block. Each must be visible and hittable from directly behind, from 45° above and from 45° below. Measure this with rays from those directions to each nozzle's centre and report the result.
- **The portal still fits.** The cross-section stays inside the 220 m portal circle (centred 30 m above the origin). Report the measured clearance.
- **The rest is unchanged:** hangar doors, the slide strip above them, turret mounts 7 and 8 on the castle, the keel thruster.
- **Part objects and pivots:** `Juggernaut_ThrusterPod` stays the model used for both side engines, so update its pivot positions and report them. If the pod's housing becomes part of the hull's engine block, keep only the nozzle and core in the part object, so a destroyed engine chars without charring the hull.

Re-render from the **final** saved file (the previous screenshots were saved 20 minutes before the `.blend`): `C1_silhouette`, `C1_top`, `C1_rear`, `C1_below`, `C1_hero` and `C1_side`. Look at them yourself before reporting. Report the new bounding box, portal clearance, thruster pivots, the exposure measurements and triangle counts. **Then stop.**

### C1 review 3: redo the stern from the approved version, at 1.5× size
The review 2 run got the stern right but also changed things it was told to keep: it removed the green radiator trench and its arches, changed the material colours, flattened the flanks and changed the render look. That version is rejected. Start again from the approved version, and make two changes only.

**Start from the approved script.** The script that built the approved model (your `build_c1_juggernaut_v8.py`) is now in the project as `models/destroyer/source/juggernaut_c1_approved.py`. Your review 2 script is beside it as `juggernaut_c1_stern_attempt.py`, for reference: reuse its stern code if it helps. Copy the approved script to a **new file**, `models/destroyer/source/juggernaut_c1.py`, make the changes below in that copy, and run it. Leave `juggernaut_c1_approved.py` and `juggernaut_c1_stern_attempt.py` unchanged.

**Change 1: the stern** (as in review 2, numbers before scaling):
- The pylons and struts are removed.
- The side thrusters move to X = ±62 m, at Z = 36 m.
- The stern widens into an armoured engine block about 170 m across, flaring over the last ~100 m, with all three engines built in.
- The nozzles stick out at least 15 m (before scaling) past the block's back face.
- `Juggernaut_ThrusterPod` keeps only the nozzle and core.

**Change 2: scale the ship by 1.5.** The user wants the destroyer 1.5 times its current size: about 1,030 m long instead of 685 m.
- Add a `SCALE = 1.5` constant and apply it to **everything that defines the ship's size and layout**: the hull, bridge, thrusters, hangar doors and bays, the part pivots, the launch points and the turret mount positions.
- **Don't scale the turret** (`Turret_Base`, `Turret_Yaw`, `Turret_Pitch`, the muzzles) or the 10 m turret mount pads. They stay at their real size, so a bigger ship carries the same-sized guns.
- The simplest way: keep every layout number in the script as it is, and multiply by `SCALE` where geometry and positions are created (as `G()` did in the old `build_destroyer.py`).

**Everything else stays exactly as in the approved script**, including:
- the radiator trench, its green glow and its arches;
- the hull forms, the bridge and the turret;
- the material names and **colours** (`COLORS`);
- the render setup (lighting, background, outline) and the camera framing, adjusted only for the bigger size.

The user will check this: I'll compare `juggernaut_c1.py` with `juggernaut_c1_approved.py` line by line. **Every difference must belong to one of the two changes.** If you find you need any other change, don't make it: describe it in your report instead.

**Measure on the final geometry, after scaling:**
- the bounding box;
- the portal clearance: it should come out at about 215 m against the 220 m limit, and if it's over 220 m say so rather than shrinking the ship;
- the nozzle exposure from behind and from 45° above and below;
- the four hangar checks, with the strafing line **60 m out from the hull's side** (the brief allows 40–100 m; the last run measured 17 m);
- the part pivots, turret mount positions and triangle counts.

**Then:**
1. Save the `.blend`.
2. Re-render **all nine** `C1_*.png` views from the saved file, and delete the stray `test_hero.png`.
3. Look at the renders before reporting.
4. Report, then stop.

### C1 approved; notes for C2
The user approved the C1 form pass built by `juggernaut_c1.py` (review 3: the armoured stern, at 1.5× size). Pass C2 builds on it as follows:

- **Work in a new script.** Copy `juggernaut_c1.py` to `models/destroyer/source/juggernaut_c2.py` and make all C2 changes there. Leave `juggernaut_c1.py` and the other scripts unchanged. The script must rebuild the whole ship by itself when run, with no runtime patches or wrappers: whatever you need to change goes into the script.
- **Fix the two script bugs you found** in that copy:
  - `object_outline_color` takes three values in Blender 5.2;
  - `setup_all_materials()` must not reset the faces' material indices.
- **Keep the C1 forms.** C2 adds detail and refines; it doesn't remove or reshape what was approved, apart from the three refinements below. I'll compare `juggernaut_c2.py` with `juggernaut_c1.py` again: every difference must be detail, one of these refinements, the two bug fixes, collision, markers or export code.
- **Three refinements** carried over from the C1 review:
  1. **Flanks:** the flank "volumes" are still mostly flat rectangular panels on one smooth hull. Give the flanks real stepped volumes: armour blocks that stand out several metres and change the cross-section, as the Style section describes.
  2. **Belly:** the keel is a single beam with ribs. Do the same there: two or three keel tiers and a few big blocks.
  3. **Bridge:** it reads as a stack of slabs (plinth, amber band, lid, roof). Give the command head more character: shape the visor brow, give the window band some depth, make the head distinct from its neck. It's the main target, so it should be the most recognisable shape on the ship.
- **Scale:** the ship is built at `SCALE = 1.5`. **Tertiary detail is sized in real metres**: windows about 1.8 × 0.9 m, lights 1–3 m, hatches and vents a few metres. Don't multiply detail by `SCALE`: a bigger ship gets more windows, not bigger ones. The turret and its mount pads stay unscaled, as in C1.
- **Collision pieces** are in the scaled ship's real size, covering it within a few metres.
- **Report the portal clearance as measured**, as in C1: it's about 229.5 m against the 220 m limit, and the game's portal will be enlarged to fit.

### Pass C2: the detail pass (only after the user approves C1)
Add the tertiary detail and painted variation by the rules above. Then build:
- **Collision:** a `Collision` collection of 10–20 convex, closed meshes named `Col_<Name>` that together cover the hull closely (within a few metres; small details can be left out, but every surface a fighter could hit must be covered). The parts don't need collision pieces: the game gives them their own.
- **Export**, glTF binary, +Y up, Apply Modifiers on, materials exported, each to its own file in `models/destroyer/`. The current files stay untouched.

  | File | Contents |
  |---|---|
  | `juggernaut_hull.glb` | the hull |
  | `juggernaut_bridge.glb` | the bridge, at its pivot |
  | `juggernaut_thruster_keel.glb` | the keel thruster, at its pivot |
  | `juggernaut_thruster_pod.glb` | the pod thruster, at its pivot |
  | `juggernaut_hangar_door.glb` | one door, at its pivot |
  | `juggernaut_turret.glb` | the turret, with its three objects and two muzzle empties as nodes |
  | `juggernaut_collision.glb` | only the `Col_` meshes |
  | `juggernaut_markers.glb` | only the empties: part pivots, launch points, turret mounts, named as above |

- **Screenshots** `C2_<view>.png`: the same views as C1, plus a `detail_*` close-up of each focal area.
- **Report:** as for C1, plus the exported files.

Hooking the new ship into `enemies/destroyer.tscn` (positions, radii, collision, AI avoidance spheres, hull outline, turret scene) is done afterwards, not by you.

---

## Not in this brief
- **The Arwing** (the player's and wingmen's ship): an imported, licensed model the game depends on by material name. Leave it.
- **Effects:** the warp portal, lasers, explosions, smoke, wrecks' debris, engine glows, space dust, the starfield and the planet in the sky are shaders or are generated by the game.
