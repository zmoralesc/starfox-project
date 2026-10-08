# Agent guide

Instructions for coding agents working in this repository. Humans: start with [docs/GUIDE.md](docs/GUIDE.md) instead.

**Star Fox: Ascent**, a Star Fox fangame: a Godot 4.7.2 (GDScript, Forward+, Jolt physics, D3D12 on Windows) third-person space shooter in the style of *Star Fox 64*, with *Rogue Squadron*-style squad orders. The player (call sign **Fox**) flies with three AI wingmen (Falco, Slippy, Krystal) against waves of enemy fighters and a destroyer, giving wingmen orders.

**Read before non-trivial work:**
- [docs/GUIDE.md](docs/GUIDE.md): how every system works, walkthroughs, recipes. Section 8 has one subsection per system.
- [ONBOARDING.md](ONBOARDING.md): quick reference (tables of values, groups, layers).
- [DESIGN_PRINCIPLES.md](DESIGN_PRINCIPLES.md): the user's design policies. Follow them for any gameplay or HUD decision, and point out when a request or an existing feature conflicts with one.

---

## Environment

- **OS / shell:** Windows 11. Both PowerShell and Git Bash are available; the commands below are Bash.
- **Godot executable** (this machine): `C:/Users/zemc7/OneDrive/Documentos/GodotEngine/Godot_v4.7.2-stable_win64.exe`. Referred to as `$GODOT` below.
- **Git repository** on branch `main`, remote `origin` = `git@github.com:zmoralesc/starfox-project.git` (private, SSH key auth). Commit and push only when the user asks. Uncommitted work has no history to fall back on, so still read a file before overwriting it and make targeted edits rather than rewrites. `.godot/` (the import cache) is ignored; `.gitattributes` stores text files with LF line endings.
- **The user often has the Godot editor open.** Scenes may be re-saved by the editor between your turns (it adds `uid=` and `unique_id=` attributes and may change values). Re-read a `.tscn` before editing it, keep values the user changed, and after editing scene files on disk tell the user to reload them in the editor rather than saving the open copies.
- **No Python.** Use Bash tools (`sed`, `awk`, `grep`) or the file-editing tools. Beware: `awk -v file="$TMP/..."` breaks on Windows backslash paths; prefer the Edit tool for multi-line changes.

## Commands

```sh
# Refresh the import cache and global class_name cache. Required after adding a
# script with a new class_name, or new assets, outside the editor; otherwise
# "Could not find type X" / "Identifier X not declared" errors.
timeout 200 "$GODOT" --headless --path . --import

# Run a headless scenario script (see Verification). Always wrap in timeout:
# a parse error in a -s script leaves Godot hanging forever.
timeout 300 "$GODOT" --headless --path . --fixed-fps 60 -s path/to/test.gd -- arg1 arg2

# Rendered screenshot run (no --headless); the script saves the viewport.
timeout 120 "$GODOT" --path . --resolution 1280x720 --fixed-fps 60 -s path/to/shot.gd -- out_dir
```

Exit-time noise like `ERROR: N resources still in use at exit` or `ObjectDB instances leaked` is normal for `-s` scripts; ignore it. Filter output with `grep -E "^(PASS|FAIL)|SCRIPT ERROR"`.

IDE diagnostics reported right after you create a `class_name` script or add a member are often stale (class cache not refreshed yet). Run `--import` and a headless script before trusting them.

---

## Verification

There is **no test suite in the repo**. Changes are verified with throwaway scenario scripts kept **outside the project** (use your scratch/temp directory, never commit them into the repo). Any behaviour change should be checked this way before reporting it done, and balancing changes should be measured before and after.

**Template:**

```gdscript
extends SceneTree

var frame := 0


func _initialize() -> void:
	var main: Node = load("res://levels/space_station.tscn").instantiate()
	root.add_child(main)
	current_scene = main


func _physics_process(_delta: float) -> bool:
	frame += 1
	if frame == 2:
		current_scene.get_node("IntroCutscene").skip()
		get_first_node_in_group("enemy_spawner").first_wave_delay = 99999.0  # hold waves back
		var ship: Ship = get_first_node_in_group("player")
		ship.global_position = Vector3(0, 1500, 0)  # clear of the asteroid field
		for w in get_nodes_in_group("wingmen"):
			w.global_position = ship.global_transform * w.slot_offset
	if frame == 600:
		print("PASS" if true else "FAIL", " description")
		return true  # quit
	return false
```

**Tips:**
- Do setup in the first physics frames (frame 2 is the established pattern), after the scene's `_ready()` has run.
- Autoloads can't be referenced by name in `-s` scripts: use `root.get_node("Settings")`.
- Simulate input with `Input.action_press(&"fire")` / `action_release`, or `Input.parse_input_event()` with a constructed event (joypad buttons for the D-pad).
- Force an enemy state: `enemy.quarry = ship; enemy._enter_state(EnemyFighter.State.CHASE)` (`quarry` may also be a wingman).
- Freeing `EnemySpawner` gives a clean scene, but `Level` then errors calling `start()` on it after the intro. Prefer `first_wave_delay = 99999.0`.
- **Orders with nobody selected skip wingmen on Cover Me** (`WingCommand.recipients()`). Select them first (`wing.toggle_select_all()`) when testing order changes on covering wingmen.
- **Wingmen can be shot.** In tests that need wingmen to keep doing their job (formation, orders), a long fight can make one evade (orders wait) or disengage (no orders, flies off for 25 s). Check `w.status == Wingman.Status.NORMAL`, or keep them topped up (`w.shields = w.max_shields` each frame).
- **AI and roaming are random** (not seeded). For balancing numbers, run each configuration several times (4–6) and compare averages; single runs swing a lot. Don't report a single-run number as an effect size.
- Headless uses a dummy audio driver: `AudioStreamPlayer.playing` never goes false and `finished` never fires. To test audio timing (e.g. music), run without `--headless` and turn Master down: `AudioServer.set_bus_volume_db(0, -80.0)`.
- Screenshots: run without `--headless`, then `root.get_texture().get_image().save_png(path)`. View them to check layout.
- Existing behaviour worth regression-checking after wingman, AI, weapon or HUD changes: formation holding in hard turns, wingmen firing with the leader only on Form Up, order routing and selection, Cover Me assignment, Weapons Free roaming and target choice, comms priorities, the intro, wingman evasion, disengaging and queued orders, the destroyer kill rule, laser hits at 15/40/150/400 m.

---

## Architecture in brief

```
Fighter (player/fighter.gd)         flight model, guns (twin lasers, muzzle flash), engine/shot sounds
├── Ship (player/ship.gd)           pilot = input; shields; crosshair raycast; death
└── AIPilot (ai/ai_pilot.gd)        pilot = AI: _decide() → avoid obstacles, ground → steer; attack runs; lead aim
    ├── Wingman (wing/wingman.gd)   orders, formation flight, Cover Me trail slot, Weapons Free; shields, evading, disengaging
    └── EnemyFighter                PATROL / CHASE / EVADE / SEEK
WingCommand (wing/wing_command.gd)  selection, order routing, target picking, Cover Me assignment, wingman comms lines
EnemySpawner                        waves, destroyer every 5th wave, fighter cap
Level (levels/level.gd)             shared mission logic on the root of levels/level_base.tscn; missions inherit that scene
Mission (missions/mission.gd)       mission selector entry: title, description, scene_path
Terrain (world/terrain.gd)          planet ground (noise, or a TerrainMap from Blender): mesh + collision + lakes; height_at() / surface_height() / clearance_height()
AsteroidField (world/asteroid_field.gd) the Space Station mission's seeded rocks, scattered in its _ready(): clear of the intro lane and the station
MapProps (world/map_props.gd)       on a map's imported props (Corneria's city, arches, base...): toon materials + trimesh collision
PlayBoundary (world/play_boundary.gd) edge of a mission area: HUD warning, then Ship turns itself back
GreatFox (world/great_fox.tscn)     scenery: the team mothership parked outside each mission's boundary; no collision
SpaceStation (world/space_station.gd) the Space Station mission's centrepiece: solid friendly scenery, AI avoidance spheres; asteroids, waves, destroyers kept out
Destroyer + DestroyerPart/Turret/Hangar   capital ship; arrives through a WarpPortal (effects/warp_portal.gd); kill rule = bridge + all thrusters. Two scenes on the same scripts: juggernaut.tscn (current, spawned by level_base) and destroyer.tscn (previous ship)
Laser (weapons/laser.gd)            raycast-per-step bolts, optional streak (trail_length)
Comms (comms/comms.gd)              dialogue box; say(speaker, text, priority, voice)
Pilot (comms/pilot.gd)              a character file (CommsSpeaker + accent colour + battle lines); a wingman's `speaker`
Advisor (comms/advisor.gd)          a character who doesn't fly (Peppy): CommsSpeaker + destroyer lines
MissionControl (comms/mission_control.gd)  in level_base.tscn: has the Advisor warn of destroyers, hint, call out progress
HUD (ui/hud.gd)                     everything drawn in _draw(), no Control per element
Settings (autoload)                 owns ALL gameplay InputMap actions + display settings
SceneFader (autoload)               fade-to-black scene changes and restarts (change_scene, reload_scene)
Music (autoload, audio/music.gd)    plays a LevelMusic (optional lead once, then loop) on the Music bus; set via Level.music
SoundFX (effects/sound_fx.gd)       one-shot positional sounds that outlive their source
ShipModel (player/ship_model.gd)    on the imported Arwing: toon materials + per-ship accent colour
```

**Invariants you must preserve:**
- **Pilot interface.** `Fighter._physics_process` calls `_think`, rotates from `_get_stick()`/`_get_roll()` (at `_get_pitch_rate()`), sets speed from `_get_target_speed()` (at `_get_acceleration()`, capped by `_get_top_speed()`), moves, then `_aim()` and fires if `_wants_fire()`. Change behaviour by overriding these in a subclass, not by special-casing in `Fighter`.
- **Physics priorities:** ships/enemies 0, wingmen 5 (follow the leader's *current* position), ChaseCamera 10, IntroCutscene 20.
- **Collision layers** (constants on `Fighter`): World 1, Friendly 2, Enemy 4, Enemy hurtbox 8. Player bolts mask 13, enemy/turret bolts mask 3, crosshair ray World+Enemy+Hurtbox; friendly raycasts set `collide_with_areas` and must pass colliders through `Hurtbox.resolve()`. Decide a new object's layer first.
- **Shootable = duck-typed.** Anything with `take_hit(damage: int, at: Vector3)` can be hit; `notify_shot(origin)` and `notify_attacker(shooter)` (destroyer hull and parts: retaliation) are optional. Wingmen have `take_hit` but are never destroyed: their shields soak hits, then they evade or disengage (`Wingman.status`; GUIDE §8.8). New shootables need a double-hit guard, a `radius`, `signal destroyed`, and usually the `targets` / `obstacles` groups. Optional `highlight_on_crosshair` and `attack_target` bools (read through `Fighter.highlights_crosshair()` / `Fighter.is_attack_target()`, on when absent) control the red crosshair and whether the Attack order can pick it; asteroids turn both off, and a shielded destroyer part (`armoured`, which also turns its hit burst into a surface spark) reports both off while shielded.
- **Systems find each other via groups** (`player`, `wingmen`, `enemies`, `targets`, `obstacles`, `destroyer`, `terrain`, `boundary`, `station`, `great_fox`, `hud`, `wing_command`, `enemy_spawner`, `comms`, `mission_control`) and exported node references, never hard-coded paths across scenes. `Comms.find(get_tree())` may return null; check it.
- **Input actions live in `Settings.ACTIONS` and `_default_bindings()`**, applied to the InputMap at startup (overwriting anything defined in Project Settings). Never add gameplay actions in the Input Map.
- **Wingman order vs state.** `order`/`standing_order` are player-facing (FORM_UP, ATTACK, COVER_ME, WEAPONS_FREE); `state` is FOLLOW/ATTACK. `assign_*()` change the order; `command_attack()`/`command_follow()` change only the state. Use `Wingman.target_gone()` (also true for destroyed-but-present destroyer parts), not just `is_instance_valid()`.
- **Formation slot** must be read through `Wingman.slot_position()` (world position: `current_slot_offset()`, which includes the Cover Me trail, raised above any terrain and, gradually, any buildings: `_structure_lift`; or, tucked in among tall buildings, blended onto the leader's recorded path: `_tuck_amount`, `_trail_point()`), not `slot_offset` directly, except for initial placement.
- **AI obstacle avoidance knows spheres and boxes.** Large shapes are covered with `ObstacleProxy` spheres or `ObstacleBox` boxes (the Juggernaut: 22 boxes instead of ~650 spheres). Every AI ship checks every obstacle every frame, so keep counts low. Code that walks the `obstacles` group must handle `ObstacleBox` (`entry_distance()`, `contains()`, `way_out()`) rather than treat its `radius` (half its diagonal) as a sphere. The player and wingmen are not in `obstacles`.
- **Ground is not an obstacle.** Terrain is handled separately by `AIPilot._avoid_ground()` through `Terrain.clearance_height()` (no raycasts), and only when a `terrain` group node exists, so the asteroid field is unaffected. On a map with structures (Corneria) that includes the buildings, arches and bridge, as per-cell heights exported with the map: they are not `obstacles` spheres, so the AI flies over the city rather than through it. Anything new that picks AI waypoints should pass them through `_clear_of_obstacles()` or `_above_ground()`.

---

## Conventions

- **Static typing everywhere** (`:=`, typed params and returns, `Array[T]`). Tabs for indentation.
- **`##` doc comments** on classes, exports and non-trivial functions; `#` comments explain *why*, not what. Match the surrounding comment density; the codebase is well commented and new code should be too.
- **Fonts:** all UI text uses the project font (`gui/theme/custom_font`, Share Tech Mono in `ui/fonts/`). Code that draws text gets it with `get_theme_default_font()`, never `ThemeDB.fallback_font` (the engine default, which ignores that setting).
- **Every tuning value is an `@export`**, grouped with `@export_group`, with a `##` comment. No magic numbers in logic. Per-type values are overridden in the `.tscn`, not by changing script defaults.
- **`_private` names** with a leading underscore; public API without.
- **Frame-rate-independent smoothing:** `lerp(a, b, 1.0 - exp(-k * delta))`; constant-rate change: `move_toward(x, target, rate * delta)`.
- **Freed nodes:** check `is_instance_valid()` before using any stored node reference; don't `as`-cast possibly-freed references. Untyped parameters where a freed object may be passed (see `target_gone`).
- **Shared resources:** `duplicate()` a material before changing it per instance.
- **Coroutines:** after any `await`, check `is_inside_tree()`. Timers that should pause with the game: `create_timer(t, false)`.
- **Don't jump positions that other code differentiates.** Formation flight derives slot velocity from frame-to-frame slot movement; blend slot changes over time (see `_cover_amount`).
- **Hand-editing `.tscn`:** add `[ext_resource ...]` lines with a unique `id`, reference them with `ExtResource("id")`, append nodes at the end with `parent="."` or a path. `uid=` / `unique_id=` attributes are optional. Inherited scenes (`wingman.tscn` ← `ship.tscn`, `light_fighter.tscn` ← `enemy_fighter.tscn`) pick up base-scene nodes and values automatically.
- **Import options** (e.g. looping audio) live in the asset's `.import` file; edit it, then run `--import`.

---

## Documentation duty

When you change behaviour, values or structure, update **both** [docs/GUIDE.md](docs/GUIDE.md) (explanations; the relevant section 8 subsection, walkthroughs, recipes) and [ONBOARDING.md](ONBOARDING.md) (reference values and tables) in the same task. Keep this file current if you change commands, invariants or conventions. Check relative links still resolve after moving or adding files.

---

## Gotchas

- Laser bolt speed is `laser_speed + speed` (shooter's speed added); `_lead_point()` assumes the same. Player/wingman `laser_speed` is set on `ship.tscn`, enemies on `enemy_fighter.tscn`.
- Twin lasers (`parallel_fire`) assume exactly two muzzles (`Model/MuzzleL`, `Model/MuzzleR`) and aim from the point between them. On the Arwing they sit at the forward roots of the blue fins.
- **The enemy fighter model is generated too** (`models/enemy_fighter/source/build_enemy_fighter.py`, same workflow and colour rule as the destroyer below). One `.glb` serves every fighter type: `FighterModel` (`enemies/fighter_model.gd`) recolours the materials named `Fighter_Accent` and `Fighter_Lights` per type (keep those names), and the light fighter overrides its colours on `Model/Mantis`.
- **The Juggernaut (the current destroyer, `enemies/juggernaut.tscn`)** is built by `models/destroyer/source/juggernaut_c2.py` in Blender (true metres, ship at `SCALE` 1.5, detail in real metres; designed with Gemini from `models/SPACE_ASSETS.md`), exported as `models/destroyer/juggernaut_*.glb`. Scene positions come from `juggernaut_markers.glb`; hull collision is built from the model at load (`hull_collision_from_model`), so it needs no pasting; but `hull_outline` was generated from the exported model with a throwaway script and must be regenerated after a shape change. The AI avoidance boxes are `ObstacleBox` nodes under `AvoidanceBoxes` (editable in the editor, where a `@tool` preview draws them; the user may adjust them by hand, so keep their values); after a shape change, check every part of the hull is still inside one (GUIDE §8.10). The thrusters keep spheres. Turret positions come from `MOUNT_PADS` in the script: after moving a pad, copy the new `TurretMount` marker positions into the scene. Keep the model's geometry rules (GUIDE §8.10): no piece may hover off the body, and no two visible faces of different pieces may share a plane (they flicker); check a rebuilt model for both, building the check's pieces from Blender's `loop_triangles` (some hull quads are bent by up to 3 m, so another triangulation fakes floating pieces). Surface detail (panels, windows, lights, markings) is painted flush into the hull mesh by `paint_juggernaut_hull()`: rectangles cut into the hull's faces and given another material, so nothing stands off the surface (the user wants detail to be part of the model, not stuck on). It adds ~16,500 triangles to the hull, and so to its collision. The hull greys also carry a tiling plating texture made by the script (`build_plating_pixels()`, UVs from `add_plating_uvs()`), packed into each `.glb`; the `juggernaut_*_Juggernaut_Plating.png` files beside them are the importer's extracted copies, so change the script, not them. Its turret meshes are saved out of `juggernaut_turret.glb` by `_subresources` in its `.import` file (keys are the importer's mesh names, `juggernaut_turret_Turret_Base` etc.), so `juggernaut_turret.tscn` can arrange them as `Yaw`/`Yaw/Pitch`.
- **The previous destroyer model (`destroyer.tscn`) is generated, not hand-made.** `models/destroyer/source/build_destroyer.py` builds it in Blender (MCP, or `"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --python build_destroyer.py -- --export`) in game coordinates times `SCALE` (2.0) and exports one `.glb` per part type plus `collision.txt` and `proxies.txt` (the `extra_proxies` line). Change the script, not the `.glb` files; after re-exporting, run `--import`, paste changed collision pieces and the proxies line into `enemies/destroyer.tscn`, and keep `hull_outline`, part positions, radii and shape sizes in step (scene values are script values × `SCALE`). The script's colours are the sRGB values Godot shows (it converts to linear for glTF); the toon light is bright, so keep hull colours dark. Export with `use_active_scene` (the exporter otherwise picks up selected objects from every Blender scene). Surface detail (`add_detail()`: plates, windows, lights, greebles) is decoration with no collision; it keeps clear of the turret mounts listed in `TURRETS`, so moving a turret in `destroyer.tscn` means updating that list and re-exporting.
- **The space station model is generated too** (`models/space_station/source/build_space_station.py`, same workflow and colour rule as the destroyer below). One `.glb`, one node per component, each modelled round its own pivot (`PIVOTS` in the script) so components can become destructible parts later; keep the node names and pivots if you change it. Its export also writes `proxies.txt`: after a layout change, paste that line into `world/space_station.tscn`. The station sits at the Space Station mission's origin (up to ~430 m from it): test scripts that need a clear area should still move the ship to (0, 1500, 0), and anything that targets the field's centre (as the destroyer used to) must go through the `station` group (`overlaps()`, `push_clear()`, `bounding_radius()`).
- **The Corneria map is generated too** (`models/corneria/source/build_corneria.py`, same workflow and colour rule). Its export writes `corneria_map.tres` (a `TerrainMap`: heights, per-cell paint, per-cell structure heights for the AI) and `corneria_props.glb`; never edit those by hand. Moving or adding a building changes the structure heights only when re-exported. The game draws only the front of a face, so open surfaces (sheets, domes, open cylinders) need `away_from` in the script (Blender's preview shows both sides and hides the mistake). `MapProps` makes props solid by node name (`solid_nodes`), so keep the object names (`City`, `Town`, `Base`, `Arches`, `RiverBridge`, `SeaStacks`, `Water`). Its buildings, bridges, arches, stacks and trees are hand-made pieces from `source/corneria_kit.blend` (spec: `models/corneria/ASSETS.md`), which the script places (`Batch.kit()`); edit a piece there and re-run the script, not the preview `.glb` files in `models/corneria/kit/`. Kit faces keep their modelled facing, so a piece modelled inside out shows only its inside in the game: check new pieces with the backface culling view, or the signed volume of each closed part. The waterfall is not a prop but a `Waterfall` node (`world/waterfall.gd`) in `levels/corneria.tscn`, placed from the `waterfall.txt` the export writes: paste it over the node's transform after moving the river or cliff. `source/` has a `.gdignore` (Godot would otherwise import the `.blend` files, which needs Blender).
- **The Great Fox is scenery with no collision** (`world/great_fox.tscn`, model in `models/great_fox/`, which came without a licence: see its README.txt). Keep it out of the player's reach (past the boundary plus turn-back margin). Disengaged wingmen fly towards it (group `great_fox`). Its `Model` transform undoes a tilt baked into the export; keep it if you swap or reimport the model. Its materials are cel-shaded at runtime by `ToonMaterial` (effects/toon_material.gd).
- The player/wingman art is an imported glTF (`models/arwing_assault/`, CC-BY 4.0: keep `license.txt` and credit the author). `ShipModel` replaces its materials with toon ones at runtime (the editor shows the originals) and paints the pilot band (`player/arwing_band.gdshader`) on materials matched **by name** (`band_materials`: `Material.002` fins, `Material.004` fin panels); reimport settings that rename materials break it. The band is placed in the ship's Model space (`band_hub`, `band_radius`), so a model swap needs new values. The wingman colour goes through `ShipModel.set_accent()`, not stripe meshes.
- **Scene inheritance leaks changes.** `wingman.tscn` ← `ship.tscn` and `light_fighter.tscn` ← `enemy_fighter.tscn`. Anything set on the base scene applies to the child unless overridden there. `enemy_fighter.tscn` is the "elite", but `light_fighter.tscn` (every level 1 enemy) inherits it; the player's `collision_mask` 5 would reach wingmen if `wingman.tscn` didn't override it to 1. After editing a base scene, check its children.
- `Laser.launch()` takes the shooter **node** (not its RID) and calls `notify_kill(victim)` on it when a shot destroys something; the shooter may be freed by then, so it's checked with `is_instance_valid`.
- `queue_free()` takes effect at the end of the frame; `is_queued_for_deletion()` within it.
- The player's ship is not freed on death: its `Model` goes to a `Wreck` (`Ship.wreck`, followed by the ChaseCamera through its unrolled `flight_basis`) and the `Ship` node stays where it died, physics off; anything it owns (e.g. `EngineSound`) keeps running unless stopped in `Ship._die()`. The restart happens on `Ship.wreck_destroyed`, in `Level._restart()` (the place for lives / game over later).
- Enemy fighters have a `Hurtbox` (`enemies/hurtbox.gd`, Area3D on layer 8, 6.6 × 3.8 × 5.2 m) taller than their 6.2 × 2 × 5.6 collision box: bolts and the crosshair hit it, crashes don't. Friendly raycasts must query areas and resolve the collider with `Hurtbox.resolve()`.
- **Hit feedback** (`effects/hit_reaction.gd`, `HitReaction`): enemies and destroyer parts call `hit(at, health_left)` from `take_hit()` (red flash, fighters' model flinch, smoke then fire as health drops). The flash is the `hit_flash` instance uniform in `toon_surface.gdshaderinc`, so it only shows on toon-shaded meshes; it's on every toon material, so keep it defaulting to zero. A new shootable that should react needs `HitReaction.attach()` and that call; pass it a smoke point (a marker, like the fighters' `Model/SmokePoint`) to fix where its smoke comes out, or the smoke starts where it was first hit. The flinch moves the fighter's `Model` (muzzles included) for a quarter second; anything reading `Model` transforms should expect it, and code handing `Model` elsewhere must call `release()` first (as `EnemyFighter` does for the wreck). Bolts hitting anything with `take_hit` spawn `Laser.hit_burst`; anything else (not water) `Laser.surface_hit`, a smaller `HitBurst` in the bolt's colour, so a hit and a miss never look alike.
- Enemies free themselves the instant they die: sounds or effects that should outlive them must be spawned separately (`SoundFX.play_at`, `Explosion.spawn`). Explosions are styled by `ExplosionStyle` presets in `effects/explosions/`; a new style should also go in `Level.prewarm_explosions`, or its first use stutters (~20 ms) while its shaders compile. The smoking wreck you see afterwards is a separate `Wreck` node (effects/wreck.gd) that takes over the fighter's `Model` and `Hurtbox`; it isn't in any group and has no collision body, so nothing that tracks enemies sees it, but friendly bolts and the crosshair do (it has `take_hit`; `attack_target` false keeps orders off it).
- Transparent materials (including `GeometryInstance3D.transparency` fades) get no ink outlines, and opaque ones always do: glowing effects (bolts, flashes) should be transparent or additive, or they read as solid outlined objects once bloom no longer covers the line (see `weapons/laser_bolt.gdshader`). To keep a lit, solid-looking surface but drop its outlines, write `ALPHA *= 1.0` (not `= 1.0`: ALPHA starts at 1 minus the node's `transparency`, and assigning it breaks that fade) and add `depth_draw_always` (see `effects/cloud.gdshader`; the explosion puffs do the same, and `effects/toon_unlined.gdshader` is the toon shader done that way, used for Corneria's foliage). The transparent pass casts no shadows: a surface drawn that way that should cast one needs a shadow-only stand-in (`MapProps._add_shadow_casters()`). The toon shader's shadow floor applies to directional light only.
- The asteroid field is seeded (`AsteroidField.field_seed`); everything else random is not.
- **Wingman characters live in `comms/speakers/*.tres` (`Pilot`)**, not on the wingman nodes: `Wingman.call_sign`, `accent_color` and `pilot` are read-only properties derived from the `speaker` export. Edit lines and colours in the pilot file.
- **Music outlives scenes.** The `Music` autoload keeps the current track across scene changes and restarts; a scene that should be silent must call `Music.play(null)` (the title does, through its empty `music` export).
- **Missions inherit `levels/level_base.tscn`** (ship, wingmen, spawner, HUD, comms, intro...). Edits to the base reach every mission unless a mission overrides them; per-mission changes go in the mission's scene. `levels/space_station.tscn` is the Space Station mission (it was `main.tscn` until the asteroid scattering moved into `AsteroidField`; test scripts must load the new path). Test the planet with `res://levels/corneria.tscn` (the Corneria mission; it replaced the old `corneria_test.tscn`).
- `Terrain` builds itself in `_ready()`, so `height_at()` returns `-INF` until then; it joins the `terrain` group in `_enter_tree()`. `PlayBoundary` (group `boundary`) also joins in `_enter_tree()`. Spawners and patrols must keep things above `clearance_height()` and inside the boundary; see `EnemySpawner` (`spawn_altitude`, `spawn_boundary_margin`). Vertex colours from `SurfaceTool` aren't sRGB-converted: convert with `srgb_to_linear()`. The water has no body of its own: the sea is a slab on Terrain's World-layer body and raised lakes are props, so a ray or bolt can't tell water from ground by collider; use `Terrain.is_water_surface(point)` / `water_level_at()` (as `Laser` does for its splash).
- **Two traps in `vertex()` of spatial shaders** (found on the laser glow, `weapons/laser_glow.gdshader`): `VIEWPORT_SIZE` reads as 0 there (dividing by it made the geometry vanish without an error), and `PROJECTION_MATRIX[1][1]` is negative (Vulkan flips y), so take `abs()` before using it as a size scale. Debug a vanishing or misshapen custom-`POSITION` mesh by painting `ALBEDO` a flat colour.
- **Meshes a vertex shader reshapes** (the water splash, the wake's spray: a unit cylinder or plane bent metres out of its own bounds) need a `custom_aabb` on their MeshInstance3D, or they're culled as soon as the small original box leaves the screen. Per-object values there are `instance uniform`s (`set_instance_shader_parameter`), so all instances share one material. In a loop whose iterations differ per pixel (`continue`), `fwidth()`/`dFdx()` are undefined: compute the pixel size before the loop and pass it in (`px_step()` in `water.gdshader`). Foam drawn on the water by gameplay (splash rings, wakes) goes through `WaterMarks` (`world/water_marks.gd`), which feeds the water shader's fixed-size arrays.
- The toon light model lives in `effects/toon_light.gdshaderinc`, included by `toon_surface.gdshaderinc` (all the `toon*` shaders), `terrain.gdshader`, the explosion puffs and the splash and spray: a change there changes every lit surface (`water.gdshader` has its own `light()`, with the same banding idea). Water depth comes from a heights texture Terrain sets on the water material; the water, splash and spray draw in the transparent pass (no ink outlines; the water at render priority -50, before other see-through things, so it can't cover bolts). Procedural noise in shaders must hash grid corners with an integer hash (use `effects/noise.gdshaderinc`, shared by the water and the terrain): float hashes like `fract(p * 123.34)` break into straight seams at world-scale coordinates. `toon.gdshader` is likewise on every flat-coloured surface: keep its texture and glow uniforms defaulting to no effect (white albedo texture, black `emission`); `emission_texture` must default to white, since it multiplies `emission` (black there zeroes every glow that has no texture). Its body is `toon_surface.gdshaderinc`, shared with `toon_clip.gdshader` (the same plus a clip plane, used by the destroyer while it warps in) and `toon_worn.gdshader` (clip plane plus noise-worn paint, `TOON_WEAR`: the Juggernaut's crimson, given by `Destroyer.worn_paint_materials`, which skips `_use_clip_shader()` because it clips itself); edit the include, not a copy. Destroyer test scripts that reposition it before calling `arrive()` should set `warp_in = false`, or it moves back out to its portal.
- The HUD lays out in a 1152×648 base viewport stretched with `canvas_items`/`expand`. Occupied corners: radar top left, shield and heat bars top right, comms bottom left (its own CanvasLayer, layer 5), wing panel bottom right.
- `user://settings.cfg` holds the player's bindings and display settings. Never delete files under `%APPDATA%/Godot/app_userdata/` with wildcards: other projects' data lives beside this one. The project name sets the folder: `config/name` "Star Fox: Ascent" maps to `app_userdata/Star Fox- Ascent/` (renaming the project moves `user://`, so copy `settings.cfg` across rather than lose the bindings).

---

## Working with this user

- **Some requests ask for instructions, not changes** ("tell me what has to be done", "describe the steps"). Then explain with file and line references and **don't edit files**. The user is learning the codebase and contributes code themselves.
- **For balancing or AI changes, measure.** Write a scenario that quantifies the effect, run old vs new (several runs each), and report the numbers with their spread. If the measurement shows the change doesn't do what was intended, say so and investigate why before reporting success (e.g. Cover Me's trailing slot only helped once the engagement manoeuvre was also fixed).
- **Report honestly.** Separate what was verified (headless tests, screenshots) from what wasn't (audio by ear, real-time feel on a physical gamepad). Correct earlier claims if new data contradicts them.
- **Respect the user's own edits.** If a file has changed since you last read it, treat the new content as intended, and keep their values unless asked to change them.
- **Plan before large features.** For multi-part features, propose a plan with recommended defaults and wait for approval before implementing.
