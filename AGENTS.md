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
	var main: Node = load("res://main.tscn").instantiate()
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
- Force an enemy state: `enemy._player = ship; enemy._enter_state(EnemyFighter.State.CHASE)`.
- Freeing `EnemySpawner` gives a clean scene, but `Level` then errors calling `start()` on it after the intro. Prefer `first_wave_delay = 99999.0`.
- **Orders with nobody selected skip wingmen on Cover Me** (`WingCommand.recipients()`). Select them first (`wing.toggle_select_all()`) when testing order changes on covering wingmen.
- **AI and roaming are random** (not seeded). For balancing numbers, run each configuration several times (4–6) and compare averages; single runs swing a lot. Don't report a single-run number as an effect size.
- Headless uses a dummy audio driver: `AudioStreamPlayer.playing` never goes false and `finished` never fires. To test audio timing (e.g. music), run without `--headless` and turn Master down: `AudioServer.set_bus_volume_db(0, -80.0)`.
- Screenshots: run without `--headless`, then `root.get_texture().get_image().save_png(path)`. View them to check layout.
- Existing behaviour worth regression-checking after wingman, AI, weapon or HUD changes: formation holding in hard turns, wingmen firing with the leader only on Form Up, order routing and selection, Cover Me assignment, Weapons Free roaming and target choice, comms priorities, the intro, the destroyer kill rule, laser hits at 15/40/150/400 m.

---

## Architecture in brief

```
Fighter (player/fighter.gd)         flight model, guns (twin lasers, muzzle flash), engine/shot sounds
├── Ship (player/ship.gd)           pilot = input; shields; crosshair raycast; death
└── AIPilot (ai/ai_pilot.gd)        pilot = AI: _decide() → avoid obstacles, ground → steer; attack runs; lead aim
    ├── Wingman (wing/wingman.gd)   orders, formation flight, Cover Me trail slot, Weapons Free
    └── EnemyFighter                PATROL / CHASE / EVADE / SEEK
WingCommand (wing/wing_command.gd)  selection, order routing, target picking, Cover Me assignment, wingman comms lines
EnemySpawner                        waves, destroyer every 5th wave, fighter cap
Level (levels/level.gd)             shared mission logic on the root of levels/level_base.tscn; missions inherit that scene
Mission (missions/mission.gd)       mission selector entry: title, description, scene_path
Terrain (world/terrain.gd)          planet ground: mesh + collision + lakes; height_at() / surface_height()
PlayBoundary (world/play_boundary.gd) edge of a mission area: HUD warning, then Ship turns itself back
GreatFox (world/great_fox.tscn)     scenery: the team mothership parked outside each mission's boundary; no collision
Destroyer + DestroyerPart/Turret/Hangar   capital ship; kill rule = bridge + all thrusters; model built by models/destroyer/source/build_destroyer.py
Laser (weapons/laser.gd)            raycast-per-step bolts, optional streak (trail_length)
Comms (comms/comms.gd)              dialogue box; say(speaker, text, priority, voice)
Pilot (comms/pilot.gd)              a character file (CommsSpeaker + accent colour + battle lines); a wingman's `speaker`
HUD (ui/hud.gd)                     everything drawn in _draw(), no Control per element
Settings (autoload)                 owns ALL gameplay InputMap actions + display settings
SceneFader (autoload)               fade-to-black scene changes
Music (autoload, audio/music.gd)    plays a LevelMusic (optional lead once, then loop) on the Music bus; set via Level.music
SoundFX (effects/sound_fx.gd)       one-shot positional sounds that outlive their source
ShipModel (player/ship_model.gd)    on the imported Arwing: toon materials + per-ship accent colour
```

**Invariants you must preserve:**
- **Pilot interface.** `Fighter._physics_process` calls `_think`, rotates from `_get_stick()`/`_get_roll()` (at `_get_pitch_rate()`), sets speed from `_get_target_speed()`/`_wants_boost()` (at `_get_acceleration()`), moves, then `_aim()` and fires if `_wants_fire()`. Change behaviour by overriding these in a subclass, not by special-casing in `Fighter`.
- **Physics priorities:** ships/enemies 0, wingmen 5 (follow the leader's *current* position), ChaseCamera 10, IntroCutscene 20.
- **Collision layers** (constants on `Fighter`): World 1, Friendly 2, Enemy 4, Enemy hurtbox 8. Player bolts mask 13, enemy/turret bolts mask 3, crosshair ray World+Enemy+Hurtbox; friendly raycasts set `collide_with_areas` and must pass colliders through `Hurtbox.resolve()`. Decide a new object's layer first.
- **Shootable = duck-typed.** Anything with `take_hit(damage: int, at: Vector3)` can be hit; `notify_shot(origin)` is optional. Wingmen deliberately have no `take_hit` (invulnerable). New shootables need a double-hit guard, a `radius`, `signal destroyed`, and usually the `targets` / `obstacles` groups. Optional `highlight_on_crosshair` and `attack_target` bools (read through `Fighter.highlights_crosshair()` / `Fighter.is_attack_target()`, on when absent) control the red crosshair and whether the Attack order can pick it; asteroids turn both off.
- **Systems find each other via groups** (`player`, `wingmen`, `enemies`, `targets`, `obstacles`, `destroyer`, `terrain`, `boundary`, `hud`, `wing_command`, `enemy_spawner`, `comms`) and exported node references, never hard-coded paths across scenes. `Comms.find(get_tree())` may return null; check it.
- **Input actions live in `Settings.ACTIONS` and `_default_bindings()`**, applied to the InputMap at startup (overwriting anything defined in Project Settings). Never add gameplay actions in the Input Map.
- **Wingman order vs state.** `order`/`standing_order` are player-facing (FORM_UP, ATTACK, COVER_ME, WEAPONS_FREE); `state` is FOLLOW/ATTACK. `assign_*()` change the order; `command_attack()`/`command_follow()` change only the state. Use `Wingman.target_gone()` (also true for destroyed-but-present destroyer parts), not just `is_instance_valid()`.
- **Formation slot** must be read through `Wingman.slot_position()` (world position: `current_slot_offset()`, which includes the Cover Me trail, raised above any terrain), not `slot_offset` directly, except for initial placement.
- **AI obstacle avoidance only knows spheres.** Large shapes are covered with `ObstacleProxy` children. The player and wingmen are not in `obstacles`.
- **Ground is not an obstacle.** Terrain is handled separately by `AIPilot._avoid_ground()` through `Terrain.surface_height()` (no raycasts), and only when a `terrain` group node exists, so the asteroid field is unaffected. Anything new that picks AI waypoints should pass them through `_clear_of_obstacles()` or `_above_ground()`.

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
- **The destroyer model is generated, not hand-made.** `models/destroyer/source/build_destroyer.py` builds it in Blender (MCP, or `"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --python build_destroyer.py -- --export`) in game coordinates and exports one `.glb` per part type plus `collision.txt`. Change the script, not the `.glb` files; after re-exporting, run `--import`, paste changed collision pieces into `enemies/destroyer.tscn`, and keep `hull_outline`, `extra_proxies` and part positions in step. The script's colours are the sRGB values Godot shows (it converts to linear for glTF); the toon light is bright, so keep hull colours dark. Export with `use_active_scene` (the exporter otherwise picks up selected objects from every Blender scene).
- **The Great Fox is scenery with no collision** (`world/great_fox.tscn`, model in `models/great_fox/`, which came without a licence: see its README.txt). Keep it out of the player's reach (past the boundary plus turn-back margin). Its `Model` transform undoes a tilt baked into the export; keep it if you swap or reimport the model. Its materials are cel-shaded at runtime by `ToonMaterial` (effects/toon_material.gd).
- The player/wingman art is an imported glTF (`models/arwing_assault/`, CC-BY 4.0: keep `license.txt` and credit the author). `ShipModel` replaces its materials with toon ones at runtime (the editor shows the originals) and matches the accent material **by name** (`Material.004`); reimport settings that rename materials break it. The wingman accent colour goes through `ShipModel.set_accent()`, not stripe meshes.
- **Scene inheritance leaks changes.** `wingman.tscn` ← `ship.tscn` and `light_fighter.tscn` ← `enemy_fighter.tscn`. Anything set on the base scene applies to the child unless overridden there. `enemy_fighter.tscn` is the "elite", but `light_fighter.tscn` (every level 1 enemy) inherits it; the player's `collision_mask` 5 would reach wingmen if `wingman.tscn` didn't override it to 1. After editing a base scene, check its children.
- `Laser.launch()` takes the shooter **node** (not its RID) and calls `notify_kill(victim)` on it when a shot destroys something; the shooter may be freed by then, so it's checked with `is_instance_valid`.
- `queue_free()` takes effect at the end of the frame; `is_queued_for_deletion()` within it.
- The player's ship is hidden, not freed, on death; anything it owns (e.g. `EngineSound`) keeps running unless stopped in `Ship._die()`.
- Enemy fighters have a `Hurtbox` (`enemies/hurtbox.gd`, Area3D on layer 8, 5.5 m cube) larger than their 4.4 × 4.4 × 2.4 collision box: bolts and the crosshair hit it, crashes don't. Friendly raycasts must query areas and resolve the collider with `Hurtbox.resolve()`.
- Enemies free themselves the instant they die: sounds or effects that should outlive them must be spawned separately (`SoundFX.play_at`, `Impact.spawn`).
- Transparent materials (including `GeometryInstance3D.transparency` fades) get no ink outlines. The toon shader's shadow floor applies to directional light only.
- The asteroid field is seeded (`main.gd → field_seed`); everything else random is not.
- **Wingman characters live in `comms/speakers/*.tres` (`Pilot`)**, not on the wingman nodes: `Wingman.call_sign`, `accent_color` and `pilot` are read-only properties derived from the `speaker` export. Edit lines and colours in the pilot file.
- **Music outlives scenes.** The `Music` autoload keeps the current track across scene changes and restarts; a scene that should be silent must call `Music.play(null)` (the title does, through its empty `music` export).
- **Missions inherit `levels/level_base.tscn`** (ship, wingmen, spawner, HUD, comms, intro...). Edits to the base reach every mission unless a mission overrides them; per-mission changes go in the mission's scene. `main.tscn` is the Asteroid Field mission (it keeps its path and flat node names, so test scripts loading `res://main.tscn` still work). Test the planet with `res://levels/corneria_test.tscn`.
- `Terrain` builds itself in `_ready()`, so `height_at()` returns `-INF` until then; it joins the `terrain` group in `_enter_tree()`. `PlayBoundary` (group `boundary`) also joins in `_enter_tree()`. Spawners and patrols must keep things above `surface_height()` and inside the boundary; see `EnemySpawner` (`spawn_altitude`, `spawn_boundary_margin`). Vertex colours from `SurfaceTool` aren't sRGB-converted: convert with `srgb_to_linear()`.
- The toon light model lives in `effects/toon_light.gdshaderinc`, included by `toon.gdshader`, `toon_vertex.gdshader` and `water.gdshader`: a change there changes every lit surface. `toon.gdshader` is likewise on every flat-coloured surface: keep its texture and glow uniforms defaulting to no effect (white albedo texture, black emission).
- The HUD lays out in a 1152×648 base viewport stretched with `canvas_items`/`expand`. Occupied corners: radar top left, shield/boost bars top right, comms bottom left (its own CanvasLayer, layer 5), wing panel bottom right.
- `user://settings.cfg` holds the player's bindings and display settings. Never delete files under `%APPDATA%/Godot/app_userdata/` with wildcards: other projects' data lives beside this one. The project name sets the folder: `config/name` "Star Fox: Ascent" maps to `app_userdata/Star Fox- Ascent/` (renaming the project moves `user://`, so copy `settings.cfg` across rather than lose the bindings).

---

## Working with this user

- **Some requests ask for instructions, not changes** ("tell me what has to be done", "describe the steps"). Then explain with file and line references and **don't edit files**. The user is learning the codebase and contributes code themselves.
- **For balancing or AI changes, measure.** Write a scenario that quantifies the effect, run old vs new (several runs each), and report the numbers with their spread. If the measurement shows the change doesn't do what was intended, say so and investigate why before reporting success (e.g. Cover Me's trailing slot only helped once the engagement manoeuvre was also fixed).
- **Report honestly.** Separate what was verified (headless tests, screenshots) from what wasn't (audio by ear, real-time feel on a physical gamepad). Correct earlier claims if new data contradicts them.
- **Respect the user's own edits.** If a file has changed since you last read it, treat the new content as intended, and keep their values unless asked to change them.
- **Plan before large features.** For multi-part features, propose a plan with recommended defaults and wait for approval before implementing.
