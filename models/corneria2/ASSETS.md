# New Corneria: kit brief

This file specifies the 3D models ("kit pieces") of the new Corneria map in **Star Fox: Ascent**, a Godot 4 fangame. The map is a Blender file, [source/corneria.blend](source/corneria.blend). Generator scripts lay it out from these pieces: the city, the harbour town and villages, the military base, the bay's arches and the forests. Today every piece is a grey placeholder box ("greybox"). Each entry below replaces one with a real model.

Read the **global brief** first; every piece depends on it. Each piece's entry then gives:
- what the piece is, where it stands and how many copies there are;
- its sizes, and how the generators stretch it;
- its triangle budget;
- what it should look like.

---

## Global brief

### How the models are seen
- **The player's view.** The player flies a small fighter at 60–130 m/s, usually 30–400 m above the ground, over a 16 × 16 km map. Most pieces pass by at 80–1,000 m, and the city skyline is seen from 5 km away. Silhouettes, big colour shapes and bold stripes read; detail under about 1.5 m doesn't.
- **Flying among them.** The player weaves between downtown towers, through the bay's arches and under bridges. Openings meant to be flown through must keep the sizes given.
- **The map.** The open sea and the approach lie to the south. A bay lined with stone arches leads north to **Corneria City**, which has:
  - three downtown clusters of towers, with the central **spire** in the middle one;
  - mid-rise districts round them;
  - an old town;
  - suburbs;
  - an industrial port.

  A harbour **town** with a lighthouse sits on the east coast, among farmland and villages. The **military base** is to the west: two runways, hangars, a control tower. Forests and rocky hills fill the rest.

### Art style: *Star Fox Assault*'s Corneria
The target is Corneria as *Star Fox Assault* showed it: a confident, optimistic sci-fi capital. It's richer than *Star Fox 64*'s blocks, but still bold and readable, with nothing gritty or realistic.
- **Architecture.** Futuristic civic architecture:
  - layered masses: podiums, setbacks, cantilevered decks and ring balconies;
  - rounded corners, curved glass fronts, domes and drum towers;
  - rooftop crowns: landing pads, antenna masts, sensor rings.
- **Colour.** Pale warm stone and white walls (`Cream`, `Tower`, `Wall`), with deep blue glass (`Glass`, `GlassDark`) in strong horizontal bands or vertical strips.
  - Accents in teal (`Teal`) and orange (`Orange`), used sparingly: a roof, a fin, a stripe, a canopy.
  - Pale cyan light strips (`LightStrip`, glowing) on the crowns and edges of the tall buildings.
- **Districts.** Each district needs its own character, and the variants within a piece should differ clearly in silhouette, not only in colour:
  - **downtown:** glass and white towers;
  - **mid-rise:** stone-and-glass offices and apartment blocks;
  - **old town:** Mediterranean-futurist: cream walls, terracotta roofs (`Roof`), arcades painted on;
  - **suburbs and villages:** whitewashed houses with terracotta or teal roofs;
  - **port and base:** practical industrial and military forms in steel, olive and grey, with yellow-and-black hazard paint (`TaxiYellow`, `HazardBlack`).

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
Use only palette materials: `corneria_common.PALETTE`, named `Corneria_<name>`. kit_tools' `Builder` takes the name without the prefix. The values are sRGB, as seen in the game. The light is bright, so avoid pure white on big surfaces.

| Name | sRGB | Use |
|---|---|---|
| `Tower` | 0.84, 0.86, 0.90 | white of tall buildings |
| `Cream` | 0.90, 0.85, 0.74 | warm stone walls, old town |
| `Wall` | 0.93, 0.91, 0.86 | whitewashed houses |
| `Concrete` | 0.72, 0.68, 0.60 | plinths, podiums, piers |
| `Stone` | 0.76, 0.68, 0.53 | arches, old-town trims |
| `Glass` | 0.30, 0.55, 0.80 | windows, glass fronts |
| `GlassDark` | 0.16, 0.30, 0.50 | dark glass bands, contrast |
| `Teal` | 0.16, 0.58, 0.62 | accent: roofs, fins, canopies |
| `Orange` | 0.95, 0.55, 0.16 | accent: stripes, markers |
| `LightStrip` | 0.55, 0.85, 1.00, glows | light strips on crowns and edges |
| `WarningLight` | 1.00, 0.20, 0.15, glows | aircraft warning lights |
| `Lamp` | 1.00, 0.90, 0.50, glows | lighthouse lamp |
| `RoofDark` | 0.36, 0.37, 0.42 | flat roofs, caps, machinery |
| `Roof` | 0.75, 0.38, 0.28 | terracotta roof tiles |
| `AwningBlue` | 0.20, 0.50, 0.85 | awnings, boat hulls |
| `Steel` | 0.60, 0.62, 0.66 | masts, tanks, cranes, decks |
| `Military` / `MilitaryDark` | 0.45, 0.50, 0.42 / 0.30, 0.34, 0.28 | base buildings |
| `TaxiYellow` / `HazardBlack` | 0.95, 0.80, 0.20 / 0.12, 0.12, 0.14 | hazard stripes, cranes |
| `BridgeRed` / `Lighthouse` | 0.75, 0.25, 0.18 / 0.82, 0.18, 0.14 | bridge steel, lighthouse bands |
| `Marking` | 0.95, 0.95, 0.90 | painted lines, helipad marks |
| `Rock` | 0.55, 0.50, 0.46 | rocks, stacks, cliffs |
| `Tree` / `TreeLight` | 0.18, 0.40, 0.20 / 0.27, 0.50, 0.22 | foliage, dark / light |
| `Trunk` | 0.40, 0.28, 0.18 | trunks, timber, jetties |

**Foliage** (`Tree`, `TreeLight`, `Trunk`) is drawn **without ink lines** and casts shadows through stand-ins: use those three for foliage only. A needed colour that isn't listed is added to the palette (in `corneria_common.py`, with a comment). Report it; don't invent materials in the model.

### Technical rules
- **Units and axes:** metres; Blender Z up.
- **Front:** a piece's front (main entrance, its street side) faces **Blender −Y**.
- **Origin:** at the centre of the footprint, on the ground (Z = 0). Parts that go below ground (feet sunk into a slope, a pier's foot) are given in the entry.
- **Normals point out.** The game draws only the front of a face, so a face pointing in is a hole. Pieces are **closed meshes**: the game builds collision from them, and the checks below find open edges and parts built inside out.
- **Separate shells are fine** (a roof box on a wall box), but they must overlap or touch cleanly; see "no coplanar overlaps".
- **Triangle budgets** are per piece (per part for stacks). Repetition sets them: there are 80,000 trees, 7,000 houses and 3,000 shops.

### Variants, stacks and stretching
The generators **fit each piece to its lot**: they scale it on each axis to the width, height and depth the lot asks for. To keep that stretching small, a piece can come as a **family of variants**:
- **Naming.** `Kit_City_Office_A`, `_B`, `_C`... each is its own collection. The generator picks the variant whose own proportions need the least stretching, choosing at random among near-ties, then fits it.
- **Placeholders.** The placeholder (`Kit_City_Office`, marked `greybox`) drops out by itself once one real variant exists. Pieces without variants keep the plain name (`Kit_City_Spire`).
- **Designing variants.** Give variants **different proportions**, spanning the size range in the entry, and different silhouettes.

A tall piece can be a **stack**: three collections, `<variant>_Base`, `<variant>_Shaft` and `<variant>_Crown` (for example `Kit_City_Tower_A_Base`).
- **How it's placed.** The base stands on the ground, as many shafts as fit stand on it, then the crown on top. So a tower grows by whole storeys, and the base and crown are never stretched in height. The shafts take up any remainder by stretching: by up to half a shaft's height, shared among them (±50 % with one shaft, ±17 % with three).
- **Each part's origin** is at the centre of its own bottom face (Z = 0 at its bottom). All three parts are stretched by the same width and depth.
- **The shaft must repeat seamlessly:**
  - its top outline equals its bottom outline;
  - its painted bands line up across the joint;
  - its bottom matches the base's top outline, and its top matches the crown's bottom outline;
  - keep it 1–4 storeys high (4 m a storey).
- **Joints.** Each part stands exactly on the measured top of the one below, so joints rely on matching outlines. A crown may reach below its own origin into the shaft (negative Z), but only with a part set back from the shaft's outline: a crown side in the plane of a shaft side flickers. Nothing overlaps shaft to shaft.
- **Joint plugs.** Stacked parts are separate instances in the game, and float rounding leaves hairline cracks at their joints. Through those the ink pass sees the hidden caps and draws black dots along the joint. So each `_Shaft` and `_Crown` has a second object, `<part>_Plug`:
  - a closed sleeve, its outline the part's bottom outline inset 0.05 m;
  - from 0.4 m below its origin to 0.1 m above;
  - in the joint wall's main colour.

  Through a crack it reads as wall. Plugs don't count in the part's measured size.
- **Open joints.** Where parts join flush, they have **no cap** in the joint:
  - shafts have no top or bottom cap;
  - crowns have no bottom cap;
  - bases have no top cap under a flush shaft (a wider podium keeps a ring-shaped roof).

  A cap there ends exactly on the continuing wall, so along the joint some pixels show the hidden cap instead of the wall, and the ink pass dots them. `kit_tools.check()` accepts open edges at those ends.
- **Footprint.** A variant's size is the widest of its parts, and the generator fits that to the lot. A podium, ring deck or saucer wider than the shaft is fine (the shaft just comes out narrower than the lot), but anything cantilevered far past the base shrinks the whole tower.
- **Cap cost.** `prism()` caps take every cut on their edges, so each column cut round a shaft costs two cap triangles at the top and two at the bottom. Fin-striped shafts get expensive: keep fins sparse.

Stretching still happens: each entry gives the range a piece is fitted to. Keep details that would look wrong when stretched (round windows, domes, discs) to pieces that are not stretched, or to stack crowns.

### Building pieces: scripts with kit_tools
Each batch of pieces is a Blender Python script, `source/kit/kit_<batch>.py`, built on [source/kit/kit_tools.py](source/kit/kit_tools.py). Read its docstring.
- `begin(script, row)`, then `piece(name, [(suffix, Builder)])` for each piece, then `finish()`.
- `Builder` provides:
  - `prism()`: upright extrusions with sides split into painted cells: windows, bands, doors;
  - `box()`;
  - `lathe()`: round shapes, cells too;
  - `extrude()`: side profiles pushed back, such as gables, vaults and arches;
  - `grid()`: painted panels;
  - `face()`;
  - `at(matrix)`, to build a part about its own origin and move, turn or mirror it.
- Vertices at the same spot merge, and normals are made outward per closed shell.
- A script may add its own helpers. Don't change `kit_tools.py`'s existing behaviour, which other batches rely on. Add to it only if needed, and report the change.

Running a script:
```sh
cd models/corneria2/source/kit
KIT_OUT=<scratch>/kit_test.blend KIT_PREVIEW=<scratch>/previews \
  "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --python kit_<batch>.py
```
- **Where it builds.** `KIT_OUT` builds into a scratch copy, which is always safe. Without it, the script writes `source/kit.blend`, the real kit; only do that when asked.
- **Checks.** `finish()` prints each piece's triangles, size (game width × height × depth), base height and centre, plus problems: open edges, parts facing in, zero-area faces, materials outside the palette. **Fix every problem.**
- **Previews.** `KIT_PREVIEW` renders each piece front three-quarter and back three-quarter, with backface culling on, so a face pointing in shows as a hole. **Look at every preview.**

---

## City (gen_city.py)

Sizes are **width (x) × height (z) × depth (y)** in metres. "Fitted to" gives the 5th–95th percentile of what the generator asks for.

### Kit_City_House: suburban houses
- **Where and how many:** 5,500, in the suburbs' grid of small lots.
- **Size:** fitted to 13–14 wide, 6–9 tall, 10–12 deep.
- **Variants:** A–D, all about 14 × 7.5 × 12.
- **Budget:** 150 triangles each.

> A modern Cornerian family house:
> - **form:** one or two storeys in white `Wall`, under a low terracotta (`Roof`) or teal (`Teal`) roof: hipped, gabled, a single curved shell, or flat with a deck;
> - **windows:** painted `Glass` bands;
> - **front:** a painted door on the −Y front.
>
> Vary the silhouette between variants: an L-shape, a gable, a curved roof, a split-level. At 300 m a street of them should read as varied little white houses with coloured roofs.

### Kit_City_Shop: old-town buildings
- **Where and how many:** 2,950, packed tight in the old town's irregular lots.
- **Size:** fitted to 7–18 wide, 9–21 tall, 6–14 deep.
- **Variants:** A 12 × 11 × 8, B 9 × 17 × 8 (narrow, tall), C 17 × 12 × 10, D 16 × 19 × 11.
- **Budget:** 250 each.

> Mediterranean-futurist townhouses and shops. The old town should feel warmer and older than the glass city round it.
> - **walls and roofs:** cream (`Cream`) walls with `Stone` trims, terracotta (`Roof`) or teal roofs; one variant may have a small dome or a rounded corner turret;
> - **ground floor:** a painted arcade or a shopfront in `Glass`, with a `AwningBlue` or `Orange` awning band;
> - **upper floors:** tall windows painted on.

### Kit_City_Apartment: mid-rise housing
- **Where and how many:** 655, in the mid-rise districts.
- **Size:** fitted to 13–36 wide, 15–29 tall, 7–28 deep.
- **Variants:** A 32 × 22 × 12 (slab), B 22 × 26 × 20 (block), C 16 × 18 × 10 (small).
- **Budget:** 400 each.

> Cornerian apartment blocks: stone and white bodies, with balcony bands painted as long horizontal `Glass` / `GlassDark` strips.
> - **form:** a set-back top storey, or a rounded end;
> - **colour:** an accent (`Teal` or `Orange`) on a stair tower or a roof edge.

### Kit_City_Office: mid-rise and downtown offices (stacks)
- **Where and how many:** 1,050, the bulk of the city's skyline.
- **Size:** fitted to 12–42 wide, 31–85 tall, 8–29 deep.
- **Variants:** stacks A–D:
  - A 36 × 16 footprint (slab);
  - B 24 × 22;
  - C 16 × 12 (thin);
  - D 30 × 28 (deep).
- **Parts:** base about 8 m (a lobby storey: a glass ground floor, a podium edge or canopy), shaft 3 storeys (12 m), crown 4–8 m (roof plant, a parapet, a small pad or fins).
- **Budget:** base 250, shaft 150, crown 300.

> Stone-and-glass offices: alternating horizontal bands of `Cream` or `Tower` and `Glass`, or vertical white fins between glass strips.
> - **Corners:** a curved glass corner on at least one variant.
> - **Colour:** teal or orange accents on the crowns.

### Kit_City_Tower: downtown skyscrapers (stacks)
- **Where and how many:** 102, in the three downtown clusters, between 87 and 205 m tall.
- **Size:** fitted square, 25–45 per side.
- **Variants:** stacks A (28 × 28), B (36 × 36), C (44 × 44).
- **Parts:** base 16–24 m (a podium, wider or set back, with a glass lobby); shaft 4 storeys (16 m); crown 20–40 m. Make the crown distinctive:
  - a stepped spire;
  - a ring and antenna;
  - a landing pad on a cantilever;
  - a canted glass top.
- **Budget:** base 500, shaft 250, crown 1,000.

> The *Assault* skyline: tall white-and-glass towers with strong vertical lines: white mullion fins over blue glass, or glass with white corner piers.
> - **Light:** `LightStrip` lines up the crown's edges.
> - **Safety:** a red `WarningLight` at the top of each antenna.

### Kit_City_RoundTower: drum towers (stacks)
- **Where and how many:** 48, downtown, between 90 and 190 m.
- **Size:** fitted round, 25–46 across.
- **Variants:** stacks A (30 across), B (42 across).
- **Parts:** as the towers.
- **Budget:** base 500, shaft 300, crown 1,000.

> Cylindrical glass towers:
> - **shaft:** banded white and glass, 16–20 segments, smooth-shaded;
> - **base:** a ring podium;
> - **crown:** a domed or saucer top with a ring deck and a mast.

### Kit_City_Spire: the central spire
- **Where and how many:** 1, the city's icon, seen from anywhere on the map. Placed at its own size, not stretched.
- **Size:** 340 m tall to the antenna tip; footprint **at most 60 × 60**, since the lot it stands on is no larger.
- **Budget:** 6,000.

> The capital's spire, more striking than any other tower:
> - **plinth:** a stepped plinth with a glass lobby ring;
> - **shaft:** three or four tapering glass tiers in white collars, with two or three white ribs running up the tiers;
> - **top:** an observation ring near the top, then an antenna with `LightStrip` bands and a red `WarningLight` tip.
>
> Smooth-shaded curves; creases only at the tier breaks.

### Kit_City_Warehouse: port warehouses
- **Where and how many:** 390, in the industrial port.
- **Size:** fitted to 35–78 wide, 10–18 tall, 25–57 deep.
- **Variants:** A 50 × 14 × 36, B 72 × 16 × 50, C 40 × 12 × 50.
- **Budget:** 200 each.

> Big port sheds:
> - **roofs:** sawtooth, barrel-vaulted (smooth) or flat with roof vents;
> - **walls:** `Steel` / `Concrete`, with `RoofDark` roofs;
> - **front:** big painted loading doors on the −Y front and `TaxiYellow` / `HazardBlack` stripes on door frames.

### Kit_City_Tank: storage tanks
- **Where and how many:** 160, in the port's tank farms and the base's fuel depot.
- **Size:** fitted round, 18–26 across, 12–18 tall.
- **Variants:** A 24 × 16, B 20 × 12 (squat, a domed top).
- **Budget:** 120 each.

> Cylindrical `Steel` or `Wall` tanks with a shallow conical or domed roof and one painted `Orange` or `Teal` band. 16 segments, smooth.

### Kit_City_Crane: harbour gantry cranes
- **Where and how many:** 8, in rows along the port's quays. Not stretched.
- **Size:** 10 × 50 × 30: the legs straddle 10 m along x, and the boom reaches 15 m each way along y.
- **Budget:** 600.

> A container gantry crane: a `TaxiYellow` portal frame on four legs, with a boom along y and a machinery house on top. Keep the legs and beams chunky: at least 1.2 m.

### Kit_City_Bridge: road bridge deck
- **Where and how many:** 4, carrying the arterial roads over the river and inlets.
- **Size:** 24 × 4 × 100, fitted to 28 wide and stretched **1.5–3× along y** (its length).
- **Budget:** 200.

> A road deck: a `Concrete` slab with `Steel` side railings as solid low parapets, and an `Orange` stripe along each side face. Nothing may change along the length (it is stretched): no lamp posts, no cross details. Its top is flush with the road, so it has no road paint of its own.

### Kit_City_Pier: bridge piers
- **Where and how many:** 11, under the bridge decks, from the bed up to the deck.
- **Size:** 17 × 20 × 8 (17 across the road), fitted to 16–20 tall.
- **Budget:** 100.

> A `Concrete` pier: a wall with rounded ends, or two columns with a cap beam. Plain; it stands in water.

---

## Trees and rocks (gen_wilds.py, and the city's and villages' trees)

### Kit_Tree_Broadleaf / Kit_Tree_Pine: trees
- **Where and how many:** broadleaves about 53,000 (forests, parks, gardens); pines about 28,000 (hills and highlands).
- **Size:** scaled uniformly 1.0–2.3× (and height ±10 %) from their own size: broadleaf about 10 × 14, pine about 7 × 16.
- **Variants:** broadleaf A–C, pine A–C.
- **Budget:** **60 triangles each.** This is the hardest budget in the kit; a forest is thousands of them.

> Stylised trees in the *Assault* look:
> - **broadleaf crown:** two or three lumpy low-poly blobs or a faceted rounded crown, in `TreeLight` with a `Tree` underside or second blob;
> - **pine crown:** two or three stacked cones in `Tree`;
> - **trunk:** a short `Trunk` trunk, 4–5 sides.
>
> No ink lines are drawn on foliage, so the colour bands carry the shape. Vary the silhouette between variants: round, tall, lopsided.

### Kit_Rock_Boulder / Kit_Rock_Outcrop: rocks
- **Where and how many:** boulders 4,500 on slopes and hilltops; outcrops 660 on steep high ground.
- **Size:**
  - boulders fitted to 4–12 wide, 3–8 tall;
  - outcrops to 20–45 wide, 11–29 tall;
  - each sunk 30 % of its height into the ground.
- **Variants:** A–C each, with different proportions: flat, round, tall.
- **Budget:** boulder 40, outcrop 120.

> Faceted `Rock`: a few big flat facets, flat-shaded, like cut stone in a cartoon. An outcrop can be a cluster of two or three slabs, or a stepped crag with a `TreeLight` grassy top face.

### Kit_Rock_Stack: sea stacks
- **Where and how many:** 35, in clusters in shallow water.
- **Size:** fitted to 22–35 wide, 50–105 tall, standing on the sea bed (up to 30 m deep).
- **Variants:** A 24 × 60, B 30 × 50, C 20 × 80.
- **Budget:** 300.

> Tall faceted rock pillars in `Rock`:
> - **form:** narrowing or overhanging a little near the top, and a grassy `TreeLight` cap;
> - **strata:** a band or two of `Stone`.

---

## The harbour town, villages and farms (gen_town.py)

### Kit_Town_House: coastal houses
- **Where and how many:** 1,650 in the harbour town and villages.
- **Size:** fitted to 8–22 wide, 7–14 tall, 6–16 deep.
- **Variants:** A 10 × 9 × 10 (cottage), B 14 × 10 × 10, C 20 × 12 × 10 (a terrace row), D 14 × 13 × 14 (two storeys).
- **Budget:** 200 each.

> A seaside town:
> - **walls and roofs:** whitewashed `Wall` with terracotta `Roof`, some with `Teal` or `AwningBlue` roofs or shutters painted on;
> - **front:** painted doors on the −Y front;
> - **details:** a chimney or a little balcony.
>
> Cheerful, simple, Mediterranean.

### Kit_Town_Hall: town and village halls
- **Where and how many:** 5. Placed at its own size: keep the footprint 18 × 26.
- **Size:** 18 × 16 × 26.
- **Budget:** 800.

> A civic hall: `Cream` walls, a terracotta roof and a small clock tower or teal dome rising above it, with an arcaded front painted on −Y.

### Kit_Town_Shed: harbour sheds
- **Where and how many:** 7.
- **Size:** fitted to 7–23 wide, 8–11 tall, 6–18 deep.
- **Variants:** A 12 × 9 × 10, B 22 × 10 × 16.
- **Budget:** 150.

> Fishing sheds and boathouses: `Steel` or timber (`Trunk`) walls, `RoofDark` or `Teal` pitched roofs, big painted doors.

### Kit_Town_Lighthouse: the lighthouse
- **Where and how many:** 1, on a headland east of the town. Not stretched.
- **Size:** 10 × 36 × 10 (the lantern may go above 36 m, up to 40).
- **Budget:** 1,500.

> A tapering round tower in `Wall` with `Lighthouse` red bands, a gallery deck with a railing (a solid low wall), and a glass lantern with a glowing `Lamp` inside and a `RoofDark` cap. Smooth-shaded.

### Kit_Town_Jetty: jetty decks
- **Where and how many:** 5. Stretched **3.3–4.1× along y**.
- **Size:** 6 × 2 × 60.
- **Budget:** 60.

> A timber (`Trunk`) deck slab, uniform along its length (it is stretched): plank lines may run along y only.

### Kit_Town_Post: jetty legs
- **Where and how many:** 120. Stretched 0.3–2× in height.
- **Size:** 0.8 × 4 × 0.8.
- **Budget:** 12.

> A plain 4- to 6-sided `Trunk` post.

### Kit_Town_Boat: moored boats
- **Where and how many:** 9, floating, sunk a little.
- **Size:** 5 × 3 × 14, not stretched; the waterline is at about 1 m.
- **Variants:** A (fishing boat: a wheelhouse aft), B (motor yacht).
- **Budget:** 400.

> Hulls in `AwningBlue`, `Wall` or `Teal`, with a cabin; bow towards −Y.

### Kit_Farm_Barn / Kit_Farm_Silo: farmsteads
- **Where and how many:** 15 each. Not stretched.
- **Size:** barn 16 × 10 × 26; silo 7 × 18 × 7.
- **Budget:** barn 400, silo 200.

> - **Barn:** a big pitched or gambrel `Roof`-red barn with `Wall` trims and a painted cross-braced door.
> - **Silo:** a `Steel` drum with a domed `Teal` cap.

---

## The military base (gen_base.py)

The Cornerian Army airfield. Everything is placed at its own size: **keep the footprints**. Practical forms in `Military`, `MilitaryDark`, `Concrete` and `Steel`, with `TaxiYellow` / `HazardBlack` stripes, `Orange` markers and a few `LightStrip` details for the sci-fi look.

### Kit_Base_Hangar
- **Where and how many:** 10, in a row facing the apron.
- **Size:** 60 × 22 × 50, its doors on the −Y front.
- **Budget:** 1,200.

> A fighter hangar with a barrel-vaulted (smooth) or angled roof. Its front is huge painted doors (`MilitaryDark`, a `TaxiYellow` / `HazardBlack` frame) with a large painted hangar number panel (`Marking`).

### Kit_Base_ControlTower
- **Where and how many:** 1.
- **Size:** 14 × 40 × 14.
- **Budget:** 1,500.

> A `Concrete` shaft with a wide glass cab (`GlassDark`), canted outward, with a `RoofDark` roof, a mast and a `WarningLight`.

### Kit_Base_HQ
- **Where and how many:** 1.
- **Size:** 70 × 24 × 40.
- **Budget:** 1,500.

> Command headquarters: a long `Concrete` block with a glass band, an entrance canopy on −Y, a rooftop helipad (`Marking` H on `RoofDark`) and a comms mast.

### Kit_Base_Barracks / Kit_Base_Shed
- **Where and how many:** 72 barracks, 54 sheds.
- **Size:** barracks 40 × 10 × 14; shed 30 × 8 × 20.
- **Budget:** 300 / 200.

> Long low `Military` buildings: painted windows, a `MilitaryDark` low-pitched roof; the shed with a big door.

### Kit_Base_Radar
- **Where and how many:** 3.
- **Size:** 18 × 22 × 18.
- **Budget:** 1,000.

> A radar dome (`Wall`, a smooth sphere on a drum) or a dish on a tower, on a concrete base.

### Kit_Base_Bunker
- **Where and how many:** 6.
- **Size:** 10 × 4 × 10.
- **Budget:** 150.

> A low armoured bunker: a sloped `Concrete` block with a dark slit (`HazardBlack`).

---

## Landmarks (gen_landmarks.py)

### Kit_Landmark_Arch: the bay's arches
- **Where and how many:** 5, standing in the sea in a row along the approach to the city. The player flies through them heading north, along y.
- **Size:** 170 × 120 × 26, scaled 0.93–1.09 and stretched up to 1.25× in height in deep water. It stands on the sea bed; its feet are sunk 2 m.
- **The opening is gameplay:** at least **0.70 × the width wide** (119 m) and **0.72 × the height high** (86 m), with a round top.
- **Budget:** 3,000.

> Monumental Cornerian stone gateways:
> - **stone:** `Stone` with `Cream` dressings; a keystone and impost bands painted on;
> - **top:** a beacon or a pair of `LightStrip` bands along the top;
> - **piers:** a stepped plinth at each pier.
>
> Grand and simple, readable from 3 km.

### Kit_Rock_Arch: the natural arch
- **Where and how many:** 1, on the big island's south shore.
- **Size:** 110 × 70 × 22, not stretched; opening at least 75 wide and 50 high.
- **Budget:** 1,500.

> A natural sea arch in faceted `Rock` with strata bands of `Stone` and a grassy `TreeLight` top.
