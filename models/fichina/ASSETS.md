# Fichina: kit brief

This file specifies the 3D models ("kit pieces") of the Fichina map in **Star Fox: Ascent**, a Godot 4 fangame. The map is a Blender file, [source/fichina.blend](source/fichina.blend). Generator scripts lay it out from these pieces: the colony, the spaceport and outposts, the ice landmarks and the wilds. Until a piece is modelled it is a grey placeholder box ("greybox"). Each entry below replaces one with a real model.

The pipeline is the Corneria map's (see [../corneria/ASSETS.md](../corneria/ASSETS.md) for the brief it was built from); this brief repeats everything a modeller needs.

Read the **global brief** first; every piece depends on it. Each piece's entry then gives:
- what the piece is, where it stands and how many copies there are;
- its sizes, and how the generators stretch it;
- its triangle budget;
- what it should look like.

---

## Global brief

### How the models are seen
- **The player's view.** The player flies a small fighter at 60–130 m/s, usually 30–400 m above the ground, over a 16 × 16 km map. Most pieces pass by at 80–1,000 m, and the colony is seen from 5 km away. Silhouettes, big colour shapes and bold stripes read; detail under about 1.5 m doesn't.
- **Flying among them.** The player weaves between the colony's towers, round the Climate Control Center and through the ice arches. Openings meant to be flown through must keep the sizes given.
- **The map.** Fichina is a snow and ice planet. The map is landlocked: mountains on every side, a long glacial valley in from the south (the approach), a central basin with the **colony** round the **Climate Control Center**, a big frozen lake north-east of it fed by a glacier off the northern range, a high ice-shelf plateau in the east with a frozen waterfall down its cliff, mesas and a deep canyon in the west, pine forests in the south-west, and a **spaceport** in the south-east. Outposts (research stations, a mining rig, radar and dish arrays, masts) dot the high ground, linked by roads and pipelines.

### Light: polar dusk
The mission is played at **polar dusk**: the sun sits just above the horizon, warm orange-pink; the sky above is deep blue-violet with an aurora; the snow reads pink on its lit side and blue in shadow. Two consequences:
- **Lit windows matter.** `WindowLit` (warm amber, glowing) is the colony's signature at dusk: paint windows with it generously on the colony's buildings (bands, rows, a lit doorway). Use `Glass` / `GlassDark` for unlit glazing to vary it.
- **Strong silhouettes and colour blocks.** Long shadows and a dim sky flatten detail; colour blocks (white panels against signal orange, dark metal against snow) carry the forms.

### Art style: an arctic frontier colony
The target is *Star Fox 64* / *Star Fox Assault*'s Fichina crossed with real Antarctic research stations: a hardy, hopeful frontier colony, sci-fi but practical.
- **Architecture.** Insulated, rounded and raised:
  - modules **raised on stilts or short legs** above the snow, or on solid plinths;
  - rounded corners, barrel vaults, domes, drums, capsule shapes; thick insulated walls read as chunky panels;
  - **snow on the roofs**: flat and gently sloped roofs carry a `Snow` cap (a slab sunk slightly into the roof, or the roof's top faces painted `Snow`), so the colony looks snowed in;
  - masts, antennas, small radar domes and vents on the roofs.
- **Colour.**
  - bodies in white and pale-grey insulated panels (`Panel`, `PanelGrey`), with `DarkMetal` for frames, legs, roofs and machinery;
  - **signal orange** (`Signal`) as the colony's accent colour, as on Antarctic stations: whole modules, roof bands, stair towers, door frames; `SignalYellow` and `HazardBlack` for industrial hazard stripes;
  - pale cyan `LightStrip` (glowing) on the crowns and edges of the tall buildings and the Climate Control Center; `CoreGlow` (bright cyan, glowing) only for the Climate Control Center's core and the power plant's vents;
  - `Greenhouse` (glowing pale green) for greenhouse glazing.
- **Ice and nature.** Ice is faceted and crystalline (`Ice` faces, `IceDeep` for the shadowed or inner faces), rocks are cold dark faceted stone (`Rock`, `RockLight`) with `Snow` on their up-facing faces, and pines are dark (`Pine`, `PineLight`) and laden with snow (`PineSnow`).
- **Variety.** The variants within a piece should differ clearly in silhouette, not only in colour.

### How the game draws them
- **Cel shading.** Everything gets three hard light bands and black ink outlines.
- **Where ink lines go.** Lines are drawn on every silhouette and on every edge where the surface normal turns sharply.
  - Each bevel, chamfer or small step adds a line, so a busy model becomes a tangle. Prefer **big clean planes and a few strong creases**.
  - **Curves** (drums, domes, vaults) are **smooth-shaded**: `kit_tools` creases only where faces meet at over 30°. 12–24 segments are enough for round shapes; 8–10 for small ones.
  - **Colour changes draw no line.** Paint windows, stripes, doors and markings as coplanar faces of another material. Don't model them as recesses or raised strips.
- **Lines fade with distance.** They fade out between 220 and 520 m from the camera, so big pieces must read by colour and shape alone.
- **No floating pieces.** No part may hover off the body.
- **No coplanar overlaps.** No two visible faces of different parts may share a plane (they flicker). Where a part sits on another, sink it a few centimetres or make it larger.

### Colours
Use only palette materials: `fichina_common.PALETTE`, named `Fichina_<name>`. kit_tools' `Builder` takes the name without the prefix. The values are sRGB, as seen in the game.

| Name | sRGB | Use |
|---|---|---|
| `Panel` | 0.85, 0.87, 0.90 | white insulated panels: most building bodies |
| `PanelGrey` | 0.60, 0.63, 0.68 | grey panels, second body colour |
| `Steel` | 0.60, 0.62, 0.66 | tanks, pipes, masts, decks |
| `DarkMetal` | 0.28, 0.30, 0.35 | frames, legs, roofs, machinery |
| `Concrete` | 0.64, 0.64, 0.66 | plinths, pads, foundations |
| `RoofDark` | 0.34, 0.36, 0.41 | roofs where snow doesn't lie |
| `Glass` / `GlassDark` | 0.30, 0.55, 0.80 / 0.16, 0.30, 0.50 | unlit glazing |
| `WindowLit` | 1.00, 0.78, 0.45, glows | lit windows (generously, see Light) |
| `Greenhouse` | 0.62, 0.95, 0.55, glows | greenhouse glazing |
| `Signal` | 0.90, 0.32, 0.14 | signal orange: the accent colour |
| `SignalYellow` / `HazardBlack` | 0.95, 0.78, 0.20 / 0.12, 0.12, 0.14 | hazard stripes, industrial |
| `Marking` | 0.95, 0.95, 0.90 | pad and road markings |
| `LightStrip` | 0.55, 0.85, 1.00, glows | light strips on crowns and edges |
| `WarningLight` | 1.00, 0.20, 0.15, glows | aircraft warning lights on masts and tops |
| `Lamp` | 1.00, 0.90, 0.50, glows | floodlights, pad lights |
| `CoreGlow` | 0.45, 0.95, 1.00, glows strongly | Climate Control Center core, plant vents only |
| `Snow` | 0.93, 0.95, 0.98 | snow on roofs, rocks and ice |
| `Ice` / `IceDeep` | 0.62, 0.82, 0.95 / 0.35, 0.60, 0.85 | ice: lit faces / deep and inner faces |
| `Rock` / `RockLight` | 0.42, 0.42, 0.48 / 0.58, 0.58, 0.63 | cold dark rock |
| `Pine` / `PineLight` | 0.12, 0.28, 0.22 / 0.20, 0.38, 0.28 | pine foliage |
| `PineSnow` | 0.90, 0.93, 0.97 | snow lying on pine foliage |
| `Trunk` | 0.35, 0.25, 0.18 | trunks |

**Foliage** (`Pine`, `PineLight`, `PineSnow`, `Trunk`) is drawn **without ink lines** and casts shadows through stand-ins: use those four on trees only (snow on a tree is `PineSnow`, not `Snow`). A needed colour that isn't listed is added to the palette (in `fichina_common.py`, with a comment). Report it; don't invent materials in the model.

### Technical rules
- **Units and axes:** metres; Blender Z up.
- **Front:** a piece's front (main entrance, its street side) faces **Blender −Y**.
- **Origin:** at the centre of the footprint, on the ground (Z = 0). Parts that go below ground (stilts' feet, a rock's base) are given in the entry.
- **Normals point out.** The game draws only the front of a face, so a face pointing in is a hole. Pieces are **closed meshes**: the game builds collision from them, and the checks below find open edges and parts built inside out.
- **Separate shells are fine** (a roof box on a wall box), but they must overlap or touch cleanly; see "no coplanar overlaps".
- **Triangle budgets** are per piece (per part for stacks). Repetition sets them: there are tens of thousands of pines and seracs, and thousands of habitat blocks and cabins.

### Variants, stacks and stretching
The generators **fit most pieces to their lots**: they scale them on each axis to the width, height and depth the lot asks for. To keep that stretching small, a piece can come as a **family of variants**:
- **Naming.** `Kit_Colony_Hab_A`, `_B`, `_C`... each is its own collection. The generator picks the variant whose own proportions need the least stretching, choosing at random among near-ties, then fits it. Pieces placed at their own size get a random variant.
- **Placeholders.** The placeholder (`Kit_Colony_Hab`, marked `greybox`) drops out by itself once one real variant exists. Pieces without variants keep the plain name (`Kit_Colony_ClimateCenter`).
- **Designing variants.** Give variants **different proportions**, spanning the size range in the entry, and different silhouettes.

A tall piece can be a **stack**: three collections, `<variant>_Base`, `<variant>_Shaft` and `<variant>_Crown` (for example `Kit_Colony_Tower_A_Base`).
- **How it's placed.** The base stands on the ground, as many shafts as fit stand on it, then the crown on top. So a tower grows by whole storeys, and the base and crown are never stretched in height. The shafts take up any remainder by stretching: by up to half a shaft's height, shared among them.
- **Each part's origin** is at the centre of its own bottom face (Z = 0 at its bottom). All three parts are stretched by the same width and depth.
- **The shaft must repeat seamlessly:** its top outline equals its bottom outline; its painted bands line up across the joint; its bottom matches the base's top outline and its top the crown's bottom outline; keep it 1–4 storeys high (4 m a storey).
- **Joints.** Each part stands exactly on the measured top of the one below. A crown may reach below its own origin into the shaft (negative Z), but only with a part set back from the shaft's outline. Nothing overlaps shaft to shaft.
- **Joint plugs.** Each `_Shaft` and `_Crown` has a second object, `<part>_Plug`: a closed sleeve, its outline the part's bottom outline inset 0.05 m, from 0.4 m below its origin to 0.1 m above, in the joint wall's main colour. Plugs don't count in the part's measured size.
- **Open joints.** Where parts join flush they have **no cap** in the joint: shafts have no top or bottom cap, crowns no bottom cap, bases no top cap under a flush shaft (a wider podium keeps a ring-shaped roof). `kit_tools.check()` accepts open edges at those ends.
- **Footprint.** A variant's size is the widest of its parts, and the generator fits that to the lot.
- **Cap cost.** `prism()` caps take every cut on their edges, so each column cut round a shaft costs cap triangles too. Keep fins sparse.

Stretching still happens: each entry gives the range a piece is fitted to. Keep details that would look wrong when stretched (round windows, domes, discs) to pieces that are not stretched, or to stack crowns.

### Building pieces: scripts with kit_tools
Each batch of pieces is a Blender Python script, `source/kit/kit_<batch>.py`, built on Corneria's [kit_tools.py](../corneria/source/kit/kit_tools.py) (read its docstring). A Fichina kit script starts like this, so that kit_tools works on Fichina's kit and palette:

```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # models/fichina/source
import fichina_common as cc   # first: makes kit_tools serve Fichina
import kit_tools as kt
```

- `kt.begin(script, row)` (each batch has its own `row`, given below), then `kt.piece(name, [(suffix, Builder)])` for each piece, then `kt.finish()`.
- `kt.Builder` provides `prism()` (upright extrusions with sides split into painted cells), `box()`, `lathe()` (round shapes, cells too), `extrude()` (side profiles pushed back: gables, vaults, arches), `grid()` (painted panels), `face()`, and `at(matrix)` to build a part about its own origin and move, turn or mirror it.
- Vertices at the same spot merge, and normals are made outward per closed shell.
- A script may add its own helpers. **Don't change kit_tools.py** (Corneria's kit relies on it); put helpers in your script.

Running a script:
```sh
cd models/fichina/source/kit
KIT_OUT=<scratch>/kit_test.blend KIT_PREVIEW=<scratch>/previews \
  "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --python kit_<batch>.py
```
- **Where it builds.** `KIT_OUT` builds into a scratch copy (made from `source/kit.blend` the first time), which is always safe. Without it, the script writes `source/kit.blend`, the real kit; only do that when asked.
- **Checks.** `finish()` prints each piece's triangles, size (game width × height × depth), base height and centre, plus problems: open edges, parts facing in, zero-area faces, materials outside the palette. **Fix every problem.**
- **Previews.** `KIT_PREVIEW` renders each piece front three-quarter and back three-quarter, with backface culling on, so a face pointing in shows as a hole. **Look at every preview.**

Sizes below are **width (x) × height (z) × depth (y)** in metres.

---

## Batch 1: the colony's buildings (`kit_colony.py`, row 0)

### Kit_Colony_Hab: habitat blocks
- **Where and how many:** about 1,500, the bulk of the colony, on lots in its blocks.
- **Size:** fitted to 12–40 wide, 8–20 tall, 10–24 deep.
- **Variants:** A 30 × 12 × 14 (a long slab), B 20 × 16 × 20 (a block, three storeys), C 14 × 9 × 10 (small, two storeys), D 24 × 10 × 16 (a barrel-vaulted hall).
- **Budget:** 300 each.

> Insulated habitat modules, like a polar station's living blocks:
> - **form:** a chunky body raised 1.5–2.5 m on `DarkMetal` stilts or a solid `Concrete` plinth (stilts as a few chunky legs, at least 1 m thick); rounded ends, a vaulted or flat roof with a `Snow` cap;
> - **colour:** `Panel` or `PanelGrey` bodies; one variant mostly `Signal` orange; `Signal` accents (an end wall, a stair tower, a roof band);
> - **windows:** rows of `WindowLit` and `GlassDark` windows painted on, a lit entrance on the −Y front.

### Kit_Colony_Tower: colony towers (stacks)
- **Where and how many:** about 40, in the colony's core round the Climate Control Center, 45–110 m tall.
- **Size:** fitted square, 22–36 per side.
- **Variants:** stacks A (28 × 28, a square tower with rounded corners), B (30 across, a drum).
- **Parts:** base 10–14 m (a wide insulated podium with a lit lobby), shaft 3 storeys (12 m), crown 10–20 m (a snow-capped roof with a mast and a red `WarningLight`, or a small domed observation deck, `LightStrip` round its edge).
- **Budget:** base 400, shaft 200, crown 800.

> Residential and admin towers: `Panel` with continuous horizontal `WindowLit` / `GlassDark` window bands; a `Signal` vertical strip (a stair core) on one face. Smooth-shaded curves.

### Kit_Colony_Cabin: outlying cabins
- **Where and how many:** about 600, scattered on the colony's outskirts and round the outposts.
- **Size:** about 10 × 6 × 8, placed at their own size, scaled 0.8–1.3.
- **Variants:** A (a capsule pod on four stilts), B (a steep A-frame with a `Snow` roof), C (a box cabin with a vaulted roof).
- **Budget:** 120 each.

> Small cabins and pods: `Signal`, `Panel` or `SignalYellow` bodies, a `WindowLit` window or two and a lit door. Cheerful dots of colour in the snow.

### Kit_Colony_Depot: depots, garages and hangars
- **Where and how many:** about 150, in the colony's industrial edge.
- **Size:** fitted to 30–70 wide, 10–18 tall, 25–50 deep.
- **Variants:** A 50 × 14 × 36 (barrel-vaulted), B 40 × 12 × 30 (flat roof, a big door), C 60 × 16 × 40 (sawtooth roof).
- **Budget:** 250 each.

> Big practical sheds: `PanelGrey` or `Steel` walls, `DarkMetal` or snow-capped roofs, big painted doors on the −Y front with `SignalYellow` / `HazardBlack` frames.

### Kit_Colony_Tank: fuel and water tanks
- **Where and how many:** about 120, in tank farms.
- **Size:** fitted round, 14–26 across, 10–20 tall.
- **Variants:** A 20 × 16, B 16 × 12 (squat, a domed top).
- **Budget:** 150 each.

> Insulated tanks: `Steel` or `Panel` drums with a domed or shallow conical roof carrying a `Snow` cap, and one `Signal` band. 16 segments, smooth.

### Kit_Colony_Mast: comms masts
- **Where and how many:** about 40, on roofs' ground lots, at outposts and on peaks.
- **Size:** 6 × 50 × 6, scaled 0.6–1.4 in height.
- **Budget:** 150.

> A lattice-like mast (a tapering 3- or 4-sided tower of solid legs; no thin cross-bracing, which wouldn't read) in `Signal` and `Panel` bands, with a dish or antenna near the top and a `WarningLight` at the tip. Legs at least 0.8 m.

### Kit_Colony_Tube: enclosed walkways
- **Where and how many:** about 200, linking neighbouring buildings and domes, a few metres above the ground.
- **Size:** 4 × 4 × 20, stretched **0.5–4× along y** (its length) and placed so its ends sink into the buildings it joins.
- **Budget:** 60.

> An insulated tube: a rounded rectangle or octagon in `Panel`, with a `WindowLit` window band along each side. **Nothing may change along the length** (it is stretched): no ribs, no posts.

### Kit_Pipe / Kit_Pipe_Support: pipelines
- **Where and how many:** about 600 of each, along the roads between the colony, the spaceport and the outposts.
- **Size:** pipe 2 × 2 × 20, stretched **1–2× along y**; support 4 × 2 × 2, stretched 1–3× in height. Pipes lie on supports every 20–40 m; the pipe's bottom sits on the support's top.
- **Budget:** pipe 40, support 40.

> - **Pipe:** a `Steel` cylinder along y, 8 sides, smooth, with one `Signal` stripe along its length. Uniform along its length.
> - **Support:** a `DarkMetal` portal (two legs and a cross beam) under the pipe, chunky.

---

## Batch 2: domes, the power plant and the Climate Control Center (`kit_domes.py`, row 1)

### Kit_Colony_Dome: habitat domes
- **Where and how many:** about 60, in the colony's dome quarter. Placed at their own size, scaled 0.7–1.5 (uniformly).
- **Size:** 40 × 20 × 40.
- **Variants:** A (a white ribbed dome on a short drum wall, an entrance on −Y), B (a dome with a `WindowLit` band round its drum and an oculus cap), C (a flattened dome with three small entrance vestibules).
- **Budget:** 600 each.

> Big insulated domes: smooth-shaded `Panel` domes (16–24 segments), ribs or segment bands painted in `PanelGrey`, a `Snow` cap on the top, `Signal` entrance vestibules with lit doors.

### Kit_Colony_Greenhouse: greenhouses
- **Where and how many:** about 30, beside the domes. Placed at their own size, scaled 0.8–1.3.
- **Size:** A 36 × 18 × 36 (a glazed dome), B 60 × 14 × 24 (a glazed barrel vault).
- **Budget:** 600 each.

> Glazed greenhouses that glow at dusk: `Greenhouse` glass panels between `DarkMetal` or `Panel` ribs (painted, not modelled), on a `Concrete` base ring. At 1 km they should read as glowing green-gold shapes in the snow.

### Kit_Colony_Plant: the power plant
- **Where and how many:** 2, on the colony's industrial edge. Placed at its own size.
- **Size:** 80 × 40 × 60 (stacks may rise to 70).
- **Budget:** 2,000.

> A geothermal power plant: a big `DarkMetal` and `PanelGrey` hall, two or three tall stacks with `Signal` and `Panel` bands and `WarningLight` tops, cooling units on the roof, and glowing `CoreGlow` vents in rows along the hall.

### Kit_Colony_ClimateCenter: the Climate Control Center
- **Where and how many:** 1, the colony's icon in the middle of its plaza, seen from anywhere on the map. Placed at its own size, not stretched.
- **Size:** 240 m tall to the antenna tip; footprint **at most 120 × 120**.
- **Budget:** 8,000.

> Fichina's Climate Control Center (the weather-control station of *Star Fox 64*'s Fichina), more striking than anything else on the map:
> - **base:** a broad, low domed hall (about 120 across, 30 high) with a ring of `WindowLit` windows and four `Signal` entrance blocks;
> - **tower:** a white tapering core tower rising from the dome, with two or three ring decks (`LightStrip` edges);
> - **crown:** the climate machine: a ring of emitter fins or dishes round a glowing `CoreGlow` core near the top, then an antenna with a red `WarningLight` tip.
>
> Smooth-shaded curves; creases only at the deck breaks. It must read as one bold silhouette from 5 km.

---

## Batch 3: the spaceport and the outposts (`kit_outposts.py`, row 2)

Everything here is placed at its own size: **keep the footprints**. Practical forms in `Panel`, `PanelGrey`, `Concrete`, `DarkMetal`, with `Signal`, `SignalYellow` / `HazardBlack` stripes, `Lamp` floodlights and a few `LightStrip` details.

### Kit_Port_Pad: landing pads
- **Where and how many:** 8 at the spaceport.
- **Size:** 60 × 3 × 60 (a round or octagonal deck).
- **Budget:** 500.

> A raised landing pad: a `Concrete` deck on a low `DarkMetal` rim, a big painted landing mark (`Marking` circle and a letter or bars, `Signal` or `SignalYellow` chevrons) and `Lamp` edge lights painted round the rim.

### Kit_Port_Terminal
- **Where and how many:** 1.
- **Size:** 90 × 20 × 40.
- **Budget:** 1,500.

> The spaceport terminal: a long low building with a curved glass front (`WindowLit` and `GlassDark` bands) on −Y, a snow-capped roof with a control cab or mast, `Signal` end blocks.

### Kit_Port_Hangar
- **Where and how many:** 4.
- **Size:** 70 × 26 × 60, its doors on the −Y front.
- **Budget:** 1,000.

> A ship hangar: a barrel-vaulted (smooth) or angled roof with a `Snow` cap, huge painted doors (`DarkMetal`, a `SignalYellow` / `HazardBlack` frame), a big painted number panel (`Marking`), a lit window strip along the side.

### Kit_Port_Tower
- **Where and how many:** 1.
- **Size:** 16 × 45 × 16.
- **Budget:** 1,200.

> A control tower: a `Concrete` or `Panel` shaft with a `Signal` band, a wide canted glass cab (`WindowLit` / `GlassDark`), a `DarkMetal` roof, a mast and a `WarningLight`.

### Kit_Outpost_Radar
- **Where and how many:** about 6, at the spaceport and on peaks.
- **Size:** 18 × 22 × 18.
- **Budget:** 1,000.

> A radome (a smooth `Panel` sphere on a drum with a `Signal` band) or a dish on a lattice tower, on a `Concrete` base.

### Kit_Outpost_Module: outpost modules
- **Where and how many:** about 40, in small clusters at the research and mining outposts.
- **Size:** fitted to 16–30 long, 8–12 tall, 10–14 deep.
- **Variants:** A 24 × 10 × 12, B 18 × 9 × 12.
- **Budget:** 250 each.

> Research modules on stilts, like Halley VI: a capsule-shaped body (`Signal` or `Panel`), lit window strips, on `DarkMetal` legs about 2.5 m tall (chunky, at least 1 m).

### Kit_Outpost_Drill: mining rig
- **Where and how many:** 2–3, at the mining outpost.
- **Size:** 20 × 60 × 20.
- **Budget:** 1,000.

> A drilling rig: a tapering `SignalYellow` derrick (solid legs, no thin bracing), a `DarkMetal` machinery house at its foot with `HazardBlack` stripes, `Lamp` floodlights and a `WarningLight` on top.

### Kit_Outpost_Dish: dish antennas
- **Where and how many:** about 6, in an array on the ice shelf.
- **Size:** 40 × 40 × 40.
- **Budget:** 1,200.

> A large radio dish (`Panel`, smooth inside face) tilted up towards the sky on a `DarkMetal` yoke and a `Concrete` base, a feed horn on struts (chunky) at its focus.

---

## Batch 4: ice, rocks and pines (`kit_nature.py`, row 3)

### Kit_Tree_SnowPine: snow-laden pines
- **Where and how many:** about 40,000 (forests in the south-west, valley floors, round the colony).
- **Size:** scaled uniformly 1.0–2.3× (and height ±10 %) from their own size, about 7 × 16.
- **Variants:** A (a classic snow-laden cone), B (tall and narrow), C (lopsided, heavy with snow).
- **Budget:** **60 triangles each.** The hardest budget: a forest is thousands of them.

> Stylised pines: two or three stacked cones (or tiers) in `Pine` / `PineLight`, each tier's top faces in `PineSnow`, so each tree reads as dark green under white snow; a short `Trunk`, 4–5 sides. No ink lines are drawn on foliage, so the colour bands carry the shape.

### Kit_Rock_Boulder / Kit_Rock_Outcrop: rocks
- **Where and how many:** boulders about 4,000 on slopes and moraines; outcrops about 800 on steep high ground.
- **Size:** boulders fitted to 4–12 wide, 3–8 tall; outcrops to 20–45 wide, 11–29 tall; each sunk 30 % of its height into the ground.
- **Variants:** A–C each, with different proportions: flat, round, tall.
- **Budget:** boulder 50, outcrop 150.

> Faceted cold `Rock` with `RockLight` facets: a few big flat facets, flat-shaded, like cut stone in a cartoon; the up-facing facets are `Snow`. An outcrop can be a cluster of two or three slabs or a stepped crag.

### Kit_Ice_Serac: seracs
- **Where and how many:** about 1,500, on the glacier and the frozen lake's shores.
- **Size:** fitted to 6–30 wide, 5–25 tall; sunk 30 % of their height.
- **Variants:** A (a tilted block), B (a leaning shard), C (a cluster of two blocks).
- **Budget:** 60 each.

> Blocks of glacier ice: faceted, flat-shaded, `Ice` faces with `IceDeep` on the steep and underside faces, a `Snow` top.

### Kit_Ice_Spire: ice pinnacles
- **Where and how many:** about 80, in clusters out on the frozen lake and on the glacier.
- **Size:** fitted to 20–50 wide, 40–150 tall; standing on the ice (sunk 3 m).
- **Variants:** A (a tall single spike), B (a twin spike), C (a crooked spire, narrowing then overhanging a little).
- **Budget:** 200 each.

> Towering crystal-blue ice pinnacles: big faceted planes, flat-shaded, `Ice` with `IceDeep` on half the facets so they read as crystals, a `Snow` cap on any ledge. Bold and simple: they are seen from kilometres.

### Kit_Ice_Arch: ice arches
- **Where and how many:** 2: one over the frozen lake, one across the western canyon. The player flies through them.
- **Size:** 160 × 100 × 30, placed at its own size (scaled 0.9–1.1); feet sunk 3 m.
- **The opening is gameplay:** at least **0.70 × the width wide** (112 m) and **0.72 × the height high** (72 m).
- **Budget:** 2,000.

> A natural arch of glacier ice: faceted `Ice` / `IceDeep`, a thick irregular span with a `Snow` top, icicle teeth painted (not modelled) along the underside in `IceDeep`.

### Kit_Ice_Falls: the frozen waterfall
- **Where and how many:** 1, against the ice shelf's western cliff, where the plateau's high lake spills over. Placed at its own size.
- **Size:** 140 × 260 × 50: its back (+Y) against the cliff, its top at the cliff's lip (the piece's top edge sits at the lip, its foot on the ground 260 m below).
- **Budget:** 3,000.

> A waterfall frozen solid: a cascade of icicle curtains and bulging ice columns down the cliff, wider at the foot where the ice pooled and froze into a mound. Faceted `Ice` and `IceDeep` (deep blue in the folds), `Snow` on the ledges. Its back may be flat (it touches the cliff), but must be closed.
