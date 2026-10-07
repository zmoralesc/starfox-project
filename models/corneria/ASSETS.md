# Corneria asset brief

This file asks for 3D models for the Corneria level of **Star Fox: Ascent**, a Godot 4 fangame in the style of *Star Fox 64*.

Today the whole level is built from code. One Blender script, [source/build_corneria.py](source/build_corneria.py), makes every building from plain boxes, cylinders and domes. Each asset below replaces one of those shapes with a hand-designed model. Afterwards the script will place the new models where the old shapes stood.

Read the **global brief** first: every prompt depends on it. Each asset prompt then gives:
- what the piece is and where it's used;
- how many times it appears;
- its required size;
- what it should look like.

---

## Global brief (applies to every asset)

### How the models are seen
- **The player's view.** The player flies a small fighter at 60–130 m/s, usually 20–300 m above the ground. Most props pass by at 50–600 m. Silhouettes and big colour shapes are what read; detail under about 1 m is invisible.
- **Flying through and around.** The player flies between, around and under the props, including under the arches and the river bridge. Openings meant to be flown through must keep the sizes given here.
- **The level's layout.** It's 8 × 8 km. The open sea and the approach are to the south. A bay with stone arches runs north to Corneria City, which sits at a river mouth. A plateau with a lake and waterfall lies to the north-east, a harbour town is on the east coast, and a military base is to the west.

### Art style
- **Overall look.** Clean, bright, optimistic cartoon sci-fi, in the spirit of *Star Fox 64*'s Corneria:
  - smooth white and pale-grey buildings with blue glass;
  - bold simple forms and gentle curves;
  - red accents.

  It shouldn't look realistic, gritty or weathered.
- **Shading.** The game cel-shades everything: three hard light bands and black ink outlines.
- **Where ink lines go.** They're drawn on every silhouette, and on every edge where the surface normal changes sharply.
  - Each bevel, chamfer or small step adds another ink line, so a busy model turns into a tangle of black lines. Prefer **big clean planes and a few strong creases**.
  - **Curved surfaces** (cylinders, domes, arches) should be **smooth-shaded**. Use Shade Auto Smooth at about 30°, so only intended creases get lines. Flat-shaded facets on a curve draw a line on every segment. 12–24 segments are enough for most round shapes.
  - **Colour changes draw no ink line.** Paint windows, stripes and markings by giving coplanar faces another material, not by modelling recesses or raised strips.
- **Lines fade with distance.** Outlines fade out between 220 and 520 m from the camera, so big landmarks must also read by colour and shape alone.

### Colours and materials
Use **flat-colour materials** from the shared palette below. Name each material exactly as listed, since the game finds some materials by name. The values are **sRGB, 0–1**: the colours as they appear in the game. The build script converts them to linear for glTF; in Blender, set the Base Color so it shows the same colour.

The light is bright, so avoid pure white (1, 1, 1) on large surfaces; it blows out.

| Material | sRGB | Use |
|---|---|---|
| `Corneria_Tower` | 0.84, 0.86, 0.90 | main building white |
| `Corneria_Glass` | 0.30, 0.55, 0.80 | windows, glass towers |
| `Corneria_Concrete` | 0.72, 0.68, 0.60 | bases, plinths, piers |
| `Corneria_RoofDark` | 0.36, 0.37, 0.42 | roofs, caps |
| `Corneria_Road` | 0.27, 0.27, 0.30 | tarmac |
| `Corneria_Stone` | 0.76, 0.68, 0.53 | arches, piers |
| `Corneria_Wall` | 0.93, 0.91, 0.86 | houses, tanks |
| `Corneria_Roof` | 0.75, 0.38, 0.28 | house roof tiles |
| `Corneria_Lighthouse` | 0.82, 0.18, 0.14 | lighthouse red |
| `Corneria_Military` | 0.45, 0.50, 0.42 | base buildings, vehicles |
| `Corneria_Marking` | 0.95, 0.95, 0.90 | painted lines |
| `Corneria_Steel` | 0.60, 0.62, 0.66 | masts, cables, decks |
| `Corneria_BridgeRed` | 0.75, 0.25, 0.18 | bridge towers, lattice, flag |
| `Corneria_Rock` | 0.55, 0.50, 0.46 | sea stacks, cliffs |
| `Corneria_Tree` | 0.18, 0.40, 0.20 | foliage, dark |
| `Corneria_TreeLight` | 0.27, 0.50, 0.22 | foliage, light |
| `Corneria_Falls` | 0.80, 0.90, 1.00 | falling water |
| `Corneria_Foam` | 0.95, 0.98, 1.00 | foam |
| `Corneria_WarningLight` | 1.00, 0.20, 0.15, emission 6 | red aircraft lights |
| `Corneria_Lamp` | 1.00, 0.90, 0.50, emission 8 | lighthouse lamp |

Rules for materials:
- **New materials** are fine when a prompt needs them. Prefix them `Corneria_`, keep them flat-coloured, and list them in your report.
- **Textures** are allowed but not needed. The game keeps only the colour texture and the emission texture; normal, roughness and metal maps are thrown away, because fine detail becomes speckle under hard light bands.
- **Glowing parts** use emission (Emission Color = Base Color, strength as listed).

### Technical rules
- **Units and axes:** Blender units are metres. Blender is Z-up, and the game converts on export.
- **Front:** the asset's front (main entrance, the side the player sees on approach) faces **Blender −Y** (south in the level, towards the player's start).
- **Origin:** at the centre of the footprint at ground level (Z = 0), unless the prompt says otherwise. Apply all transforms (scale 1, rotation 0).
- **Normals point outwards.** The game draws **only the front of each face**: a face whose normal points inwards is invisible from outside. Blender shows both sides by default and hides the mistake, so check every asset with **Viewport Shading → Backface Culling** turned on. Open surfaces (a sheet, a dome without a floor, a flag) must face the side the player sees; make them double-sided by modelling thickness, not by relying on a material setting.
- **Solid props are closed meshes.** The game builds collision straight from the visible mesh, so:
  - no holes, no loose internal faces, no zero-area faces;
  - merge the vertices at seams;
  - small protruding parts collide too; that's fine.
- **What not to include:** no modifiers left unapplied, no armatures, animation, lights or cameras.
- **Polygon budget:** stay within each asset's triangle budget. Many pieces are repeated hundreds of times; trees are repeated about 6,000 times.
- **Height and size changes:** many pieces are placed at varied sizes. Each prompt says which axes the placement script will scale and by how much. Keep details that would look wrong when stretched (round windows, domes) to parts the prompt keeps unscaled. For tall towers, use the modular **Base / Shaft / Crown** split described in those prompts.

### Delivery
- **Blender file:** put all assets in one library file, `models/corneria/source/corneria_kit.blend`, with **one collection per asset**, named exactly as the asset ID below (e.g. `Kit_SteppedTower`). Model each asset at the world origin, its origin as specified. A multi-part asset (Base/Shaft/Crown, variants) has one object per part, named `<ID>_<Part>` (e.g. `Kit_SteppedTower_Shaft`).
- **Preview files:** also export each collection as `models/corneria/kit/<ID>.glb` (glTF binary, +Y up, Apply Modifiers on, materials exported, selected objects only), so it can be previewed in Godot.
- **Files not to touch:** `build_corneria.py`, `corneria_map.tres`, `corneria_props.glb` or any `.tscn` scene. Placing the kit into the level is a separate step. Don't commit; the user reviews first.
- **Report:** for each asset, give:
  - its triangle count;
  - its bounding-box size;
  - where its origin is;
  - the materials it uses;
  - a viewport screenshot (front three-quarter view, backface culling on).

---

## Landmarks (one of each)

### 1. `Kit_Spire`: the Corneria City central spire
**Used:** once, at the centre of Corneria City. It's the tallest thing on the map and the player's main navigation landmark.
**Size:** 340 m tall to the tip of the antenna. Footprint up to 124 m across (the plinth). Not scaled.
**Budget:** 6,000 triangles.

> Design the central spire of Corneria City: a 340 m futuristic glass-and-white tower, the icon of the planet's capital, seen from every part of an 8 km map.
>
> **Plinth:** a round concrete plinth (`Corneria_Concrete`), 124 m across and 18 m high, with the tower rising from its centre. Give it a broad stepped or sloped edge so it reads as a grand base, and a few large entrance openings painted, not cut, in `Corneria_Glass`.
>
> **Shaft:** three tapering tiers of blue glass (`Corneria_Glass`):
> - from 18 to 130 m, narrowing from 30 to 22 m radius;
> - from 130 to 225 m, from 22 to 14 m;
> - from 225 to 295 m, from 14 to 5 m.
>
> **Collars:** at each tier break, a projecting white collar ring (`Corneria_Tower`), about 6 m wider than the glass and 3 m deep, like an observation deck.
>
> **Accents:** you may add two or three slim white vertical fins or ribs running up the tiers, to make the silhouette more distinctive than a stack of cones, keeping the overall taper.
>
> **Top:** a steel antenna (`Corneria_Steel`) from 295 to 340 m, tapering from 1.6 to 0.4 m radius, with a 3 m red warning light (`Corneria_WarningLight`) at the very top.
>
> **Style:** smooth-shaded curves, crisp creases only at the tier breaks and collars. Origin: centre of the plinth's base.

### 2. `Kit_RiverBridge`: suspension bridge over the river mouth
**Used:** once, spanning the river mouth on the city's west side. The player is meant to fly under the deck and between the towers.
**Size:** deck 300 m long (along X), 20 m wide, its top at 30 m above sea level. Origin: the centre of the deck span at **sea level** (Z = 0), so the deck top is at Z = 30. Not scaled.
**Budget:** 5,000 triangles.

> Design a red suspension bridge in a cheerful cartoon style (think a simplified Golden Gate), spanning 300 m along the X axis.
>
> **Deck:** a steel box deck (`Corneria_Steel`), 20 m wide and 3 m deep. Its top surface is at Z = 30 and carries a two-lane road on top: `Corneria_Road` with dashed `Corneria_Marking` centre line, painted as faces.
>
> **Towers:** two towers at X = −75 and X = +75 (150 m apart). Each tower is two square legs (`Corneria_BridgeRed`, about 6 × 6 m) at Y = ±11, rising from Z = −10 (below the water line, so they look planted in the river bed) to Z = 104. Join the legs with three cross beams: just under the deck (about Z = 24), near the top (Z = 92) and capping the top (Z = 98–104). The opening between the legs and below the deck must stay clear: at least 16 m wide and 24 m tall above the water.
>
> **Cables:** two main cables (`Corneria_Steel`, about 1.4 m thick), one per side at Y = ±9. Each runs from the deck at each end of the bridge up to the tower tops (Z = 100), and sags between the towers to about Z = 42 at mid-span. Vertical hangers (0.7 m) drop from the cables to the deck roughly every 19 m.
>
> **Ends:** the deck ends are open (they join roads made by the level script). Leave each end as a clean flat cut, flush with X = ±150.
>
> **Style:** keep everything chunky enough to read at 400 m; no rivets or trusswork detail.

### 3. `Kit_StoneArch`: the bay's stone arches
**Used:** 6 times along the bay, scaled uniformly 0.92–1.08. They stand in the sea, and the player flies through them in a row heading north.
**Size:**

| Feature | Size |
|---|---|
| Opening width | 80 m between the pillars' inner faces |
| Clearance under the crown | 120 m above the water |
| Outer width | about 124 m |
| Depth | 20 m along the flight direction (Y) |
| Top | about 125 m above the water |

**Origin:** at **sea level** (Z = 0), centred in the opening. The pillar feet go down to Z = −22 (the seabed).
**Budget:** 3,000 triangles.

> **Draft:** a natural-arch draft already exists in `models/corneria/natural_arch.glb`. The user hasn't reviewed it yet; leave it alone and treat this entry as the spec.
>
> Design a monumental arch standing in the sea, one of a row of six that the player flies through. The flight line passes through the opening along the **Y axis**, so the arch's faces look north and south.
>
> **Form:** square-sectioned pillars rising from the seabed (Z = −22) into a semicircular arch. Keep these sizes:
> - **Opening:** the inner faces 80 m apart, the inside of the crown 120 m above the water.
> - **Masonry:** about 22 m thick around the opening, and 20 m deep.
> - **Capstone:** a capstone ledge along the top.
>
> **Material:** warm sandstone (`Corneria_Stone`). It can be either:
> - clean, monumental masonry: a few big blocks, a keystone, a plinth band at the water line in `Corneria_Concrete`;
> - weathered natural rock in `Corneria_Rock`, with a grassy cap in `Corneria_TreeLight`.
>
> Pick one and say which. Either way, keep the inner opening smooth and clear: no ledges or rocks jutting into the 80 × 120 m flight space.
>
> **Style:** smooth-shade the curve of the arch.

### 4. `Kit_SeaStack`: rock pillars off the coast (3 variants)
**Used:** 8 placements in the sea south of the coast, around the mission's start, rotated and scaled 0.85–1.15. The player weaves between them on approach.
**Size:**
- 150–230 m tall above the water. Make the three variants about 160, 195 and 230 m.
- Base 75–110 m across, tapering strongly to the top.
- Leaning up to 20 m off vertical.

**Origin:** the centre of the base at **sea level**. The rock continues down to Z = −25.
**Budget:** 800 triangles per variant.

> Design three tall, leaning sea stacks: rugged rock pillars rising out of the sea, tapering to a narrow top, like the stacks off a cartoon coastline.
>
> **Variants:**
> - `Kit_SeaStack_A`: tall and slender.
> - `Kit_SeaStack_B`: stout, with a ledge or notch partway up.
> - `Kit_SeaStack_C`: split into two peaks near the top.
>
> **Shape:** big faceted planes and a few strong ledges, in `Corneria_Rock`. These pillars should look hewn and craggy: here flat shading is fine, but keep the facets large, about 10 m and up, so the ink lines stay sparse.
>
> **Colour:** optional green tufts on top or on ledges (`Corneria_TreeLight`), and a pale foam ring at the water line (`Corneria_Foam`), sitting just at Z = 0–1.

### 5. `Kit_Lighthouse`: harbour lighthouse
**Used:** once, on a headland east of the harbour town.
**Size:** 58 m tall, base about 18 m across. Not scaled.
**Budget:** 1,500 triangles.

> Design a classic red-and-white striped lighthouse in a cheerful cartoon style.
>
> **Tower:** a slightly tapering round tower, 18 m wide at the base and 13 m at the top, in four 11 m bands alternating `Corneria_Lighthouse` (red, bottom band) and `Corneria_Wall` (white). Add a small door and two or three slit windows, painted not cut.
>
> **Top, from bottom to top:**
> - At Z = 44, a gallery platform: 20 m across, 2 m thick, `Corneria_RoofDark`, with a simple railing ring.
> - The lamp room, a glowing cylinder 9 m across and 6 m tall (`Corneria_Lamp`, emissive).
> - A red conical roof (`Corneria_Lighthouse`) from Z = 52 to 58, with a small ball or vent on top.
>
> **Base:** optionally a small keeper's hut attached at the base (white walls, `Corneria_Roof` roof), within a 30 m footprint.

### 6. `Kit_Waterfall`: the plateau waterfall
**No longer used.** The game draws the falls itself now (the `Waterfall` node, `world/waterfall.gd`, with a shader). The piece stays in the kit file but the script doesn't place it. The original brief is kept below for reference.

**Used:** once, where the plateau's river drops off a cliff. The lake and river surfaces are generated by the level, not modelled.
**Size:** 80 m wide at the lip, widening to about 100 m at the foot. It drops from Z = 120 to Z = 0, bowing out about 32 m from the cliff as it falls.
**Origin:** the centre of the lip at Z = 120. The water flows towards **−Y**.
**Budget:** 1,500 triangles.

> Design a cartoon waterfall: a broad sheet of water pouring over a cliff lip and curving outwards as it drops 120 m into a foaming pool.
>
> **Sheet:** a sheet, in `Corneria_Falls`, given a little thickness (about 2 m) so it has a front and back. Make it 80 m wide at the top and about 100 m wide at the bottom, curving out 16 m by Z = 85, 26 m by Z = 45 and 32 m at Z = 0.
>
> **Break-up:** break it into three to five vertical streams or ribbons, with a couple of narrow gaps, so it isn't one flat curtain. Add a few white streak strips in `Corneria_Foam` on the face.
>
> **Foot:** at the foot, a mound of billowing foam (`Corneria_Foam`) about 120 m across and 14 m high, made of several overlapping smooth domes, plus a few smaller foam puffs (25–45 m across) scattered downstream.
>
> **UVs:** give the sheet a clean UV layout where V runs top to bottom along the flow, so the game can later scroll a texture down it.
>
> **Normals:** check that all normals face outward, viewed from downstream.

---

## Corneria City kit

The city is a grid of 110 m blocks with 24 m streets, so each building must fit an 86 × 86 m plot. Tall towers stand near the centre; mid-rise and low blocks are further out.

**Rooftop light rule:** every tower taller than 100 m gets a `Kit_RoofLight` on top. The placement script adds it, so leave a flat spot or the antenna tip for it.

**Towers come in three parts:**
- `_Base`: fixed height.
- `_Shaft`: a section exactly **20 m tall** that stacks seamlessly on itself.
- `_Crown`: fixed height.

The script stacks shafts to reach heights from about 60 to 250 m, and may stretch the last shaft by up to ±25 % vertically. It also scales a whole tower by ±15 % in width and depth.

### 7. `Kit_SteppedTower`: stepped skyscraper
**Used:** about 30 % of the city's tall towers. Up to ~245 m with its antenna.
**Footprint:** 55 × 52 m (scaled 48–62 by 44–60).
**Budget:** Base 600, Shaft 300, Crown 800 triangles.

> Design a stepped white skyscraper in clean retro-futurist style, in three parts that stack.
>
> **`_Base`** (Z 0–20): the full 55 × 52 m footprint, in `Corneria_Tower`, with a glass lobby band (`Corneria_Glass`) and a slight plinth.
>
> **`_Shaft`** (20 m, tiles vertically): the full footprint, with white corners and horizontal glass bands. Each band is 3 m tall, painted as faces, with a 1 m projecting white ledge (`Corneria_Tower`). It must match itself perfectly top to bottom.
>
> **`_Crown`** (fixed, about 120 m tall): the two setbacks that give the tower its stepped look.
> - A middle tier at 78 % of the width and depth, about 60 m tall.
> - A top tier at 56 %, about 40 m tall.
> - Each setback has a glass band and ledge just below its roof.
> - A steel antenna (`Corneria_Steel`), 1.5 → 0.5 m radius, about 20 m tall, on top.
>
> **Style:** keep the setbacks crisp and the walls flat.

### 8. `Kit_RoundTower`: round glass tower
**Used:** about 25 % of the tall towers. Up to ~245 m.
**Footprint:** 22 m radius (scaled 18–26 m).
**Budget:** Base 600, Shaft 300, Crown 800 triangles.

> Design a cylindrical blue glass tower with white rings and a white dome, in three stacking parts. Use smooth shading throughout and 20–24 segments.
>
> **`_Base`** (Z 0–12): a wider concrete drum (`Corneria_Concrete`), radius 30 m, with painted glass entrances.
>
> **`_Shaft`** (20 m, tiles): a glass cylinder (`Corneria_Glass`), radius 22 m, with one projecting white ring (`Corneria_Tower`, 1 m proud, 2.5 m tall) at its middle. It must tile seamlessly.
>
> **`_Crown`:**
> - a white dome (`Corneria_Tower`), radius 22 m and 13 m tall;
> - a ring of small glass windows painted around its rim;
> - a tapering steel antenna (`Corneria_Steel`, 1.2 → 0.4 m radius, about 26 m) on top.

### 9. `Kit_SlabTower`: slab tower / mid-rise block
**Used:** about 25 % of the tall towers, plus about half of the mid-rise ring (36 × 56–76 m, 35–140 m tall).
**Footprint:** 55 × 38 m (scaled 36–64 by 32–76).
**Budget:** Base 400, Shaft 250, Crown 400 triangles.

> Design a rectangular glass slab tower framed by white corner columns, in three stacking parts.
>
> **`_Base`** (Z 0–10): a glass lobby, recessed 2 m, under the corner columns.
>
> **`_Shaft`** (20 m, tiles):
> - a glass block (`Corneria_Glass`) inset 2 m from the footprint;
> - four 6 × 6 m white corner columns (`Corneria_Tower`) running full height;
> - thin horizontal white floor lines every 4 m, painted as faces.
>
> **`_Crown`** (about 8 m): a white roof cap 4 m thick overhanging the glass, with one or two rooftop boxes (plant rooms, `Corneria_RoofDark`).
>
> **Stretching:** this one is stretched the most (36–76 m in depth), so avoid features that distort when stretched along Y.

### 10. `Kit_TwinTowers`: twin towers with a sky bridge
**Used:** about 20 % of the tall towers. Up to ~245 m.
**Footprint:** 63 × 38 m (scaled 56–70).
**Budget:** 2,500 triangles.

> Design a pair of square glass towers on a shared podium, linked by a sky bridge.
>
> **Podium:** 63 × 38 m and 14 m tall, in `Corneria_Concrete`.
>
> **Towers:** two glass shafts (`Corneria_Glass`), each 24 × 24 m, centred 20 m either side of the middle along X. The west (−X) tower is 100 % of the height; the east tower is 86 %. Each has a white cap (`Corneria_Tower`, 3 m) and white vertical corner trims.
>
> **Sky bridge:** at 62 % of the full height, a white sky bridge, 19 × 9 m and 7 m tall, with a glass band.
>
> **Parts:** deliver it with the same Base / Shaft / Crown idea:
> - **`_Base`:** the podium.
> - **`_Shaft`:** a 20 m section of both shafts that tiles.
> - **`_Bridge`:** the sky bridge as its own object (the script places it at 62 %).
> - **`_CrownWest` and `_CrownEast`:** one cap per tower.

### 11. `Kit_LowBuilding`: low block (3 variants)
**Used:** hundreds of times: the city's outer ring (34 × 34 m, 10–32 m tall), mid-rise blocks (38 × 76 m, up to 90 m) and the base's barracks (15 × 50 × 8 m). Scaled freely on all three axes.
**Budget:** 150 triangles each.

> Design three simple low-rise buildings, each modelled as a 10 × 10 × 10 m unit cube that the script stretches to any size (10–90 m tall, 15–76 m wide or deep). Because of that stretching, **use only flat faces, with all detail painted as material faces in proportions that survive stretching**.
>
> **Variants:**
> - `Kit_LowBuilding_A`: an office block. Walls `Corneria_Tower`, two horizontal window bands per 10 m.
> - `Kit_LowBuilding_B`: an apartment block. Walls `Corneria_Wall`, vertical window strips.
> - `Kit_LowBuilding_C`: a plain concrete block (`Corneria_Concrete`) with one band of windows near the top.
>
> **Roof:** each has a flat roof with a dark inset roof panel (`Corneria_RoofDark`, inset 10 % from the edges, 0.2 units high) and one small rooftop box.

### 12. `Kit_RoofLight`: rooftop aircraft warning light
**Used:** on top of every tower over 100 m and the tallest masts (a few dozen placements). Not scaled.
**Size:** about 3 m. **Budget:** 80 triangles.

> Design a small aircraft warning beacon for rooftops: a short steel post (`Corneria_Steel`) with a glowing red lens on top (`Corneria_WarningLight`, emissive). About 3 m tall overall, the lens about 2 m across.
>
> It must read as a bright red dot from 500 m, so keep the lens a big simple shape (a squat cylinder or a faceted ball). Origin: the bottom of the post.

### 13. `Kit_Street`: city street pieces
**Used:** across the whole city grid. The script lays straight runs and crossings.
**Size:** 24 m wide.
**Budget:** 40 triangles each.

> Design flat street tiles for a 24 m wide city street, 0.6 m thick. The top is at Z = 0.6 and the bottom at Z = 0, so the slab is 0.6 m thick.
>
> **Pieces:**
> - `Kit_Street_Straight`: 24 × 10 m along Y, tiling end to end. Tarmac `Corneria_Road`, with a 4 m pale pavement strip each side (`Corneria_Concrete`) and a dashed white centre line (`Corneria_Marking`, 3 m dashes in each 10 m).
> - `Kit_Street_Crossing`: 24 × 24 m. Tarmac with pavement corners and zebra crossings on all four sides.
>
> **Style:** all markings painted as faces, no raised geometry.

### 14. `Kit_StreetBridge`: street bridge over the river (modular)
**Used:** where city streets cross the river, about 4 bridges of 100–400 m.
**Size:** 24 m wide. Deck top at Z = 0 at the origin; piers go down to Z = −20.
**Budget:** 600 triangles per piece.

> Design a modular concrete-and-steel road bridge, 24 m wide, built from repeating spans.
>
> **`Kit_StreetBridge_Span`:** a 70 m deck section along Y.
> - **Deck:** a steel box deck (`Corneria_Steel`), 3 m deep, with a road surface matching `Kit_Street_Straight` and low parapets.
> - **Underside:** a gently arched underside or a simple girder line.
> - It must tile end to end seamlessly.
>
> **`Kit_StreetBridge_Pier`:** a concrete pier (`Corneria_Concrete`), 6 m thick across the flow and about 16 m wide, from the deck underside (Z = −3) down to Z = −20. The script places one at each span joint.

---

## Harbour town

### 15. `Kit_House`: harbour-town house (4 variants)
**Used:** 45 houses in the harbour town, rotated freely. Uniform scale 0.75–1.3, plus up to 1.6 × stretch in depth (Y).
**Reference size:** 18 × 24 m footprint, 10 m walls, ridge 6 m above the walls. Origin: footprint centre, ground level.
**Budget:** 300 triangles each.

> Design four seaside cottages in a cheerful cartoon Mediterranean style.
>
> **Style:**
> - white walls (`Corneria_Wall`);
> - terracotta pitched roofs (`Corneria_Roof`) overhanging about 1 m on every side;
> - painted windows and doors (`Corneria_Glass` windows, `Corneria_RoofDark` door), no recesses.
>
> **Variants:**
> - `Kit_House_A`: simple gable house, the ridge along Y.
> - `Kit_House_B`: two storeys, with a chimney.
> - `Kit_House_C`: L-shaped, two roof ridges meeting.
> - `Kit_House_D`: a small shop with a striped awning on the front (−Y) face. The awning can be any bright colour; add a new `Corneria_` material.
>
> **Roof faces:** the roof is an open shape. Model it with thickness, or make sure every face points outward, including the underside of the overhang (seen from below when flying low).

### 16. `Kit_Pier`: stone harbour pier
**Used:** 3 times, jutting south from the harbour into the sea.
**Size:** 14 m wide, 240 m long along Y, deck top 3 m above sea level. Origin: the shore end, at sea level, centred.
**Budget:** 400 triangles.

> Design a long stone harbour pier (`Corneria_Stone`), 14 m wide and 240 m long, extending along **−Y** from its origin (the shore end) out to sea.
>
> **Deck:** at Z = 3, with a low parapet along one side, a few bollards, and a small lamp or beacon post at the far end (a `Corneria_Lighthouse` red cap).
>
> **Below the deck:** the sides drop to Z = −5 (below the water line). Add buttresses every 30 m. Optionally, a few steps down to the water.

### 17. `Kit_Boat`: small harbour boat (2 variants)
**Used:** 6 boats moored beside the piers, slightly rotated.
**Size:** 6 m wide, 16 m long. The hull's waterline is at Z = 0, sitting about 1 m into the water.
**Budget:** 250 triangles each.

> Design two small cartoon harbour boats, each 16 m long along Y with the bow at −Y.
>
> **Variants:**
> - `Kit_Boat_A`: a fishing boat. White hull (`Corneria_Wall`) with a red stripe (`Corneria_Lighthouse`), a small wheelhouse with glass windows (`Corneria_Glass`) towards the stern, and a short mast.
> - `Kit_Boat_B`: a small motor launch. Low, sleek hull, an open cockpit and a windscreen.
>
> **Hull:** smooth-shaded, a simple chunky shape.

---

## Military base

The Cornerian military base: a runway, hangars and support buildings on flat ground, all at one level. Use `Corneria_Military` (olive), `Corneria_Concrete` and `Corneria_Wall`, with `Corneria_Marking` details.

### 18. `Kit_Runway`: runway and taxiway pieces
**Used:** one runway (70 × 1,300 m), one parallel taxiway (30 × 900 m) and three cross taxiways (200 × 26 m).
**Budget:** 300 triangles per piece.

> Design flat airfield surface pieces, each 0.6 m thick, with the top at Z = 0.6. All markings are painted faces, not raised.
>
> **`Kit_Runway_Main`:** a 70 × 1,300 m runway along Y, in `Corneria_Road`. Markings in `Corneria_Marking`:
> - a dashed centre line (30 m dashes, 63 m apart);
> - six 4 × 40 m threshold bars at each end;
> - edge lines;
> - painted runway numbers at each end, as simple blocky numerals.
>
> **`Kit_Runway_Taxiway`:** a 30 m wide strip, 100 m long along Y and tiling, with a yellow centre line. Add a `Corneria_TaxiYellow` material, about (0.95, 0.80, 0.20).
>
> **`Kit_Runway_Apron`:** a 60 × 60 m concrete pad (`Corneria_Concrete`) with parking bays.

### 19. `Kit_Hangar`: Quonset hangar (2 variants)
**Used:** 4 large hangars beside the runway, plus 1 small one used as the mess hall.
**Size:**
- Large: 60 m wide, 30 m tall (a half-cylinder of radius 30 m), 90 m long along Y.
- Small: radius 11 m, 44 m long.

**Budget:** 1,000 triangles (large), 500 (small).

> Design a military Quonset hangar: a half-cylinder shell lying along Y, in `Corneria_Military`, smooth-shaded, with 16–20 segments over the curve.
>
> **Large hangar (`Kit_Hangar_Large`):**
> - **Front (−Y) end:** a large sliding door, 40 m wide and 22 m tall. Paint it as darker panels (add `Corneria_MilitaryDark`, about (0.30, 0.34, 0.28)) with door seams. Above the door, a painted unit number in `Corneria_Marking`.
> - **Back end:** closed, with a small personnel door.
> - **Ribs:** three or four subtle ribs over the shell, raised at most 0.5 m.
>
> **Small hangar (`Kit_Hangar_Small`):** a mess hall, radius 11 m and 44 m long. It has a normal door and a row of windows along each side instead of the big door.
>
> **Closure:** both ends must be closed walls.

### 20. `Kit_ControlTower`: airfield control tower
**Used:** once.
**Size:** 57 m tall including the beacon. Base about 12 m across, cab 24 m across.
**Budget:** 1,200 triangles.

> Design an airfield control tower.
>
> **Shaft:** a slender concrete shaft (`Corneria_Concrete`), 12 m across at the base and 10 m at the top, 45 m tall, with a vertical window strip.
>
> **Cab:** an octagonal glass cab (`Corneria_Glass`) from Z = 45 to 53, flaring outwards (22 m across at the bottom, 24 m at the top), with white mullions.
>
> **Roof:** a dark overhanging roof (`Corneria_RoofDark`, 26 m across, 2 m thick).
>
> **Top:** a small antenna, and a `Corneria_WarningLight` beacon on top at Z ≈ 55.
>
> **Base:** an optional low annex building at the base, within a 30 m footprint.

### 21. `Kit_RadarDish`: radar dish
**Used:** once.
**Size:** pole 20 m tall, dish 28 m across. **Budget:** 800 triangles.

> Design a radar installation.
>
> **Pole:** a steel lattice or tube pole (`Corneria_Steel`), 3 m thick and 20 m tall, on a small concrete pad.
>
> **Dish:** a 28 m parabolic dish (`Corneria_Wall` face, `Corneria_Steel` back and frame), tilted about 35° up and facing −Y, with a feed horn on struts at its focus.
>
> **Normals:** the dish is an open bowl. Give it real thickness, about 0.5 m, so both the inside and the back render.
>
> **Dish as its own object:** make it a separate object, `Kit_RadarDish_Dish`, with its origin at the pivot where it meets the pole, so the game can rotate it.

### 22. `Kit_FuelTank`: fuel tank
**Used:** 3 in a row.
**Size:** 20 m across, 14 m walls plus a 3 m domed roof. **Budget:** 500 triangles.

> Design a squat cylindrical fuel storage tank.
>
> **Body:** white walls (`Corneria_Wall`), radius 10 m and 14 m tall, smooth-shaded, with a gentle domed roof (3 m high).
>
> **Details:**
> - a red band near the top (`Corneria_Lighthouse`);
> - a painted hazard number;
> - a spiral or straight access ladder in `Corneria_Steel` (a flat strip, not individual rungs);
> - a low concrete bund ring around the base (`Corneria_Concrete`, 1 m high, 26 m across).

### 23. `Kit_Headquarters`: base headquarters
**Used:** once.
**Size:**
- Footprint about 76 × 92 m in an L shape: a 22 × 92 m wing along Y, plus a 54 × 22 m wing off its north end towards +X.
- 15 m tall (three storeys).

**Budget:** 2,000 triangles.

> Design the base's headquarters: a three-storey L-shaped administrative building, modernist and military-tidy.
>
> **Main wing:** 22 × 92 m along Y.
>
> **Second wing:** 54 × 22 m, joined at the main wing's north (+Y) end and extending towards +X.
>
> **Walls and roof:**
> - **Walls:** `Corneria_Wall`.
> - **Window bands:** three continuous horizontal glass bands (`Corneria_Glass`), 1.8 m tall, at Z ≈ 3, 8 and 12.5.
> - **Roof:** a flat roof with a dark inset (`Corneria_RoofDark`), and a few rooftop units.
>
> **Front (west, −X):**
> - **Porch:** an entrance porch on the main wing's west face (`Corneria_Concrete`, 8 × 12 m, 4 m tall), with a painted emblem above it.
> - **Flagpole:** in front of the porch, an 18 m steel flagpole with a red flag (`Corneria_BridgeRed`). The flag is a thin box, about 3 × 5 m and 0.3 m thick, so it's visible from both sides.
>
> **Roof antenna:** a 14 m steel antenna on the roof near the south end.

### 24. `Kit_Car` and `Kit_ParkingLot`
**Used:** a 56 × 36 m parking lot with about 11 cars.
**Budget:** car 120 triangles, lot 100.

> **`Kit_ParkingLot`:** a flat 56 × 36 m tarmac pad (`Corneria_Road`), 0.4 m thick, with the top at Z = 0.4. Paint two rows of eight parking bays in `Corneria_Marking`.
>
> **`Kit_Car`:** a chunky, toy-like cartoon car, 2.2 m wide, 4.4 m long along Y and 1.6 m tall, with the front at −Y.
> - Body in one material slot named `Corneria_CarBody`. The game will recolour cars, so model the body with that one material.
> - Windows in `Corneria_Glass`, wheels in `Corneria_RoofDark`.
> - Simple rounded shape, smooth-shaded.

### 25. `Kit_Depot` and `Kit_Truck`: maintenance depot and military truck
**Used:** one depot, 4 trucks parked in front.
**Size:** depot 64 × 36 m, 11 m tall; truck 3.4 m wide, 8 m long, 3.2 m tall.
**Budget:** depot 600 triangles, truck 250.

> **`Kit_Depot`:** a vehicle maintenance shed in `Corneria_Military`.
> - Four large roller doors on the front (−Y) face, in darker panels (`Corneria_MilitaryDark`).
> - A shallow-pitched roof (`Corneria_RoofDark`).
> - A painted hazard stripe along the door tops: alternating yellow and black, as painted faces. Add a `Corneria_HazardBlack` material, about (0.12, 0.12, 0.14), and use `Corneria_TaxiYellow` for the yellow.
>
> **`Kit_Truck`:** a chunky military utility truck, front at −Y.
> - Cab in `Corneria_Military`, with `Corneria_Glass` windows.
> - A canvas-covered cargo bed (`Corneria_MilitaryDark`).
> - Six chunky wheels (`Corneria_RoofDark`).
> - Toy-like proportions.

### 26. `Kit_Helipad`: helipad
**Used:** once. **Size:** 30 m across. **Budget:** 150 triangles.

> **`Kit_Helipad`:** a round concrete helipad, 30 m across and 0.4 m thick, with the top at Z = 0.4.
> - Dark surface (`Corneria_Road`).
> - A white edge ring and a white "H" (`Corneria_Marking`), painted as faces.
> - Four small yellow edge lights: low boxes in `Corneria_TaxiYellow`, raised 0.3 m.

### 27. `Kit_RadioMast`: lattice radio mast
**Used:** once (possibly reused on mountain tops later).
**Size:** 64 m tall, legs spreading to 8 m square at the base, 1.6 m at the top.
**Budget:** 1,200 triangles.

> Design a tapering four-legged lattice radio mast.
>
> **Legs:** four corner legs (`Corneria_BridgeRed`, 0.6 m square beams), tapering from an 8 × 8 m base to a 1.6 × 1.6 m top over 64 m.
>
> **Bracing:** diagonal cross braces (`Corneria_Steel`, 0.3 m) between the legs in four levels.
>
> **Bands:** alternate red and white (`Corneria_Wall`) bands on the legs, like aviation-marked masts.
>
> **Top:** a few small antenna panels near the top, and a `Corneria_WarningLight` beacon at the tip.
>
> **Style:** it should read as a red-and-white lattice from 300 m. The beams are thin, so keep their count modest: the ink lines will outline each one.

### 28. `Kit_GuardPost`: gate guard post
**Used:** once, where the road enters the base.
**Size:** booth 4 × 4 m, 3 m tall; barrier arm 14 m long.
**Budget:** 300 triangles.

> Design a small checkpoint at the base gate.
>
> **Booth:** a guard booth (`Corneria_Wall`, 4 × 4 m and 3 m tall) with glass windows on all sides and an overhanging flat roof (`Corneria_RoofDark`, 5 × 5 m).
>
> **Barrier:** next to it, a barrier post with a 14 m horizontal barrier arm at 1.2 m height, extending towards −X across the road. The arm is striped red and white (`Corneria_Lighthouse` / `Corneria_Wall`) and is 0.4 m thick.
>
> **Arm as its own object:** make the arm a separate object, `Kit_GuardPost_Arm`, with its origin at the hinge, so it could swing up.

---

## Vegetation

### 29. `Kit_Tree`: trees (3 variants)
**Used:** about **6,000 times**, in forest clumps on the hills and in city parks, rotated randomly and scaled 11–19 m tall. **No collision**: the player flies through them.
**Reference size:** 15 m tall, crown 10 m across.
**Budget:** **40 triangles** per tree (hard limit: they're drawn thousands of times).

> Design three very low-poly cartoon trees, readable from 50–500 m. Each is a few chunky shapes: no individual leaves or branches.
>
> **Variants:**
> - `Kit_Tree_Conifer`: two or three stacked cones of foliage in `Corneria_Tree`, with a short brown trunk. Add `Corneria_Trunk`, about (0.40, 0.28, 0.18).
> - `Kit_Tree_ConiferLight`: the same idea in `Corneria_TreeLight`, a slightly different shape.
> - `Kit_Tree_Round`: a round deciduous tree for city parks, a smooth-shaded low-poly ball crown in `Corneria_TreeLight` on a trunk.
>
> **Geometry:** 5–6 segments per cone. The bottom of each cone must be closed, or face outward, since players see the underside when flying low. The trunk base is at Z = 0 and goes 1 m below it (Z = −1), so trees on slopes don't float.

---

## Optional

### 30. `Kit_GreatFox` (optional, large job): the team mothership
**Why:** the current Great Fox model ([models/great_fox/](../great_fox/)) came without a licence. It appears behind the Corneria start and on every mission, so a home-made replacement would remove that problem.
**Size:** about 460 m long, 310 m wide, 100 m tall. Bow at −Y, origin at the middle of the hull.
**Budget:** 15,000 triangles.

> Design an original large starship carrier inspired by the Great Fox from *Star Fox 64*:
> - a long white-and-grey hull with a pointed bow;
> - two swept forward-reaching side prongs;
> - large rear engines;
> - blue and red accent stripes;
> - a glowing hangar opening (emissive) underneath.
>
> **Viewing distance:** it's seen only from far away (700 m and more, through haze), so favour a bold silhouette and large colour areas over detail.
>
> **Materials and normals:** follow the global brief: flat materials, outward normals, smooth-shaded curves. Name the materials `GreatFox_<Name>`.
>
> **Delivery:** export it to `models/great_fox_new/great_fox.glb` with its `.blend` source beside it.

---

## Not on this list (generated by the game or the level script)

Don't model these; they're built from data:
- **Terrain:** the ground, coast, plateau, cliffs, canyon, mesas and islands. It's a height grid in `corneria_map.tres`, with painted sand, grass, rock and snow.
- **Sea:** made by the game's water shader, including foam, wakes and splashes.
- **Plateau lake and river surfaces:** follow the terrain.
- **Road from the bridge to the base:** follows a graded curve. The script lays it as a ribbon; `Kit_Street_Straight`'s look is the reference for its markings.
- **Clouds, sky and fog.**

## Integration (done after delivery, not by the modeller)

`build_corneria.py` places these assets where its boxes used to stand (see `load_kit()` and `Batch.kit()`, and the GUIDE's Corneria section):
- It reads the kit from `corneria_kit.blend`, stacks tower parts to the required heights, and merges each group (`City`, `Town`, `Base`, `Arches`, `RiverBridge`, `SeaStacks`, `Water`, `Trees`) into one object.
- It re-exports `corneria_props.glb` and the AI's structure-height map, so wingmen and enemies keep flying over the buildings.
- Materials are matched by name to the script's palette; the colours set in the kit file are ignored.

To change a piece: edit it in `corneria_kit.blend` (same object names, origins and sizes), then re-run the script with `--export`. Keep the group names. Collision is built from the merged meshes by name, so nothing else in the game changes.
