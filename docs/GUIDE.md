# Project guide

A guide to how this game works, written so you can read the code with confidence and start changing it yourself.

[ONBOARDING.md](../ONBOARDING.md) is the short reference card: tables of numbers, groups and layers. This guide explains the *why* and the *how*: how a frame runs, how each system thinks, what the odd-looking bits of code are for, and how to make common changes safely.

**Contents**

1. [How to read this guide](#1-how-to-read-this-guide)
2. [The game in one page](#2-the-game-in-one-page)
3. [Godot concepts this project uses](#3-godot-concepts-this-project-uses)
4. [Working on the project](#4-working-on-the-project)
5. [Architecture: the big picture](#5-architecture-the-big-picture)
6. [Walkthrough: one shot, from button to explosion](#6-walkthrough-one-shot-from-button-to-explosion)
7. [Walkthrough: one order, from D-pad to "You got it!"](#7-walkthrough-one-order-from-d-pad-to-you-got-it)
8. [Systems in depth](#8-systems-in-depth)
9. [Code conventions and recurring idioms](#9-code-conventions-and-recurring-idioms)
10. [Recipes: common changes step by step](#10-recipes-common-changes-step-by-step)
11. [Testing and debugging](#11-testing-and-debugging)
12. [Gotchas](#12-gotchas)
13. [Where to start contributing](#13-where-to-start-contributing)
14. [Glossary](#14-glossary)

---

## 1. How to read this guide

- **First pass (about an hour):** sections 2, 5, 6 and 7. That's enough to follow how the pieces fit and to trace any behaviour back to its code.
- **New to Godot?** Read section 3 before section 5. It covers only the Godot features this project actually uses, and points to where each one appears.
- **Before changing a system:** read its part of section 8, then the relevant recipe in section 10.
- **Keep the code open alongside.** Every system section names its files; links open them in VS Code. The scripts are well commented, and a `##` comment above a function or export is its documentation (Godot shows these in the editor's tooltips and help).

---

## 2. The game in one page

***Star Fox: Ascent*** is a Star Fox fangame. You fly an Arwing, call sign **Fox**, in third person through an asteroid field, in the style of *Star Fox 64* with *Star Wars: Rogue Squadron*'s squad orders. Three AI wingmen fly with you:

| Wingman | Colour | Formation slot | Breaks off attacks |
|---|---|---|---|
| **Falco** | Blue | Left, slightly low | To the left |
| **Slippy** | Green | Top cover: 10 m above, 10 m ahead | Straight up |
| **Krystal** | Pink | Right, slightly low | To the right |

**The loop:**

1. **Title screen** → Start opens the **mission selector** → picking a mission fades into its level (Space Station mission or Corneria).
2. **Intro cutscene:** the formation flies past a fixed camera, Fox says *"We're approaching the combat zone."* on the comms, and the camera swoops in behind you.
3. **Waves:** enemy fighters arrive in waves that grow from 3 to 8 fighters. Every 5th wave a **destroyer** (capital ship) also arrives, launches more fighters and shoots with hull turrets. Peppy, aboard the Great Fox, warns you over the comms, says how to sink it and calls out your progress.
4. **Orders:** you select wingmen with the D-pad (or 1–4) and give orders: **Attack** your target, **Cover Me**, **Form Up**, or **Weapons Free**. A wingman acknowledges on the comms.
5. **Death:** your shields absorb every hit until they're knocked out; the next hit destroys you. After 3 s the level restarts, skipping the intro.

There's no win condition yet: the waves are endless.

**What's on screen:** the radar (top left), shield and thruster heat bars (top right), the comms box (bottom left), the wing panel (bottom right), and markers over enemies, wingmen and their targets.

---

## 3. Godot concepts this project uses

This is a Godot **4.7** project written in **GDScript**. If you know another engine or language, most of this will feel familiar; this section is about the parts that are specific to Godot and how this project uses them. The official docs are excellent and searchable: <https://docs.godotengine.org/en/stable/>.

### Nodes, scenes and instancing
Everything in a running game is a **node** in a single tree. A node has a type (`Node3D`, `CharacterBody3D`, `Camera3D`, `Label`...) and can have children. A **scene** (`.tscn` file) is a saved branch of nodes. Scenes can contain other scenes: that's **instancing**.

- `player/ship.tscn` is the player's ship: a body, a collision shape, a model (an instance of the imported Arwing scene, `models/arwing_assault/scene.gltf`), two muzzle markers, an engine glow and light, and a shield bubble.
- `wing/wingman.tscn` **inherits** `ship.tscn` (it's an instance of it with a different script and a few overrides), so wingmen use exactly the same model.
- `levels/level_base.tscn` holds everything every mission shares: the ship, the three wingmen, the HUD, the comms, the pause menu, the intro and so on. Each mission's scene **inherits** it and adds its own world: `main.tscn` (Space Station mission) adds the asteroids and space dust, `levels/corneria.tscn` adds the Corneria map (terrain and props) and clouds. See [8.18](#818-missions-and-levels).

In code, `preload("res://...tscn")` loads a scene as a `PackedScene`, and `scene.instantiate()` makes a new copy of its nodes, which you then `add_child()` into the tree. Lasers, enemies and the destroyer are all created this way at runtime.

`res://` is the project folder. `user://` is a per-user data folder (on Windows, `%APPDATA%\Godot\app_userdata\Star Fox- Ascent\`), where settings are saved.

### Scripts, `class_name` and `extends`
A script attaches behaviour to a node. `extends Fighter` makes the script a subclass of `Fighter`; `class_name Ship` registers it as a global type, so any other script can write `var ship: Ship` or `node is Ship`. Inheritance is used heavily here (see section 5).

`super()` calls the parent class's version of the current function. `_ready()` overrides almost always start with `super()` so the parent sets itself up too.

### Static typing
The code uses GDScript's optional static types everywhere: `var speed := 0.0` (type inferred), `func radius_of(node: Node) -> float`, `Array[Wingman]`. Types catch mistakes in the editor before you run the game. `as` casts (`node as Ship`) return `null` if the node isn't that type, which the code uses as a cheap type check.

### Exports and the Inspector
`@export var cruise_speed := 45.0` makes a variable editable in the editor's **Inspector** when the node is selected. Every tuning value in this project is an export, grouped with `@export_group("...")`. The value in the script is the default; a scene can override it (you'll see lines like `cruise_speed = 50.0` in `enemy_fighter.tscn`). **To tune the game, you rarely need to touch code**: select the node, change the value in the Inspector.

### The node lifecycle
Godot calls these functions on your script if you define them:

| Function | When | Used for |
|---|---|---|
| `_ready()` | Once, after the node and its children enter the tree | Setup: join groups, find children, build meshes |
| `_physics_process(delta)` | Every physics tick, a fixed 60 times a second | Movement, AI, anything that touches physics |
| `_process(delta)` | Every rendered frame (may be faster or slower than 60) | Visual-only work: HUD drawing, fades, camera-fade checks, typing text |
| `_input(event)` | Every input event, first | Things that must see all input (device tracking, rebinding capture) |
| `_unhandled_input(event)` | Input events nothing else has consumed | Gameplay input (pause, orders, mouse steering) |

`delta` is the time since the last call, in seconds. Multiplying by `delta` makes behaviour frame-rate independent.

**`@onready var x = $Path`** fetches a child node just before `_ready()` runs. `$Model/MuzzleL` is shorthand for `get_node("Model/MuzzleL")`. `%StartButton` finds a node marked *unique name in owner* anywhere in the same scene.

### Physics bodies and collision layers
- **`CharacterBody3D`** (all fighters): moved by code via `velocity` and `move_and_slide()`, which stops at and reports collisions.
- **`StaticBody3D`** (asteroids, destroyer parts): solid, doesn't move on its own.
- **`AnimatableBody3D`** (destroyer hull): moved by code, but pushes and blocks others like a solid wall.

Every body has a **collision layer** (what it *is*) and a **collision mask** (what it *collides with* or *detects*). This project uses three layers, defined as constants on `Fighter`: World (1), Friendly (2), Enemy (4). See [section 8.6](#86-lasers-and-hit-detection) for how they keep friendly fire out.

**Raycasts** (`PhysicsRayQueryParameters3D` + `direct_space_state.intersect_ray`) test a line segment against the physics world. They're used for laser hits, the crosshair, line of sight and turret clear-shot checks.

### Signals
A signal is an event a node announces: `signal destroyed`, then `destroyed.emit()`. Others subscribe with `node.destroyed.connect(some_function)`. Signals let a node say "this happened" without knowing who cares. Examples: `EnemyFighter.destroyed` → the spawner counts it; `Ship.died` → `Level` restarts the level; `WingCommand.selection_changed` → listeners can react to a new wingman selection.

### Groups
A group is a named tag on nodes: `add_to_group("enemies")`. Any code can then call `get_tree().get_nodes_in_group("enemies")` or `get_first_node_in_group("player")`, or `get_tree().call_group("hud", "add_score", 1)` to call a method on every member. **This is the main way systems find each other here**, and it means no system holds a hard-coded path to another. The full list is in [section 5](#how-systems-find-each-other).

### Autoloads
An autoload is a node Godot creates at startup and keeps across scene changes, reachable everywhere by name. This project has two, registered in `project.godot`:
- **`Settings`** (`settings/settings.gd`): input bindings, display settings, which device you're using.
- **`SceneFader`** (`ui/scene_fader.gd`): fade-to-black scene changes.
- **`Music`** (`audio/music.gd`): plays the level's or title's soundtrack, see [8.17](#817-sound).

### Resources
A **Resource** is a data object saved as a `.tres` file (or embedded in a scene): materials, meshes, environments, themes. You can define your own by writing a script that `extends Resource`. This project defines a few: `CommsSpeaker` (a character's name, colour, portrait and beep pitch) and `Pilot`, which extends it with a flying character's accent colour and battle lines, with one `.tres` per character in `comms/speakers/` (Fox is a plain `CommsSpeaker`; Falco, Slippy and Krystal are `Pilot`s). `LevelMusic` and `Mission` are others.

### Tweens and `await`
A **Tween** animates a property over time: `create_tween().tween_property(node, "modulate:a", 1.0, 0.6)` fades a node in over 0.6 s. **`await`** pauses a function until a signal fires, then resumes it: `await get_tree().create_timer(3.0, false).timeout` waits 3 seconds (the `false` means "don't run while paused"). Functions that `await` become coroutines; this project uses them for multi-step sequences like the destroyer's death explosions, hangar launches and scene fades.

### 2D on top of 3D: CanvasLayers and `_draw()`
UI lives on **CanvasLayers**, which draw on top of the 3D view in order of their `layer` number. This project's layers: HUD (1), Comms (5), pause menu (10), SceneFader (100).

Most UI uses `Control` nodes (`Button`, `Label`...). The **HUD is different**: one `Control` overrides `_draw()` and draws everything with `draw_line`, `draw_rect`, `draw_string` and friends, every frame. See [section 8.12](#812-the-hud).

### Shaders
Shaders are small GPU programs, written in Godot's GLSL-like shading language (`.gdshader`). This project has nineteen, plus shared includes: toon lighting (`toon.gdshader`, `toon_clip.gdshader` for the warping destroyer, `toon_unlined.gdshader` for foliage without ink outlines; the light model and surface body live in `toon_light.gdshaderinc` and `toon_surface.gdshaderinc`), the planet terrain, the Arwing pilot band, water (noise shared with the terrain in `noise.gdshaderinc`), ink outlines, the shield bubble, the warp portal, the comms portrait static, the explosion puffs, the hit burst, the water splash and the wake's spray, the waterfall, the laser bolts and their glow, the clouds and the procedural sky (which can also draw a distant planet). See [section 8.15](#815-visual-style).

### Pausing and process modes
Setting `get_tree().paused = true` freezes every node whose `process_mode` is *Inherit/Pausable* (the default). Nodes that must keep running while paused set `process_mode = PROCESS_MODE_ALWAYS`: the pause menu, the settings menu, `Settings`, `SceneFader` and `Music`.

---

## 4. Working on the project

### Running it
- **Editor:** open `project.godot` in Godot 4.7.2, press **F5** (runs the main scene, the title screen) or **F6** (runs the scene you have open; open `main.tscn` or `levels/corneria.tscn` and press F6 to skip the title screen and mission selector).
- **Command line:** `godot --path .` runs the game from the project folder. `godot` here means your Godot executable (for example `C:/Users/<you>/.../Godot_v4.7.2-stable_win64.exe`).

### Editing
- **Scripts** can be edited in the Godot editor or VS Code. For VS Code, the *godot-tools* extension gives highlighting, autocomplete and go-to-definition while the Godot editor is open.
- **Scenes** (`.tscn`) are best edited in the Godot editor. They're plain text, so small hand edits (changing a number, adding a property line) work too; several in this project were written by hand.
- **If the editor or VS Code says "Could not find type X"** after you add a `class_name` script outside the editor, Godot's class cache is stale. Focus the Godot editor (it rescans) or run `godot --headless --path . --import`.

### Where tuning lives
- **Per-node behaviour:** exports in the Inspector. Select `Ship` in `player/ship.tscn` for flight and shields, `EnemySpawner` in `levels/level_base.tscn` for waves, `Falco`/`Slippy`/`Krystal` in `levels/level_base.tscn` for each wingman, and so on.
- **Per-type defaults:** the scene files (`enemy_fighter.tscn`, `light_fighter.tscn`, `laser.tscn`...).
- **Look:** shader uniforms on the materials, and `world/space_environment.tres` for sky, ambient light and glow.

### Version control
The project folder isn't a git repository yet. Before you start making your own changes, it's worth running `git init` and committing the current state, so you can always see what you changed and roll back. Add a `.gitignore` containing `.godot/` (Godot's local cache).

---

## 5. Architecture: the big picture

### Folder map

```
main.tscn / main.gd      The Space Station mission (inherits levels/level_base.tscn): the asteroid field
levels/                  The shared level base (level_base.tscn + Level script) and other missions (corneria.tscn)
missions/                Mission resources listed by the mission selector
player/                  The player's ship, the shared flight model, the chase camera
ai/                      Shared AI brain for every computer-flown ship
wing/                    Wingmen and the order system
enemies/                 Enemy fighters, waves, the destroyer and its parts
weapons/                 Laser bolts (one script, three scenes)
world/                   Asteroids, the intro cutscene, speed dust, the sky; planet terrain (and TerrainMap, MapProps), clouds, the play boundary, the Great Fox, the space station
effects/                 Explosions, enemy wrecks, muzzle flashes, one-shot sounds, the shield bubble, toon shading, ink outlines
audio/                   Sound effects (audio/sfx/), level music (LevelMusic + the Music autoload)
models/                  3D models: the Arwing (player and wingmen), the Great Fox scenery, the destroyer, the enemy fighter, the Corneria map and the space station (ours; each built by a Blender script in its source/ folder)
comms/                   The dialogue box and its characters
ui/                      HUD, title screen, pause menu, settings screen, scene fader, theme, the UI font (ui/fonts/)
settings/                The Settings autoload: input bindings and display options
docs/                    This guide
```

### The class hierarchy

Every ship in the game is a `Fighter`. The flight model lives in one place; what differs is the **pilot**.

```
CharacterBody3D (Godot)
└── Fighter              player/fighter.gd     flight model, guns, twin lasers
    ├── Ship             player/ship.gd        pilot = your input; shields, crosshair, death
    └── AIPilot          ai/ai_pilot.gd        pilot = AI: steering, avoidance, attack runs
        ├── Wingman      wing/wingman.gd       orders, formation flight, weapons free
        └── EnemyFighter enemies/enemy_fighter.gd   patrol / chase / evade / seek

StaticBody3D (Godot)
├── Asteroid             world/asteroid.gd
└── DestroyerPart        enemies/destroyer_part.gd     bridge, thrusters (base class)
    ├── DestroyerTurret  enemies/destroyer_turret.gd
    └── DestroyerHangar  enemies/destroyer_hangar.gd

AnimatableBody3D (Godot)
└── Destroyer            enemies/destroyer.gd   owns its parts, moves, launches, dies

Node3D: Laser, HitBurst, Explosion, ObstacleProxy, ObstacleBox              Node: WingCommand, EnemySpawner, IntroCutscene
CanvasLayer: Comms, PauseMenu, SceneFader   Control: HUD overlay, SettingsMenu
Resource: CommsSpeaker, Pilot (extends CommsSpeaker), LevelMusic, Mission
```

Note that a **wingman is a subclass of `AIPilot`, not of `Ship`**, even though its scene inherits `ship.tscn`. The scene gives it the same body and model; the script gives it a different brain.

### A level's scene tree (the Space Station mission)

```
Main (main.gd, extends Level)       inherits levels/level_base.tscn; everything below comes from the base except ★
├── WorldEnvironment, Sun          lighting and sky
├── Ship (ship.tscn)               you
├── ChaseCamera (chase_camera.gd)
│   └── InkOutline                 full-screen outline pass
├── SpaceDust ★                    speed streaks
├── Asteroids ★                    filled in by main.gd's _build_world()
├── PlayBoundary ★                 edge of the area, radius 4000 m on the Space Station mission (play_boundary.gd)
├── GreatFox ★                     the team mothership, scenery behind the intro start (great_fox.tscn)
├── SpaceStation ★                 the Cornerian station at the centre of the field: solid scenery (space_station.tscn)
├── Falco, Slippy, Krystal           (wingman.tscn ×3, each with its own slot, colour and speaker)
├── WingCommand                    order system
├── EnemySpawner                   waves (adds enemies and destroyers as siblings at runtime)
├── HUD (hud.tscn)                 CanvasLayer → Overlay control that draws everything
├── Comms (comms.gd)               CanvasLayer, layer 5
├── PauseMenu (pause_menu.tscn)    CanvasLayer, layer 10, includes a SettingsMenu
├── IntroStart, IntroCameraSpot    markers used by the intro
└── IntroCutscene
```

Runtime-spawned things (enemy fighters, destroyers, lasers, explosions) are added as children of the level root too. Corneria (`levels/corneria.tscn`) has the same base nodes and its own `PlayBoundary` and `GreatFox`, with `Terrain`, `Props` (the map's buildings and scenery) and `Clouds` instead of `SpaceDust` and `Asteroids`.

### How systems find each other

There are three mechanisms, and it's worth knowing which is used where:

1. **Exported node references**, set in the scene: `Wingman.leader`, `ChaseCamera.target`, `WingCommand.leader`, the `IntroCutscene`'s ship/camera/hud/markers. Used when the relationship is fixed for the level.
2. **Groups**, for "find me whoever plays this role":

   | Group | Members | Who looks it up |
   |---|---|---|
   | `player` | `Ship` | HUD, enemies, turrets, space dust, spawner |
   | `wingmen` | the active `Wingman` nodes | WingCommand, HUD, turrets, other wingmen |
   | `enemies` | `EnemyFighter`s | HUD, radar, Cover Me, Weapons Free, spawner |
   | `targets` | asteroids, enemies, intact destroyer parts | order targeting (`WingCommand.pick_target()`, which skips anything whose `attack_target` is false, such as asteroids) |
   | `obstacles` | asteroids, enemies, destroyer and space station `ObstacleProxy` spheres, and `ObstacleBox` boxes (the Juggernaut's hull) | AI obstacle avoidance |
   | `station` | `SpaceStation` (Space Station mission; joined in `_enter_tree`) | `main.gd` (asteroid placement), spawner (waves, destroyer destination) |
   | `destroyer` | the `Destroyer` | HUD |
   | `destroyer_parts` | every `DestroyerPart` | (available for queries) |
   | `hud` | the HUD overlay | `call_group("hud", "add_score", n)` from anything destroyed |
   | `wing_command` | `WingCommand` | HUD, `EnemySpawner` (destroyer callout) |
   | `enemy_spawner` | `EnemySpawner` | tests |
   | `terrain` | `Terrain` (planet missions only) | chase camera, AI ground avoidance, spawner, wingman slots |
   | `boundary` | `PlayBoundary` (missions with an edge) | ship (turn back), HUD, enemy patrols, spawner |
   | `comms` | `Comms` | via `Comms.find(get_tree())` |

3. **Signals**, for "tell whoever cares": `Ship.died`, `IntroCutscene.finished`, `EnemyFighter.destroyed` / `Destroyer.destroyed` (wave tracking), `DestroyerPart.destroyed` (kill rule), `WingCommand.order_feedback` (nothing listens at the moment) and `selection_changed`, `Settings.bindings_changed` / `display_changed` / `input_device_changed`, `SettingsMenu.closed`.

### Scene flow

```
title_screen.tscn ──Start──▶ MissionSelect ──pick──▶ SceneFader.change_scene(mission.scene_path)
                                       │
Level._ready():  _build_world() (asteroids, or nothing), capture mouse
                ├── first load:  IntroCutscene.play()  ──finished──▶ _begin_play()
                │                 + after 0.5 s: Fox's intro line on the comms
                └── after death: _begin_play() at once (intro skipped, line said here)
                                       │
                         _begin_play(): EnemySpawner.start() → waves begin (unless spawn_enemies is off)

Ship.died ──▶ Level waits restart_delay (3 s) ──▶ reload_current_scene() (the same mission)
                (a static flag, _skip_intro_once, survives the reload)

Pause menu "Quit to Title" ──▶ change_scene_to_file(title_screen.tscn)
```

### The order things run in each physics tick

Godot runs `_physics_process` on nodes in order of `process_physics_priority` (lower first). The project sets priorities deliberately so that followers react to the *current* frame's position of whatever they follow:

| Priority | Who | Why |
|---|---|---|
| 0 (default) | Ship, enemy fighters, destroyer, turrets, lasers, WingCommand | Move first |
| 5 | Wingmen | Follow the leader's position *this* frame, not last frame's |
| 10 | ChaseCamera | Frame the ship after everything has moved |
| 20 | IntroCutscene | Drives the camera during the intro, after the ships move |

Then, every rendered frame, `_process` runs: HUD redraw, comms typing, wingman camera fade, space dust, asteroid spin, shield bubble animation.

---

## 6. Walkthrough: one shot, from button to explosion

Following one bolt through the code is the fastest way to see how the pieces connect. Open the files as you go.

**1. Input is registered.** At startup, the `Settings` autoload adds an action called `fire` to Godot's InputMap, bound to Left Mouse, Space and the right trigger ([settings.gd](../settings/settings.gd), `_default_bindings()` and `_apply_bindings()`).

**2. The ship reads it.** Every physics tick, `Fighter._physics_process` calls `_think()`. In [ship.gd](../player/ship.gd), `_think` sets `is_firing = Input.is_action_pressed("fire")`.

**3. The crosshair picks an aim point.** After moving, `Fighter` calls `_aim()`. `Ship._aim` casts a ray 700 m straight ahead against World and Enemy layers. If it hits something, `aim_point` is the hit position and, if that thing can take hits, it becomes `aim_target`, and if its optional `highlight_on_crosshair` property allows it (`Fighter.highlights_crosshair()`: on unless set to false; off on asteroids, which are everywhere in the field and would drown out the enemies) the HUD turns the crosshair red (`aim_on_target`). If not, `aim_point` is 220 m straight ahead. While firing at a target, it's also remembered as `fire_target` for 1.5 s, which wingmen in formation use to join in.

**4. The gun fires.** `Fighter._update_weapons` counts down a cooldown (`fire_interval`: 0.09 s on `ship.tscn`, so about 11 shots a second for you and your wingmen, who inherit it; 0.35 s for elite enemies, 0.8 s for light fighters) and, if `_wants_fire()` (which returns `is_firing` for the ship), calls `_fire()`, which plays the ship's `FireSound` (see [8.17](#817-sound)). Muzzles alternate left and right.

**5. The bolt is launched.** `_fire()` instantiates `laser_scene` (`weapons/laser.tscn`) and adds it to the level. Because the ship has `parallel_fire` on, the bolt's direction is the line from the point between the two muzzles to the aim point, so it leaves its muzzle (at the root of the blue fins) **parallel** to that line: twin lasers, as in *Star Fox 64* (see [8.1](#81-the-flight-model-fighter)). It calls `Laser.launch(origin, direction, speed, shooter)`; the bolt's speed is `laser_speed + speed`, so it inherits the ship's speed. With `muzzle_flash_size` above 0, `MuzzleFlash.spawn()` puts a 70 ms flash on the muzzle.

**6. The bolt flies and checks for hits.** Each physics tick, [laser.gd](../weapons/laser.gd) moves the bolt by `velocity × delta`, and **raycasts along that step** (so a fast bolt can't skip through a thin object between frames). It then stretches its glowing mesh behind it (`trail_length`, 8 m on `laser.tscn`), never longer than the distance it has flown so far, so the streak starts at the muzzle instead of poking back through the ship. The ray uses the bolt's `collision_mask`: player bolts (mask 5) hit World + Enemy, never Friendly.

**7. The hit lands.** If the ray hits something, `_cast()`:
- calls `notify_shot(origin)` on it if it has that method (enemy fighters use it to start evading; your ship records it for the HUD's hit-direction arc),
- if the hit destroyed it, calls `notify_kill(victim)` on the shooter if the shooter has that method and still exists (wingmen use it for kill celebrations and the Weapons Free cooldown; the player's ship for wingman praise),
- calls `take_hit(damage, position)` on it if it has that method,
- spawns a `HitBurst` (a cartoon star and sparks) if the thing it hit can be shot (it has `take_hit`), a `WaterSplash` on water, otherwise a smaller `HitBurst` in the bolt's colour (`surface_hit`), and frees the bolt.

**8. The enemy takes damage.** [enemy_fighter.gd](../enemies/enemy_fighter.gd) `take_hit` subtracts health. While it has some left, its `HitReaction` makes the hit show: the model flashes red and flinches, and it starts trailing smoke, then fire (see [8.15](#815-visual-style)). At 0 it sets off an `Explosion` (`explosion` style and `explosion_size` exports on `Fighter`; see [8.15](#815-visual-style)), plays its explosion sound through `SoundFX.play_at()`, calls `get_tree().call_group("hud", "add_score", 1)`, hands its `Model` to a `Wreck` (which flies on, smoking, and explodes again: see [8.15](#815-visual-style)), emits `destroyed`, and `queue_free()`s itself (removed at the end of the frame).

**9. The wave notices.** When the spawner created this enemy, it called `track(enemy)`, which connected `destroyed` to `_on_enemy_destroyed`. That waits one frame (so the dead enemy has left the tree), then if no fighters and no destroyer remain, schedules the next wave in 6 s.

That's the general shape of almost everything in this codebase: **a pilot decides → the Fighter acts → physics queries find out what happened → duck-typed methods (`take_hit`, `notify_shot`) deliver the effect → signals and groups tell the rest of the game.**

> **Duck typing:** the laser doesn't know what it hit. It just checks `has_method("take_hit")`. Anything with a `take_hit(damage, at)` method is shootable: asteroids, enemies, destroyer parts, and the player's ship. Wingmen deliberately have no `take_hit`, which is why they can't be hurt.

---

## 7. Walkthrough: one order, from D-pad to "You got it!"

**1. Selecting.** You press D-pad left. [wing_command.gd](../wing/wing_command.gd) `_unhandled_input` sees the `select_wingman_1` action (the selection actions are numbered by `wing_index`, not named after wingmen, so the squad can be any size up to three; ignored if the ship's controls are disabled, as in cutscenes), finds the wingman with `wing_index` 0 and calls `toggle_select()`. `selected` now holds Falco, and `selection_changed` fires. The HUD's wing panel reads `_wing.selected` on its next redraw and lights Falco's card.

**2. Ordering.** You press Y (`command_attack`). `order_attack(pick_target())` runs. `pick_target()` returns whatever is under your crosshair (`leader.aim_target`), or failing that the `targets` group member closest to the crosshair within a small angle, preferring enemy fighters. Either way only things the Attack order may pick (`Fighter.is_attack_target()`: an optional `attack_target` property, on unless set to false; off on asteroids), so a rock under the crosshair is looked past.

**3. Routing.** `_issue()` asks `recipients()` who gets the order: the selection if there is one, otherwise every wingman whose standing order isn't Cover Me. Recipients already carrying out that exact order (the same order, or for Attack the same target) are skipped; if that leaves nobody, the order is silently dropped, with no feedback or acknowledgement. For each remaining recipient it calls the order's `assign_*` function (here `assign_attack(target)`), emits `order_feedback("Falco: attacking fighter")` (no longer shown on screen: the acknowledgement and the wing panel are the feedback), and clears the selection.

**4. The wingman takes the order.** [wingman.gd](../wing/wingman.gd) `assign_attack` sets `order = ATTACK` and calls `command_attack(target)`, which sets `state = ATTACK` and first flies to a **split point** off to the wingman's break side, so wingmen sent together fan out instead of flying in a clump.

**5. The acknowledgement.** `_issue()` picks one recipient at random and calls `_acknowledge()`, which picks one of the `acknowledgements` in that wingman's pilot file (for Falco, "You got it!" or "On it!"), never the one it used last, and calls `Comms.find(get_tree()).say(wingman.pilot, line)`. That's a low-priority line, so if someone is already talking it's silently dropped.

**6. The comms box types it out.** [comms.gd](../comms/comms.gd) opens the box (a line expands into the portrait square, static, then the portrait and name as the text box unfolds), then reveals one character every 1/40 s, beeping on every other letter at Falco's pitch. It holds, then closes by running the opening backwards.

**7. The attack plays out.** Every tick, `Wingman._decide` sees `state == ATTACK` and returns `_attack_goal(target, side)`, the shared AI attack behaviour. When the target is destroyed, `target_gone()` becomes true, the wingman calls `command_follow()`, and because its `order` was ATTACK it reverts to its `standing_order` (Form Up, unless you'd given it Cover Me or Weapons Free before).

The key idea is the split between **order** (what you told the wingman: a *player-facing* value shown on the HUD) and **state** (what it's physically doing right now: FOLLOW or ATTACK). Cover Me and Weapons Free switch state on their own as threats appear, without the order changing.

---

## 8. Systems in depth

### 8.1 The flight model (`Fighter`)

**File:** [player/fighter.gd](../player/fighter.gd)

`Fighter` is an arcade flight model: ships always fly forward, along their nose (−Z), and turning is direct.

**Each physics tick:**
```
_think(delta)          pilot decides (input or AI)
_update_rotation       stick → turn rates → rotate
_update_speed          throttle → speed
velocity = forward × speed + _velocity_offset()
move_and_slide()       move, stop at collisions
_handle_collisions     on a hit: drop to min speed, nudge out
_update_model          visual bank and pitch tilt of the model
_aim(delta)            pilot sets aim_point
_update_weapons        fire if wanted and the cooldown allows
```

**Turning.** The pilot returns a virtual stick from `_get_stick()`: x is yaw (right positive), y is pitch (down positive, like a screen). The target turn rates are `(-stick.y × pitch_rate, -stick.x × yaw_rate, roll × roll_rate)`. Actual rates ease towards those with `turn_response`, which gives turns a little weight. The rotation is applied in the ship's own frame each tick.

**Auto-level.** When the pilot isn't rolling (`_get_roll()` returns 0), the ship rolls itself so its right wing is level relative to `_get_level_up()`. `basis.x · up` measures how far the right wing points up; rolling against it levels the ship. The player and enemies level to world up; wingmen in formation level to *the leader's* up, so they roll with you.

**Banking is visual only.** `_update_model` tilts the `Model` child (not the body) into turns, proportional to the yaw rate from `_visual_turn_rates()` (the stick-driven rates by default) as a fraction of the ship's `yaw_rate`. The physics body never banks. Wingmen override `_visual_turn_rates()` with the rate they actually turned last frame, because formation flight turns them directly rather than through the stick (see [8.8](#88-wingmen)); in formation they also rescale it to the leader's turn rates, so they bank exactly as much as you.

**Speed.** `_get_target_speed()` is clamped between `min_speed` and `boost_speed`, the absolute top speed. `max_speed` is the top speed in normal flight; acceleration is faster (`boost_acceleration`) above it or when heading above it, which only the AI does (enemies evading or closing in, wingmen catching up). There is no player boost: the player's full throttle is already the fastest it flies.

**`_velocity_offset()`** adds velocity on top of "fly along the nose". It's zero for everyone except wingmen in formation, who use it to slide a little sideways to hold their slot (see [8.8](#88-wingmen)).

**The pilot interface** (override these in a subclass):

| Function | Returns |
|---|---|
| `_think(delta)` | (nothing) runs first each tick |
| `_get_stick() -> Vector2` | x = yaw right, y = pitch down, each −1..1 |
| `_get_roll() -> float` | positive rolls left; 0 = auto-level |
| `_get_target_speed() -> float` | desired speed |
| `_wants_fire() -> bool` | |
| `_get_level_up() -> Vector3` | "up" for auto-level |
| `_aim(delta)` | (nothing) sets `aim_point` after moving |
| `_velocity_offset() -> Vector3` | extra velocity (default zero) |
| `_get_pitch_rate() -> float` | pitch rate at full stick (default `pitch_rate`; wingmen raise it to somersault) |
| `_get_acceleration(fast) -> float` | how fast speed changes (default `acceleration`, or `boost_acceleration` when `fast`) |

**Twin lasers.** With `parallel_fire` on (`ship.tscn`, so you and the wingmen; off on enemies), each bolt flies from its muzzle parallel to the line from the ship's centre through the aim point:

```
 muzzle L ●──────────────────────────────────────▶  (0.87 m left of the line)
          ·  centre ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─▶  aim point
 muzzle R ●──────────────────────────────────────▶  (0.87 m right of the line)
```

The muzzles sit 0.87 m either side of the centre, less than an enemy fighter's 1.1 m hit sphere, so the pair lands on whatever is under the crosshair at any range. With it off, each bolt flies from its muzzle straight to the aim point, meeting there and drifting apart beyond it (enemies use this).

*History:* the old primitive ship had its guns on the wingtips, 3 m out, so parallel bolts would have straddled small targets. It used **converging fire** instead: each bolt bent once, 30 m ahead, onto the crosshair line. At about 10 m per frame the bend happened within three frames and read as a sudden sideways jump, so it was dropped when the Arwing's fin muzzles made it unnecessary.

**Muzzle flash** (`muzzle_flash_size`, 0.6 on `ship.tscn`, 0 = off): `MuzzleFlash` ([effects/muzzle_flash.gd](../effects/muzzle_flash.gd)) is a stretched additive blob plus a small light, parented to the muzzle so it rides along with the ship, fading over 70 ms. It's drawn without depth testing, because from the chase camera the Arwing's muzzles sit behind its upper fins. The colour is the bolt's `impact_color`.

**Physics layers** are constants here: `LAYER_WORLD = 1`, `LAYER_FRIENDLY = 2`, `LAYER_ENEMY = 4`, `LAYER_HURTBOX = 8` (enemy hurtboxes, see [8.6](#86-lasers-and-hit-detection)). **`radius_of(node)`** is a static helper that reads a `radius` property from anything that has one (asteroids, fighters, parts, proxies), defaulting to 5 m; the AI uses it for aiming tolerance and obstacle clearance.

### 8.2 The player's ship (`Ship`)

**File:** [player/ship.gd](../player/ship.gd), scene [player/ship.tscn](../player/ship.tscn)

**Steering input** comes from two sources that share one virtual `stick`:
- **Mouse:** in `_unhandled_input`, mouse motion *accumulates* into `stick` (scaled by `mouse_sensitivity`, clamped to length 1). The stick stays where you leave it, like a joystick held at an angle; `mouse_recenter` can make it drift back (0 by default). The HUD draws this stick as the small circle inside the faint ring around the screen centre.
- **Gamepad / arrow keys:** `Input.get_vector("steer_left", "steer_right", "steer_up", "steer_down")` replaces the stick directly while held, and releases it to zero when let go.

`stick_deadzone` ignores tiny deflections; `invert_y` flips pitch.

**Throttle** (`throttle_up` / `throttle_down`) maps −1..1 onto min..cruise..max speed: 20, 60 and 130 m/s for the player (set in `ship.tscn`; wingmen override cruise back to 45 in `wingman.tscn`). The player changes speed at `acceleration` 60 m/s² (`ship.tscn`; the script default, which wingmen keep, is 35): cruise to full throttle takes about 1.2 s, cruise to minimum about 0.7 s. There is no boost: full throttle is as fast as boost used to be (130), and cruise sits halfway between the old cruise (45) and the old full throttle (75). **Roll** is `roll_left` / `roll_right`. **`controls_enabled = false`** (used by the intro) zeroes all input and flies at `autopilot_speed`.

**Thruster heat.** Throttling up or down heats the thrusters (`thruster_heat`, 0..1), in proportion to how far the throttle is pushed: `heat_time` (5.2 s) of full throttle either way overheats them; half throttle takes twice as long. Released, they cool from full in `cool_time` (3 s). Overheated (`overheated`), the throttle is ignored, so the ship eases back to cruise speed (from 130 m/s that takes about 1.2 s), while the heat drains over `overheat_time` (3 s); then it works again. `_update_thrusters()` runs in `_think()` and sets the throttle `_get_target_speed()` uses. It limits how long you can sit at full speed (about 3.6 s at 130 m/s after the 1.2 s it takes to get there) or hang back at minimum speed, which is the balance for removing boost. `thrusters_overheated` / `thrusters_cooled` signals fire on the changes, for anything that wants to react (a wingman line, a sound). The HUD bar under the shields shows what's left: blue (`COLOR_THRUSTERS`, the old boost bar's look), full when cool and emptied by throttling (`1 - thruster_heat`), so empty means overheated. During the lockout it refills in red, fading slowly out and in (`OVERHEAT_BLINK_PERIOD` 1 s, down to `OVERHEAT_BLINK_MIN_ALPHA` 0.2), and the throttle works again when it is full. The AI has no thruster heat. **`thrusters_overheat`** switches all of this off (heat never builds, the HUD hides the bar); `ship.tscn` has it off, leaving the throttle unlimited, since destroyer turret lock-on ([8.10](#810-the-destroyer)) now punishes hanging back slowly.

**Shields** are a small state machine:

```
          hit (shields ≥ 1)                      no hit for 3 s
 ┌─────────┐ ──────────────▶ shields -= damage ─────────────────▶ recharge 10/s
 │ UP      │
 └─────────┘ ── hit takes shields below 1 ──▶ ┌──────────────┐  12 s without   ┌────┐
                                               │ DOWN (reboot)│ ──────────────▶ │ UP │ (from 0)
     any hit while DOWN (or at < 1) ──▶ DEAD   └──────────────┘                 └────┘
```

Shields absorb *any* hit as long as at least 1 point is left, whatever the damage. The `ShieldEffect` child plays `flash()` on a hit, `collapse()` when knocked out and `shimmer()` when back online; the HUD reads `shields`, `shields_down`, `shield_reboot_progress()` and `damage_flash`. Signals `shields_depleted` and `shields_online` fire on the transitions (nothing listens yet: good hooks for comms lines).

**Crashing.** The ship's collision mask is 5 (World + Enemy), so it physically hits asteroids, the destroyer hull, terrain and enemy fighters. `Ship._handle_collisions()` (overriding `Fighter`'s) treats a collision as a crash: it takes `crash_damage` (30) through `take_hit()` (so with shields down, a crash is fatal), at most once per `crash_cooldown` (0.5 s) and never again during the recovery. The bounce then plays out over `crash_recover_time` (0.6 s) instead of in one frame, which used to feel like a teleport (the nose could swing 90–160° in a single frame, and the camera with it):
- the nose swings smoothly (`crash_turn_sharpness` 5) to a glancing deflection, halfway (`crash_deflect` 0.5) between skimming along the surface and heading straight out from it, with a little random scatter; the player's stick and roll are ignored meanwhile (`_update_rotation()` override);
- a push away from the surface cancels any speed still going into it plus `crash_push_speed` (10 m/s), fading at `crash_push_fade` (4/s) (`_velocity_offset()` override);
- the ship slows to `min_speed` and accelerates back normally; a small random wobble (`crash_wobble` 1 rad/s) and a camera shake (`crash_shake` 0.6).

Measured (dives into flat ground at 15°, 45° and 80°, and head-on into an asteroid): the largest per-frame turn went from 25–164° to 4–13°, the camera's from 19–142° to 3–10°; every case was a single crash and ended clear of the surface.

Wingmen use mask 1 (World only, overridden in `wingman.tscn`) and AI ships use `Fighter`'s plain collision response: slow down and nudge out.

**Death** (`_die()`) hides the model, removes the collision layer, stops physics and emits `died`.

**Play boundary.** On a mission with a `PlayBoundary` (both missions), `_update_turn_back()` runs after input each tick. Past `radius + turn_back_margin` it sets `turning_back`: `_get_stick()` returns an automatic stick that turns the ship towards the middle of the area (roll input is ignored), climbing hard if the ground is within `turn_back_clearance` (60 m; planet missions only). Once the heading is within `turn_back_done_deg` (25°) of the way back, control returns and the mouse stick is reset, so the ship doesn't swing straight back out. The HUD shows the warnings, see [8.19](#819-planet-terrain-corneria).

### 8.3 The chase camera

**File:** [player/chase_camera.gd](../player/chase_camera.gd)

The camera sits at `offset` (2.6 m up, 11 m back) in a *lagging copy* of the ship's orientation. Each tick, `_basis` slerps towards the ship's basis by `1 − exp(−follow_sharpness × delta)`, so in a turn the camera swings a little behind, which makes turns feel weighty. It looks at a point 30 m ahead of the ship. Above cruise speed it pulls back (`speed_pullback` per unit of speed) and the FOV widens, from `base_fov` 70° at cruise to `top_speed_fov` 84° at the ship's `max_speed` (full throttle).

- `chase_transform()` gives the lag-free position (the intro flies the camera to it).
- `snap()` drops the lag and jumps into place.
- On a planet mission (a node in the `terrain` group), the camera stays at least `ground_clearance` (3 m) above the ground or water, see [8.19](#819-planet-terrain-corneria).

### 8.4 The AI pilot (`AIPilot`)

**File:** [ai/ai_pilot.gd](../ai/ai_pilot.gd)

This is the shared brain for wingmen and enemies. Subclasses only decide **where to go**; `AIPilot` turns that into stick input, handles obstacles and shooting.

**`_think()` pipeline, every tick:**
```
goal = _decide(delta)              subclass: the world point to fly towards
goal = _avoid_obstacles(goal)      swerve if something's on the flight path
goal = _avoid_ground(goal)         planet missions: stay above the ground, climb if the path dips too low
if we just scraped something:      steer away from its surface(s) for 0.8 s
_stick = _steer_towards(goal)      world point → stick deflection
if lead_turns and engaging:        add _tracking_stick(target)
```

The scrape recovery steers along the sum of the surfaces hit, plus the previous recovery direction while it is still running. With only the first surface, a ship wedged in a corner (a tower wall with a ledge above) turned towards the wall one frame and the ledge the next and never got out; in a Corneria combat test the combined direction also halved the time AI ships spent touching surfaces.

`_decide()` also sets four fields that the rest of the pipeline reads: `_target_speed`, `_engage` (what to shoot at, or null), `_level_up`, and through `_aim()`, `_firing`.

**Steering** (`_steer_towards`): convert the goal into the ship's local space; the x/y of the normalised direction, times `steer_gain`, is the stick. If the goal is behind, turn as hard as possible.

**Shooting** (`_aim`): if `_engage` is set, aim at its **lead point** (where it will be when a bolt gets there: `position + velocity × distance / bolt_speed`) and fire when the nose is within `fire_tolerance_deg` plus the target's angular size, inside `attack_range`. `aim_scatter` (metres) then moves the aim point randomly by up to that much in each axis, so even a perfectly lined-up pilot misses some shots: 4 on wingmen, 2 on elite fighters, 0 on light fighters. Otherwise fire only if `_wants_idle_fire()` (wingmen use this to fire along with you).

**Attack runs** (`_attack_goal(target, side)`) have two behaviours depending on the target:
- **Fighters:** sit `pursuit_distance` (50 m) behind and match speed, closing distance only when roughly facing the target (otherwise it orbits). Break off if too close or meeting head-on.
- **Anything else** (asteroids, destroyer parts): full-speed **strafing runs**. Approach, fire, and at `break_distance` from its surface, break away to a waypoint to the side and up, fly out, then turn in again. These runs need a clear view of the target (`_clear_view()`: one ray on the World layer, stopping `VIEW_MARGIN` 3 m beyond its radius so the surface it's mounted on doesn't count). If something solid is in the way during the approach, the pilot breaks off and repositions instead of pressing on, and the pull-out point must itself see the target: if the usual one (to the side and up, from the pilot's own orientation) can't, `_viewpoint()` tries a ring of `VIEW_RING` (8) directions level with the target, a ring above it and straight above, and takes the one closest to the usual direction. Without this, a banked wingman often pulled out under a destroyer and started its next run with the whole hull between it and a turret on top.

Breaking off uses a two-phase pattern: `APPROACH` and `BREAK`. In `BREAK`, the AI flies to `_waypoint` until it gets there or `_waypoint_timeout` runs out, then switches back to `APPROACH`. `_fly_to_then_attack(point, timeout)` starts a BREAK on purpose; wingmen use it for the opening split and for peeling off when crowded.

**Obstacle avoidance** (`_avoid_obstacles`): looks along the current flight path for `avoid_lookahead_time` (1.5 s) of travel. For the nearest member of `obstacles` that crosses that path, it replaces the goal with a point skirting its near side. Obstacles come in two shapes. Most are **spheres** (asteroids, fighters, and `ObstacleProxy` spheres on the station and the old destroyer's hull), kept radius × 1.3 + `avoid_margin` from their centre. An **`ObstacleBox`** ([enemies/obstacle_box.gd](../enemies/obstacle_box.gd)) is kept its `margin` + `avoid_margin` from its faces: the path is tested against the box grown by that much (`entry_distance()`), and the new goal goes out of the grown box through its nearest side face (`way_out()`, never the face straight ahead or behind) plus half the clearance again. Boxes are for big blocky hulls that would take hundreds of spheres (the Juggernaut: 15 boxes instead of 649 spheres). While attacking, obstacles beyond the target are ignored (the run breaks off before reaching them). When the target is a structure rather than a fighter, so is what it's mounted on: any sphere whose clearance zone holds the target (a destroyer turret sits inside the margin of the hull spheres under it, which otherwise kept wingmen from ever lining up), and any box our path meets within `mount_ignore_distance` (60 m) plus the target's radius of it. A box is often a whole hull, so only that stretch of it is ignored: farther along the path it still counts. Fighters are exempt: a rock beside one still counts. Waypoints (`_clear_of_obstacles`) are pushed out of spheres radially and out of boxes through the nearest face.

**Ground avoidance** (`_avoid_ground`, planet missions only: it does nothing without a node in the `terrain` group). Two parts:
- **Goals are raised** to at least `ground_clearance` (25 m) above the ground, water or buildings under them, except the lead point of a target being shot at (so pilots can still dive on a low target). `_clear_of_obstacles()` raises break and roam waypoints the same way.
- **The flight path is checked** at 7 points along the current heading, `ground_lookahead_time` (2 s) of flight ahead, straight down to `Terrain.clearance_height()`: the ground or water, or on a map with structures (Corneria) the top of the tallest building, arch or bridge on that 25 m cell. If any point is closer than the clearance, `_ground_danger` is set and the goal becomes a steep climb that keeps the same heading over the ground. This check uses the terrain's height functions, not raycasts, so it is cheap. Buildings count as raised ground rather than `obstacles` spheres: 170 towers' worth of spheres would be checked by every AI ship every tick. The catch: the AI flies **over** the city, never down its streets ([8.19](#819-planet-terrain-corneria)).

Measured on Corneria (3-minute runs, the player flying a loop over hills and mountains at 15, 35 or 60 m above the ground while waves attack and the wingmen cycle Form Up, Weapons Free and Cover Me): before this, enemies spawned inside the hills and spent the whole run underground. With it: 0 frames underground, and 1 enemy and 0 wingman ground scrapes across six 3-minute runs. The climb aims steeply on purpose: with a shallower climb (half the steepness) enemies on patrol hit 13 times in 12 runs, all climbing at about 40–50° into steeper ridges.

`_ground_clearance()` and `_ground_lookahead()` are virtual; wingmen in formation override them (see [8.8](#88-wingmen)).

**`lead_turns` and `_tracking_stick()`.** Plain steering towards a turning target always lags behind it: the stick only deflects in proportion to the *current* error, so by the time the nose catches up, the target has moved on. The result is a steady aiming error of around 10°, outside the firing window. `_tracking_stick` computes how fast the line of sight to the target is rotating, and adds exactly the stick needed to turn at that rate. Proportional steering then only corrects the leftover error. It's on for wingmen (`wingman.tscn`) and elite fighters, and off for light fighters; turning it on makes any pilot a much better shot.

### 8.5 Enemy fighters

**File:** [enemies/enemy_fighter.gd](../enemies/enemy_fighter.gd), scenes [enemy_fighter.tscn](../enemies/enemy_fighter.tscn) (elite) and [light_fighter.tscn](../enemies/light_fighter.tscn) (basic, used in level 1); model [models/enemy_fighter/](../models/enemy_fighter/) with [fighter_model.gd](../enemies/fighter_model.gd)

**The model: the Venomian "Mantis".** A tapered wedge body with one big glowing compound eye on the forebody, two pincer forelegs reaching past the nose with guns slung under them, swept-back wings ending in upright tip plates, a dorsal fin and twin engines: about 6.2 m across and 5.7 m long, Arwing-sized. Olive hull, dark keel, ribs and pincers, a purple-tinted canopy. To stand out against space it carries lights in the fighter type's colour: the eye, the pincer tips, a strip wrapped round each wing's leading edge (so it faces whoever is ahead) and a bar down the front of each tip plate, bright enough to bloom; the engine glow is the `Model/Glow` node (one wide oval over both nozzles), which `Fighter` brightens with speed. Head-on the lit wings and tip plates read as a coloured "I" shape out to about 170 m; beyond about 250 m any fighter is a few pixels and the HUD brackets and radar take over.

Like the destroyer, it's our own model built from code: [build_enemy_fighter.py](../models/enemy_fighter/source/build_enemy_fighter.py) (game coordinates; colours are the sRGB values the game shows) exports `enemy_fighter.glb`. One model serves both types: `FighterModel` (on the `Model/Mantis` instance) cel-shades it and paints the `Fighter_Accent` markings and `Fighter_Lights` in its `accent_color` / `light_color` / `light_energy`. The elite is purple with red lights (energy 10); `light_fighter.tscn` overrides them to tan with orange lights (energy 8). Muzzles sit at the gun tips, (±0.95, −0.42, −2.15).

A four-state machine. `_update_state()` handles transitions; `_decide()` picks the goal for the current state.

```
            spots player (cone + range + line of sight)
  PATROL ─────────────────────────────────────────────▶ CHASE ◀───┐
    ▲                                                     │  │      │ sees player
    │ 12 s without finding them                           │  │ hit  │ after evading
    │                                       no sight 3 s  │  ▼      │
   SEEK ◀─────────────────────────────────────────────────┘ EVADE ──┘
    ▲                                                          │
    └──────────────── doesn't see player after evading ───────┘
  (player dead → back to PATROL)
```

- **PATROL:** wander between random points around `patrol_center` (its spawn point). Spots the player within a 45° cone, 400 m, with clear line of sight. On planet missions, roam points are at least `patrol_min_altitude` (60 m) above the ground and `patrol_boundary_margin` (150 m) inside the `PlayBoundary`.
- **CHASE:** `_attack_goal(player)`. Keeps tracking within 700 m whenever nothing blocks the view, even if the player is behind it.
- **EVADE:** triggered by `notify_shot()` from a laser hit. Jinks hard away from the shooter at boost speed for 2.5 s, then ignores hits for 4 s so it gets to fight back.
- **SEEK:** searches near where the player was heading, with a wider, longer view; gives up after 12 s.

**Asteroids and terrain block line of sight** (the raycast uses the World layer), so hiding behind a rock, or flying low behind a hill, is a real escape.

**Hurtbox.** Two boxes surround each fighter. The `CollisionShape3D` (6.2 × 2 × 5.6 m, centred 0.5 m forward) is what it physically is: what you crash into. The `Hurtbox` child ([enemies/hurtbox.gd](../enemies/hurtbox.gd), an `Area3D`, 6.6 × 3.8 × 5.2 m, centred 0.5 m forward) is what friendly bolts and your crosshair hit. It's deliberately generous: wider and taller than the flat model, so shots that look like they clip a wing or the body count. With the old TIE-style model it was a 5.5 m cube (around a 4.4 × 4.4 × 2.4 m collision box); when the Mantis replaced it, the new box was sized to keep the hit rate about where it was, a touch in the player's favour. Simulated aim at a crossing, weaving light fighter (old cube, 4 runs → new box, 8 runs): 19.0 → 23.8% at 100 m with 0.5° of aim wobble, 20.8 → 20.8% with 1°, 4.9 → 5.8% at 200 m with 0.5°; 200 m with 1° is noisy (8.2 vs 3.9%, single runs range 0–16%). Hit rate is sensitive to the box: 6.8 × 4 × 5.6 m gave 26.9 / 24.0% at 100 m, a clear buff, and 6.4 × 3.6 × 5.0 m gave 19.8 / 19.8%. Wingmen don't notice (their kill time on a light fighter is identical with either size on each of 5 seeds, 3.5–5.2 s), because they aim at the centre. To make enemies easier or harder to hit, change the box size on `Hurtbox/CollisionShape3D` in `enemy_fighter.tscn` (light fighters inherit it). `radius` (aim assist, avoidance) is 3.5.

`begin_launch(duration)` is used by destroyer hangars: the fighter flies straight out with collisions off (so it can leave through the hull), then the AI takes over.

The two scenes differ only in exports and the model's colours: the light fighter has 3 HP, a fixed 55 m/s, slower turns and a slower fire rate. The elite has 4 HP, can speed up and boost, and aims much better: `lead_turns` on and an `aim_scatter` of 2. **The light fighter inherits the elite scene**, so anything set there applies to it too unless `light_fighter.tscn` overrides it, as it does for `lead_turns` (off) and `aim_scatter` (0).

### 8.6 Lasers and hit detection

**File:** [weapons/laser.gd](../weapons/laser.gd); scenes [laser.tscn](../weapons/laser.tscn) (player and wingmen, green; speed is `laser_speed` on `ship.tscn`, 1800 m/s; 16 m `trail_length`), [enemy_laser.tscn](../weapons/enemy_laser.tscn) (red, 4 damage, 250 m/s from `enemy_fighter.tscn`), [turret_laser.tscn](../weapons/turret_laser.tscn) (red, bigger, slower, 8 damage, 3 s lifetime)

One script, three scenes; they differ in look, damage, lifetime and **`collision_mask`**:

| Layer | Bit | On it | Collides with |
|---|---|---|---|
| World | 1 | asteroids, destroyer hull | everything |
| Friendly | 2 | player and wingmen | World; the player also Enemy (crashes) |
| Enemy | 4 | enemy fighters, destroyer parts | World (parts: nothing) |
| Enemy hurtbox | 8 | `Hurtbox` areas around enemy fighters | nothing (only raycasts look for it) |

- Player bolts: mask **13** (World + Enemy + Enemy hurtbox).
- Enemy and turret bolts: mask **3** (World + Friendly).
- The player's crosshair ray: World + Enemy + Enemy hurtbox.

Both friendly raycasts set `collide_with_areas`, because a `Hurtbox` is an `Area3D`: a box around each enemy fighter, bigger than its collision shape, that only bolts and the crosshair see. `Hurtbox.resolve(collider)` turns a hit on it into the fighter itself, so `take_hit`, `notify_shot`, `notify_kill` and `aim_target` all get the real enemy. Enemy and turret bolts also query areas, but their mask leaves out layer 8, so they ignore hurtboxes.

So neither side can shoot itself, and **if you add a new kind of object, decide its layer first.**

A bolt also excludes its shooter's RID from its raycasts so it can't hit the ship that fired it. Bolts move in straight lines and free themselves after `lifetime`. With `trail_length` above 0 (16 m on `laser.tscn`, a bit over half a frame of travel at 1800 m/s plus the ship's speed), the `Bolt` mesh is stretched behind the bolt's position and grows from the muzzle over the first frames, so a fast bolt reads as a continuous streak; enemy and turret bolts keep their modelled mesh.

**How bolts look.** Each bolt is light, not a solid object: `Bolt` is an open, tapered `CylinderMesh` (thin tail, full-width head; no end caps, which seen end-on from the chase camera showed as a bead or ring) drawn by [laser_bolt.gdshader](../weapons/laser_bolt.gdshader): unshaded and additive, a sharp spike: the head narrows to a point over its front `head_point` (15%) and the edges are crisp (`edge_softness` 0.2), with a white-hot core (`core_energy`, `core_width` 0.3) fading to the bolt colour (`energy`, 16 on the player and enemy bolts, 20 on turret bolts) at the edges, fading in from the tail over `tail_fade`, and kept at least `min_width_px` (1 px at 720p) wide far away so it doesn't flicker. It's 0.2 m in radius at the head on `laser.tscn` (0.24 enemy, 0.7 turret), tapering to 15% at the tail. Being transparent it writes no depth, so the ink outlines skip it: the bolts used to be an opaque emissive material, which got outlined like a hull and read as a solid green tube once they were far enough for bloom to stop covering the line. `Glow`, a quad under `Bolt` ([laser_glow.gdshader](../weapons/laser_glow.gdshader)), adds a soft halo: far bolts cover too few pixels for the screen-wide bloom to spread, so without it they lost their glow with distance. The shader lays the quad out on screen (in units of half the screen height, from the projection matrix alone) as a soft capsule along the bolt (laid out in view space instead, perspective skewed it off the bolt into an X; it shares the bolt's axis and stretching, given its unstretched `bolt_length`), even along most of its length and fading out over the last `tail_fade` (60%) towards the tail, like the bolt (fading all the way from the head made it read as a blob of light stuck on the front); end-on it comes out round. `size` is its width (0.8 m player, 1 m enemy, 2.5 m turret), at `energy` 3. It shrinks with distance like the bolt, with no minimum size: with one, far bolts lingered on screen as glowing dots that looked stuck. A round glow at the head alone made the bolts look like lollipops.

### 8.7 Waves and the spawner

**File:** [enemies/enemy_spawner.gd](../enemies/enemy_spawner.gd)

- `start()` (called by `Level._begin_play()` when you get control, if the mission's `spawn_enemies` is on) schedules wave 1 after `first_wave_delay`.
- Each wave: `first_wave_size + (wave − 1) × wave_growth` fighters, capped at `max_wave_size` (8) and by `fighter_room()`. They appear `spawn_distance` (600 m) away, roughly ahead of you, and patrol around that point, so you usually find them before they find you. With a space station in the level, that point is first pushed `spawn_station_margin` (100 m) clear of it (`SpaceStation.push_clear()`).
- Every `destroyer_every`-th wave (5, 10, 15...) also spawns a destroyer at the edge of the zone (`zone_radius`: 1000 m by default, 3000 m on the Space Station mission, inside its 4000 m boundary) if none is alive, and asks `WingCommand` to announce it. `destroyer_every = 0` means never (Corneria).
- `track(node)` connects a node's `destroyed` signal; when everything tracked is gone (no fighters, no destroyer), the next wave comes after `wave_delay`.
- **`max_fighters`** (12) caps enemy fighters alive at once, including hangar launches.

`enemy_scene` sets the level's fighter type for both waves and hangars.

**Planet missions:** with a `PlayBoundary`, the wave's centre is pulled in to at least `spawn_boundary_margin` (250 m) inside it; with a `Terrain`, the centre is at least `spawn_altitude` (80 m) above the ground, and each fighter at least half that above the ground under it.

### 8.8 Wingmen

**File:** [wing/wingman.gd](../wing/wingman.gd), scene [wing/wingman.tscn](../wing/wingman.tscn); each wingman's character is a `Pilot` file in [comms/speakers/](../comms/speakers/), its place in the wing is set on its node in [levels/level_base.tscn](../levels/level_base.tscn) (shared by every mission)

This is the largest and most intricate script. It's organised in regions: Orders, Weapons free, Formation flight, plus helpers.

#### Identity
**Who flies it** is the `Pilot` resource in the `speaker` export (see [8.13](#813-comms)): `call_sign` is its `display_name`, `accent_color` (fin panels and HUD) comes from it, and so do its lines. `pilot`, `call_sign` and `accent_color` are read-only properties on `Wingman`, so the HUD and `WingCommand` read them as before. **Its place in the wing** is set on the node: `wing_index` (0, 1, 2: HUD order and seniority on shared targets), `break_side` (−1 left, 0 up, 1 right) and `slot_offset` (formation slot in the leader's local space). `_paint_accent()` passes the accent colour to the ship's `ShipModel` (see [8.15](#815-visual-style)), which paints that wingman's fin panels.

#### Order and state
| Order (`order`) | Standing order? | What the wingman does |
|---|---|---|
| `FORM_UP` | yes | Hold the slot; fire with you when in formation |
| `ATTACK` | no | Go after one target until it's gone, then revert to `standing_order` |
| `COVER_ME` | yes | Wait in a trailing slot `cover_trail_distance` (35 m) behind the normal one, **without** firing with you; `WingCommand` sends it straight after enemies attacking you (no fan-out split) |
| `WEAPONS_FREE` | yes | Roam near you and attack enemies it finds |

`state` is FOLLOW or ATTACK. `assign_*()` functions change the order (the player-facing part); `command_attack()` / `command_follow()` change only the state (used internally by Cover Me and Weapons Free).

`_decide()` is short and worth reading in full:
```gdscript
_track_leader(delta)                          # measure the slot's motion, set formation assist
if state == ATTACK and target_gone(target):   # target dead → follow; Attack order → standing order
    ...
if state == ATTACK:   return _attack_goal(target, _side())
if order == WEAPONS_FREE: return _free_goal(delta)
return _follow_goal()
```

**`target_gone(node)`** is true for freed nodes *and* for destroyer parts that are destroyed but still in the scene (they stay on the hull, charred). Its parameter is untyped on purpose: a typed parameter would error when passed a freed object.

#### Following the slot

`_follow_goal()` aims at a point `formation_lookahead` (30 m) ahead of the slot, and sets speed to the leader's speed plus `catch_up_gain` per metre behind. Joining is shaped so that nothing snaps:

- **Arrival from behind.** Catch-up speed is never more than the wingman can shed by the slot braking at `arrival_deceleration` (30 m/s², `_arrival_speed()`: v = √(2·a·d)). While it's behind, it heads for `_approach_point()`, a point `join_approach_offset` (12 m) outside the slot (sideways, or above for Slippy's centre slot) that closes in to the slot over the last `rejoin_behind_distance` (40 m). That way the approach never runs past the leader: a straight line to Slippy's slot, above and ahead of you, otherwise passes right by your ship.
- **Formation flight eases in.** Its pull towards the slot (`_slot_pull`, used by `_formation_velocity()`) is capped by the same braking curve. It can only build up or change at `slot_pull_rate` (45 m/s²), and while formation flight is off it's kept equal to the wingman's actual motion relative to the slot, so engaging it changes nothing at first. Formation flight also only fades in while the wingman's nose is within about 37–73° of the leader's heading (`ASSIST_MIN_ALIGNMENT` / `ASSIST_FULL_ALIGNMENT`), tilted by the slot's own climb or dive, so a wingman pitching up with its slot over a building still counts as facing the right way. That way it never drags a wingman around mid-turn. In formation the heading stays within about 20°.
- **Overshooting instead of a hard stop** (`_overshooting`). A wingman closing more than `overshoot_margin` (5 m/s) faster than a gentle arrival allows, and more than `assist_full_range` (25 m) from the slot, doesn't brake hard. It flies on in the slot's lane, changing speed at `arrival_deceleration`: past the slot, slowing to the leader's speed, then drifting back along the same braking curve. It hands over to formation flight once it's within 25 m and drifting back or holding. If it's at minimum speed and not drifting back (you're flying as slowly as it can), it hands over to the normal logic, which waits or somersaults back. The 25 m limit matters: holding formation in hard turns can briefly look like closing fast, and must not drop formation flight.
- **Far ahead: the somersault** (more than `rejoin_turn_distance`, 70 m, from the slot and over 20 m ahead, not while still overshooting at speed). It loops back behind its slot like a *Star Fox 64* U-turn, with formation flight off. The stages are `_stunt` (`Stunt` enum), driven by `_somersault_goal()`:
  1. `PULL_UP`: full stick back, slowing to `somersault_speed` (40 m/s) and pitching at `somersault_pitch_rate` (3 rad/s instead of 1.8), up and over until it's upside down heading back.
  2. `BACK`: flies back past you upside down, in a lane parallel to your flight line, one loop's height (2 × speed / pitch rate, about 27 m) above the point where the normal join starts (`_approach_point`, beside the slot), and at least `somersault_pass_clearance` (20 m) off your line. It speeds up for long trips and slows back to `somersault_speed` in time for the next stage. A wingman that was already facing away from your heading starts here: it turns round flat, then half-rolls onto its back on the way (as in a split-S).
  3. `PULL_THROUGH`: once the rest of the loop would bring it out `somersault_exit_behind` (20 m) behind the slot, allowing for how far you fly meanwhile, and it's most of the way up to its lane, it pulls through the second half and comes out upright, right where the normal join starts. If you're close enough, it goes straight from 1 into 3: one whole loop.
  4. `ROLL_OUT`: only as a fallback, if it somehow comes out upside down.

  Then it arrives as above. The loops cheat: they're tighter and quicker than the ship could normally fly, and while somersaulting it speeds up and slows down at `somersault_acceleration` (60 m/s²) or more. Both go through two `Fighter` hooks, `_get_pitch_rate()` and `_get_acceleration()`. Because the lane is above the formation and the pull-through comes down beside the slot, the wingman never needs a wide turn to stay clear of you.
- **Just ahead** (20–70 m): it flies parallel in the slot's lane and lets you catch up rather than U-turning, and formation flight pulls it in.
- **Behind the slot but facing away** (e.g. after an attack run): it turns round towards a point `rejoin_turn_out` (60 m) out on its slot's side, never across your path.

Measured (all three wingmen, same heading as you; formation holding through hard manoeuvres unchanged at 100%, worst slot error 2.1 m):

| Start | Before this work | Now |
|---|---|---|
| 60–300 m behind, normal speed | 1.2–3.7 s, final braking 114–133 m/s² | 1.7–4.5 s, final braking 45 m/s² |
| 150 m behind at 150 m/s | 1.7 s, braking 133 m/s² | 4.6 s, sails 29 m past, braking 30–46 m/s² |
| 40 m behind at 120 m/s | 0.6 s, braking 114–169 m/s² | 4.8 s, sails 58 m past, braking 34 m/s² |
| 80–300 m ahead | 5–14 s, or never at minimum speed, waiting at 20 m/s | 3.9–5.9 s (somersault), at cruise or minimum speed, facing your way or away, also on Corneria; closest pass to you 11.6 m |

Before the somersault, a gentle flat turn-back needed a wide loop to stay clear of you and took 9–12 s. The earlier quick turn-back (4–5.6 s) only worked because formation flight yanked the wingman round, and it passed 1.4–6 m from your ship.

If you're shooting something (`leader.fire_target`) within 15° of its nose and it's in formation, it aims at that instead.

#### Formation flight
Ordinary AI steering is too loose for close formation: when you turn hard, a wingman steering towards its slot lags, and you sweep through it. **Formation flight** is an assist that takes over near the slot:

- `_assist` (0..1) is how strongly it applies: full within 25 m of the slot, fading to 0 by 70 m, blended in and out over time so joining looks like a quick settle. It drops to 0 at once when the wingman gets an attack state or is on Weapons Free, and quickly while it is dodging an obstacle, pulling up from the ground or a building (`_ground_danger`), recovering from a scrape (unless tucked in behind you), somersaulting or overshooting (see Formation near the ground below).
- **Rotation** (`_update_rotation` override): after the normal stick-driven turn, the heading is slerped towards the follow goal with the leader's roll, and the leader's current spin is *anticipated* so the wingman turns with you instead of after you. Since that turn bypasses the stick, the override also measures how far the ship actually turned (`_turn_rates`) and the model banks with that, scaled to the leader's turn rates while in formation: before this, wingmen flew your turns perfectly level.
- **Velocity** (`_velocity_offset` override): the wingman moves with the slot's measured velocity plus a spring towards it (`slot_spring`), capped at `max_slot_correction`. This lets it slide sideways or brake a little, which a nose-forward flight model can't do on its own.
- `velocity_heading_blend` (0.5) points the nose partly along the direction of travel, hiding most of the sideways slide. Pitch has its own, `vertical_heading_blend` (1.0): the nose climbs and dives with the slot. Otherwise a wingman rising over a building or dropping back after it slides straight up or down with its nose level, as if hauled on strings.

`formation_flight = false` turns it off and the wingman flies like any other AI ship (useful for comparing).

#### Formation near the ground
On a planet, flying low would put the slots below you (Falco's and Krystal's are 1.5 m down) into the ground. `slot_position()` is the slot in the world, and on a planet mission it is raised to at least `formation_ground_clearance` (6 m) above the ground or water, both under the slot and `formation_ground_lookahead` (1 s) of your flight ahead of it, so the slot starts climbing before a rise. All formation code reads the slot through `slot_position()`. Near the slot (`_near_slot()`), a wingman also uses that 6 m clearance and the 1 s look-ahead for its own ground check instead of the AI's 25 m and 2 s. If that check still fires (`_ground_danger`), formation flight lets go so the climb isn't dragged back along the slot. In formation the check looks along the slot's path rather than the nose (`_ground_probe_direction()`), and never extrapolates the slot's descent: coming down after a building, the lift eases off above the rooftops, but a straight line along the dipping nose would run into them and break formation for nothing.

Why it's built this way (measured with you flying 15 m above the hills): with the normal 25 m / 2 s ground check, and formation flight letting go whenever it fired, wingmen held formation only 77% of the time on Form Up, because every rise you were about to climb over pulled them out. Shortening the check got formation back to 97% but they scraped the ground 1–3 times a minute, mostly where they had to climb a slope by themselves. Raising the slot ahead of rises gives 99% in formation and about 0.1 scrapes a minute. Remaining scrapes come when you yourself fly into the ground or bounce off it. Letting formation flight go on the short check (added with the building lift below) costs about a point over hills: 98.4% → 97.5% in formation in scripted hill passes, still with no scrapes.

**Buildings.** The ground lift uses `surface_height()`, which doesn't know about buildings, so flying low past Corneria City used to put slots inside towers: formation flight dragged wingmen into the walls while their ground check tried to climb. On top of the ground lift, the slot now gets a **structure lift** (`_structure_lift`, updated once a tick by `_update_structure_lift()`). Its target is `formation_ground_clearance` above the `clearance_height()` of every point the slot will pass over in the next `structure_lookahead` (4 s) on your current course, and `structure_side_margin` (8 m) to either side of that path (the wingman's nose wanders a little off it), less what the wingman can climb by then at `structure_climb_rate` (10 m/s). Only structures count (`_structure_excess()`): the ground slot rises over the land by itself, so a bare hill ahead needs no lift. So the target ramps up ahead of a tall building instead of jumping at its edge, and reaches full height `structure_ready_time` (2 s) early: the wingman's own ground check looks 1 s ahead, and the lift needs the rest to catch up.

**The lift moves like a climbing ship.** It heads for the target at `structure_lift_gain` (3 m/s per metre left), changing speed no faster than `structure_lift_accel` (25 m/s²), at most `structure_lift_rise_speed` (40 m/s) up and `structure_lift_fall_speed` (10 m/s) down, or `structure_lift_clear_fall_speed` (30 m/s) once nothing at all stands above the slot along the look-ahead (out of the city). It never comes down faster than it can brake by the height it is aiming for, so it lands softly on the slot rather than stopping dead. It holds its height `structure_lift_hold` (1.5 s) after the buildings ahead get lower before coming down, so it doesn't bob between neighbours. Climbs and descents therefore start and end in smooth curves. In effect, wingmen hop over the rooftops beside you when you fly between buildings, and settle back after. A whole 25 m cell counts as tall as its tallest structure, so a slot over a street next to a tower rises too. If you fly under an arch or down a street canyon, they go over it rather than through.

Measured with scripted low passes through the city (the leader 15–70 m up between buildings, each pass with at least one slot cutting through a building). The first version (the lift jumping at a fixed rate) took wingman passes with any scrape from 87 / 300 to 4 / 300, and scrapes from 852 to 17, but looked like wingmen yanked up and down by an invisible hand. Over 60 passes, starting each with the lift already settled as in real flight, it averaged 193–242 m/s² of vertical acceleration (95th percentile 107–123, peaks of 3,000: a velocity jump in a single frame), and formation flight dropped out 198–261 times per 20 passes. Two causes: the lift rose in bursts as each new building came into view (a staircase that formation flight copied), and the slot's path missed towers just beside it, which the wingman's own pull-up then caught: formation flight let go and the AI climbed steeply over the whole tower, overshooting by up to 100 m. With the smoothed lift, the 2 s ready time and the side margin: 13–15 m/s² (95th percentile 26), formation flight dropping out 5–9 times per 20 passes, 94–100% in formation, no scrapes. Over hills the wingmen stay as close to their slots as before (about 1 m), though they count as in formation (which also needs your heading within 20°) a few percent less, because they now ease into climbs earlier than a scripted leader that doesn't pitch.

Pitching with the climb (same 60 passes): the vertical gap between nose and flight path dropped from 7.6° to 2.3° on average (time over 10°: 47% → 1%). On its own, it raised formation-flight dropouts to 12–54 per 20 passes, all of them false ground alarms during descents; with the slot-path ground check, it's 1–4. The in-formation share reads a few percent lower (91–97%) because the 20° heading test counts the pitch. Hard turns in the asteroid field are unchanged (100% in formation, about 1 m off the slot).

**Tuck in.** Corneria City has towers of 100–240 m (a 343 m spire). Flying a street low, a slot beside you often lands in a tower's cell, and the lift alone would carry the wingman 100–200 m above you: on low street passes, wingmen spent about half the time more than 30 m above their slots. So when the slot would need lifting more than `tuck_lift_threshold` (25 m), the wingman **tucks in** behind you instead (`_tuck_amount`, `_update_tuck()`). Its slot slides over `tuck_slide_time` (1.5 s, eased) onto your own flight path, `tuck_spacing` (20 m) × (`wing_index` + 1) behind you (plus the Cover Me trail), so the wing trails in single file at 20, 40 and 60 m, behind the chase camera. Your path is recorded as you fly (`_trail`, a point every metre, the last 240; `_trail_point()` walks back along it). It is used rather than the map because the map stores one height per 25 m cell, about the width of a street, so even the cells along your path often read as tower-tall; the place you just flew through is known to be clear.

While tucked in and near the slot (`_on_trail()`: horizontally within 25 m, and not more than 25 m below it), the wingman trusts your path: it skips its own cell-based ground check (which down a street would keep pulling it up for nothing) and keeps formation flight through a graze against a wall (the scrape reaction would throw it across the street into the opposite building). Above the slot counts too, so a wingman still high from an earlier climb can drop straight down into the street. Tucked-in wingmen don't fire with you (they would be shooting through you), and formation flight's heading check follows your path's direction rather than your current heading. They stay tucked for `tuck_hold` (2 s) after the last tall building ahead, then slide back out once the lift (which falls quickly while unused) is below the threshold. `tuck_in` turns the behaviour off.

Measured with a scripted leader flying low down the city's streets (climbing only where a building physically blocks it), 4 × 6 passes, tuck off → on: time more than 30 m above the slot 48–58% → 0.1–0.9%, average distance from you 57–81 → 25–28 m. Weaving 45° each way through the city: 19–34% → 0.4–1.5%, 23–72 → 20–24 m, and scrapes 165 → 29 in total (most of the rest are grazes where the scripted leader skims a wall closer than a real ship could).

#### Formation fire
Wingmen only fire with you on **Form Up**, and only when `is_in_formation()`: within 10 m of the slot and pointing within 20° of your heading, and not tucked in behind you (`joins_leader_fire()`). That stops a wingman that's out of position from spraying shots across the formation. Covering wingmen never join in: Cover Me trades your wing's firepower for defence.

#### Shared targets
Two wingmen chasing the same fighter would settle into the same spot behind it and block each other. So a wingman gives way to any **senior** (lower `wing_index`) on the same target: it hangs back `pursuit_stagger` (30 m) per senior (`_pursuit_offset()`), and if it still ends up within `crowd_distance` of one for `crowd_time`, it peels off and comes back from another angle (`_check_crowding()`).

#### Weapons Free
`_free_goal()`:
1. Look for a target (`_pick_free_target()`): enemy fighters within `free_detect_range` of the wingman *and* `free_engage_radius` of you. Any untaken enemy beats any taken one (score = distance + 10000 × wingmen already on it).
2. If there's none: if farther than `free_leash` (325 m) from you, head back at `boost_speed` (your full throttle, 130 m/s, outruns the wingman's `max_speed` of 80; at `max_speed` they ended up about 1 km behind); otherwise fly to a roam point. Roam points are random spots within `free_roam_radius` (208 m), mostly ahead of you, stored *in your local space* so they move with you. `_steer_clear_of_leader()` keeps the route from passing through your ship (you're not an AI obstacle).
3. Once engaged, it never breaks off, however far the chase goes.
4. After shooting down an enemy fighter itself, it waits `free_kill_cooldown` (2–3.5 s, random) before looking for a new target, roaming meanwhile, so a wingman doesn't chain kills back to back. `notify_kill()` starts the cooldown; losing a target any other way (your kill, another wingman's, the enemy leaving) doesn't.

#### Camera fade
`_process()` measures how close the camera is to a box around the wingman, and fades its meshes (`GeometryInstance3D.transparency`) when the camera is about to pass through it. With Slippy's top-cover slot this rarely triggers now, but it still catches wingmen rejoining past the camera.

### 8.9 The order system (`WingCommand`)

**File:** [wing/wing_command.gd](../wing/wing_command.gd)

Owns **selection** (`selected`, `toggle_select`, `toggle_select_all`, `clear_selection`), **routing** (`recipients()`), **issuing** (`order_attack`, `order_cover_me`, `order_form_up`, `order_weapons_free` → `_issue`), **targeting** (`pick_target()`), **Cover Me assignment**, and the wingmen's **comms lines**.

**Cover Me** (`_update_cover()`, every physics tick) assigns threats to covering wingmen in two passes:
1. Wingmen already on a live threat keep it (one wingman per enemy).
2. The rest take a threat nobody's on. If there's none left, a wingman already sharing keeps its target, and an idle one doubles up on the nearest threat. A covering wingman with no threat returns to formation.

A "threat" is an enemy in CHASE (`threats()`), nearest to you first. Once on one, a wingman stays until the enemy dies or goes back to PATROL; evading or searching doesn't count as giving up.

**Comms lines.** Each character's `acknowledgements`, `celebrations`, `praise` and `celebration_chance` live in their `Pilot` file (`comms/speakers/falco.tres`...), so every character has its own voice, the same in every mission. `_acknowledge()` avoids repeating a wingman's last line. Destroyers are called out by Peppy (`MissionControl`, see [8.13](#813-comms)), not by the wingmen. **Kill celebrations** are in `Wingman.notify_kill()`: when a wingman's shot destroys an enemy fighter (rocks and destroyer parts don't count), it says a random line from its pilot's `celebrations` with `celebration_chance` (25%), never while on Form Up, at low priority. **Praise for your kills:** `Ship.notify_kill()` calls `WingCommand.praise_player_kill()` when your shot destroys an enemy fighter. A random wingman, with its pilot's `celebration_chance` (the same 25%), says one of its `praise` lines (Falco "Nice shot, Fox!", Slippy "Way to go, Fox!", Krystal "Nice flying, captain!"...), never the same line twice in a row, at low priority. Unlike their own celebrations this happens on any order, Form Up included. Measured: 24–26% of 2,000 simulated kills, spread over all three wingmen. A kill by a wingman's bolt fired alongside yours in formation counts as theirs, not yours.

### 8.10 The destroyer

**Files:** [enemies/destroyer.gd](../enemies/destroyer.gd), [destroyer_part.gd](../enemies/destroyer_part.gd), [destroyer_turret.gd](../enemies/destroyer_turret.gd), [destroyer_hangar.gd](../enemies/destroyer_hangar.gd), [obstacle_proxy.gd](../enemies/obstacle_proxy.gd), [effects/warp_portal.gd](../effects/warp_portal.gd) + [.gdshader](../effects/warp_portal.gdshader); scenes [juggernaut.tscn](../enemies/juggernaut.tscn) (the current destroyer) + [juggernaut_turret.tscn](../enemies/juggernaut_turret.tscn), and [destroyer.tscn](../enemies/destroyer.tscn) (the previous one); models [models/destroyer/](../models/destroyer/)

**Two destroyers.** Every mission spawns the **Juggernaut** ([juggernaut.tscn](../enemies/juggernaut.tscn)): `levels/level_base.tscn` sets the `EnemySpawner`'s `destroyer_scene` to it (the script default is still `destroyer.tscn`). The previous ship, `destroyer.tscn`, is kept unchanged: set `destroyer_scene` back to it to switch. Both run the same scripts (`Destroyer`, `DestroyerPart`, `DestroyerTurret`, `DestroyerHangar`), so everything below about the life cycle, warp, kill rule, turrets and hangars applies to both. The rest of this section describes `destroyer.tscn` in detail; the Juggernaut's differences follow.

**The Juggernaut.** A brutalist siege dreadnought, about 1,050 × 306 × 329 m (1.4× the old ship's length): a blunt stepped battering-ram prow, a long hull with a glowing green radiator trench down the spine, stepped armour bastions on the flanks, a stern castle carrying the bridge (an amber window band under a raked visor), and a 255 m armoured engine block with three engines in a shallow V. It was designed with Gemini (through the Antigravity CLI) from the brief in [models/SPACE_ASSETS.md](../models/SPACE_ASSETS.md) (Stage C) and is built by [juggernaut_c2.py](../models/destroyer/source/juggernaut_c2.py) in Blender (true metres, built at `SCALE` 1.5 of the approved design; detail in real metres; the turret unscaled), which exports `models/destroyer/juggernaut_*.glb`: hull, bridge, keel thruster, pod thruster (used for both side engines, mirrored), hangar door, turret, collision (not used) and markers (part pivots, launch points and turret mounts, which the scene's positions come from). Concept art and earlier rounds are in `models/destroyer/source/concepts/` and `juggernaut_preview/`. Its surface detail is still thin (hull about 11,400 triangles): see the to-do at the end of this section.
- **Parts** (same health and score as the old ship): bridge at (0, 204, 195), `radius` 50; keel thruster (0, 30, 502.5), `radius` 40; side thrusters (±93, 54, 502.5), `radius` 34, the right one's model mirrored; hangar doors at (±132, 36, 15), 114 × 51 m, sliding up `open_height` 54 m, with a glowing bay panel just behind each (`BayGlowL/R`) and launch points 6 m outside; 8 turrets, each on a pad half sunk into the surface under it: two on the bow glacis (±22.5, 112.7, −360), two on the forward sponson plates (±112.5, 121, −165), two on the main deck beside the radiator trench (±78, 115, −82.5) and two on the castle bastions (±63, 188.5, 195). The pads are `MOUNT_PADS` in the script, which both the hull and the turret markers read.
- **Turret** (`juggernaut_turret.tscn`): an armoured head with twin barrels in a front mantlet and a green sensor eye; same script and values as the old turret. Its three meshes are saved out of `juggernaut_turret.glb` by the import settings (`_subresources` in `juggernaut_turret.glb.import`, as `juggernaut_turret_base/yaw/pitch.res`), so the scene can arrange them as `Yaw` and `Yaw/Pitch` the way `DestroyerTurret` expects. Reimporting the glb refreshes them.
- **Collision from the model:** `hull_collision_from_model` (on) builds trimesh collision from the `Hull` model's triangles at load (`_build_hull_collision()`, shapes cached per mesh), so it matches the hand-made hull exactly. (The model's own 14 collision boxes covered only 68 % of the hull surface within 4 m.) Checked: 200 of 200 rays aimed into the hull from all round hit it or a part.
- **AI boxes:** the hull and bridge are covered by 15 `ObstacleBox` nodes, `Box1`…`Box15` under `AvoidanceBoxes` in [juggernaut.tscn](../enemies/juggernaut.tscn) (`margin` 10 m each, plus the AI's own 6 m `avoid_margin`); the thrusters keep their spheres, and `proxy_radius` 0 with no `extra_proxies` means no other spheres. `Destroyer` collects every `ObstacleBox` under it at load (for smashing asteroids); the boxes put themselves in `obstacles`. **Editing them:** open `juggernaut.tscn`: each box is drawn as a see-through cyan box in the editor (only there: `ObstacleBox` is a `@tool` script, and its preview is an internal child that isn't saved). Move or rotate a box with the gizmo, and resize it with its `size` or the scale gizmo (both count: the maths uses size × scale). Duplicate one to add a box, delete one to remove it. Keep every part of the hull inside some box (the AI can't see what's outside), and keep box faces close to the hull (a face far off it keeps the AI that much farther away, which made wingmen slow against the bridge with big spheres). Changes need measuring like any AI change (wingman attack times and hull scrapes). The first 15 were fitted to the exported model with a throwaway script: the hull and bridge, sampled every 3 m, are voxelised in 8 m cubes (a top-view column is solid between its lowest and highest surface point); boxes grow from the deepest uncovered voxel, a layer at a time in all six directions, while each new layer touches the hull and holds no empty voxel more than 25 m from it; boxes made redundant by later ones are dropped. Every surface point is inside a box, and no box face stands more than 25 m (plus up to one 8 m voxel) off the hull. Check them after a shape change. `hull_outline` (top view, widest point per 25 m band) is still needed: death blasts are scattered inside it, and it sets the bow and stern extents for the warp.
- **Warp and parking:** `portal_radius` 190 m, `portal_height` 95 m (the cross-section needs 175 m from that centre); `stop_distance` 375 m (200 + the 175 m longer bow), so it parks with its bow 560–600 m from the station's centre, as the old ship did (3 runs: through the portal at 12.0 s, active at 17.1 s, parked at 130 s; with the boxes, its bow parked 553 m from the station's centre). `death_blast_height` 150 m, `death_blast_size` 60–125 m, `final_blast_size` 290 m.
- **Measured** (headless, `main.tscn`): hangars launched 9 fighters per test, all clear of the hull within 4 s; turrets hit a stationary player above the deck within 0.8 s and downed it in 2.5 s (old ship: 1.3–1.7 s and 3.0 s); destroying the bridge and every thruster kills it. **Wingmen against it** (Attack order, all three on one part, from 4 seeded spots 700 m out round the ship and 0–250 m up; the same 4 for each setup; average of the 4, range in brackets): with the boxes, bridge 30.4 s (6.7–55.5), hangar 27.1 s (22.6–30.4), centre thruster 38.3 s (31.8–49.7), turret 22.6 s (7.3–40.2), 80 frames of hull scraping in all; with the 649 spheres it replaced, 42.3 s (6.8–84.7), 39.5 s (24.2–62.7), 35.5 s (31.1–39.4), 38.6 s (7.8–89.8) and 201 frames. A 15 m box `margin` was worse (bridge up to 108 s, more scraping). With big spheres (60 m cubes, 288 spheres) the wingmen had struggled badly (bridge not destroyed in 150 s).
- **Geometry rules** (after a review found floating turrets, detached pieces and flickering spots): every piece must touch or sink into the body (nothing may hover, not even by centimetres), and no two visible faces of different pieces may lie in the same plane (they flicker as the depth test flips between them). A piece that meets another face to face should sink into it or stand slightly proud of it instead (the script's comments give the offsets, typically 0.3–0.5 design units). The first model broke both rules in 29 + 68 places: the stern castle hovered 6 m over the deck, two turret pads 18 m over it and two hung off the bow's edge, the windows and posts above each hangar door hung in the air (the hull side slopes in there; a door-pocket wall now backs them), and the engine cowls, radiator arches, door ribs and bridge mullions shared face planes. They were found by a throwaway check run on `juggernaut.blend` in background Blender (loose parts not connected to the main body, with their gap; same-facing coplanar overlapping faces of different parts, skipping faces buried inside a third part); rerun one like it after changing the model.
- **Cost:** every AI ship checks every obstacle every frame (`AIPilot._avoid_obstacles()`), which is why the boxes replaced the spheres. In a busy fight round the ship (8 enemies, 3 wingmen on Weapons Free, 3 runs each, headless), physics took 7.5 ms per frame with no destroyer, 9.9 ms with the 649 spheres and 8.3 ms with the boxes. **To do:** add surface detail to the hull (painted plates, window rows, running lights).

**The model.** A broad armoured body splitting into two blade prongs (with an open gap between them and a glowing emitter at their root), a raised deck, a bridge tower with a flared neck under the bridge, an engine block with three thrusters, and hangar housings on both flanks. It's about 737 m long, 350 m wide and 278 m tall (built at `SCALE` 2.0 from the script's numbers; it was 552 m at 1.5, and the first version of this model was 368 m, itself 1.5× the old box-built wedge), dark gunmetal with crimson bands, amber windows and red-orange engines. Surface detail (`add_detail()` in the script) keeps the big flat surfaces from looking plain and gives the ship its scale: armour plates in three close greys with dark panel lines in the gaps on the deck, superstructure roof, prongs and aft hull (`plate_field()`, a staggered brick pattern); rows of lit amber windows along both hull tiers, the superstructure and the tower, plus bay lights under each hangar door (`window_row()`); red running lights on the prong tips, the hull's widest point, the engine block corners and the bridge antenna; and greebles: conduits with junction boxes down each prong, ribs across the deck trench, machinery on the superstructure roof, aft deck and engine block, and extra antennas, a dish and equipment pods on the bridge (which char with it). The **underside** (`add_underside()`, seen when you dive under the ship for the thrusters) steps down in two tiers: the keel and a narrower lower keel (`KEEL_LOWER`, solid, with its own collision piece). The sun is overhead, so the whole belly sits in the shadow band, where close greys all look the same; what reads there is shape and light: large plates (their edges get ink outlines) on the hull bottom, prongs and both keel tiers, a crimson spine down the lower keel lined with floodlights, a ventral bay with a glowing grating, window rows along both keel tiers, radiator fins under the aft hull, crimson sensor blisters at the keel's bow corners and red running lights on the keel corners. Apart from the lower keel it's all decoration: no collision, clear of the turret mounts (`TURRETS`), seeded (`random.Random(7)`, the underside its own `Random(11)` so editing one leaves the other unchanged) so a rebuild gives the same ship, and merged into one mesh per material (`Batch`) so it adds a handful of nodes, not hundreds. The hull is about 42,500 triangles (most of them plates, which are sized in real metres, so the 2.0 hull has more of them than the 1.5 one's 25,000; the Great Fox is about 230,000). It's our own design, built from code: [build_destroyer.py](../models/destroyer/source/build_destroyer.py) runs in Blender (Scripting tab, the Blender MCP, or `blender --background --python build_destroyer.py -- --export`) and exports four `.glb` files next to it:

| File | What | Pivot |
|---|---|---|
| `destroyer_hull.glb` | everything that isn't a part | ship origin |
| `destroyer_bridge.glb` | bridge block, windows, sensor domes, antenna | `BRIDGE_POS` (0, 75, 120) |
| `destroyer_thruster.glb` | one thruster (used three times), nozzle towards +Z | the nozzle centre |
| `destroyer_hangar_door.glb` | one door, stripes facing −X (the right door is turned 180°) | the door centre |

Everything in the script is in game coordinates (−Z is the bow) **before scaling**: `G()` multiplies by `SCALE` (2.0), so the game (and `destroyer.tscn`) has 2× every number in the script. Surface detail (windows, plates) is sized in real metres instead (divided by `SCALE`), so the bigger hull has more windows rather than bigger ones. Its colours are the **sRGB values the game ends up with**: the script converts them to the linear values Blender and glTF store. They're deliberately dark because the toon light is bright (the old hull's 0.46 grey rendered near-white). It also writes `collision.txt`, the hull's convex collision pieces, and `proxies.txt`, the `extra_proxies` line (AI avoidance spheres), both scaled and ready to paste into `destroyer.tscn`. **If you change the shape or `SCALE`, re-export, paste both, and update `hull_outline` and any part positions, radii and shape sizes in the scene.** `Destroyer._ready()` cel-shades the imported materials with `ToonMaterial`, like the Great Fox; the editor shows the originals.

**Structure.** The hull is the `AnimatableBody3D` root, on the World layer: it blocks shots, sight and ships, but can't be damaged. Its collision is nine convex pieces (body, both prongs, keel, lower keel, deck, superstructure, tower, neck) plus boxes for the engine block and hangar housings. Damage goes to **parts**, separate `StaticBody3D` children on the Enemy layer, each holding its model as a `Model` child:

| Part | Count | Health | Score | Notes |
|---|---|---|---|---|
| Bridge | 1 | 70 | 3 | Must die to kill the ship. `radius` 54 |
| Thruster | 3 | 46 | 2 | Must all die to kill the ship; each lost one slows it. `radius` 30 |
| Hangar door | 2 | 29 | 2 | Blown off → no more launches from that side. `radius` 30; slides up `open_height` 39 m |
| Turret | 8 | 12 | 1 | Disabled when destroyed. `radius` 6; gunmetal (not scaled with the hull: turrets are smaller relative to it) |
| The destroyer itself | | | +10 | |

Health didn't change with the scale-ups (1.5×, then 2.0×): bigger parts are just easier to hit, in the player's favour. `radius` (aim assist, wingman fire tolerance, HUD brackets) grew with them.

`Destroyer._ready()` finds every `DestroyerPart` below it and sorts them into `bridge`, `thrusters`, `turrets`, `hangars`. When any part emits `destroyed`, `_on_part_destroyed` checks the **kill rule**: bridge destroyed and no thrusters left → `_die()`, a chain of 14 explosions scattered over the hull (`_random_hull_point()`, inside `hull_outline`), a final blast, a fade-out, then `destroyed` and `queue_free()`.

A destroyed part stays in place, charred (`_char_meshes`), with its lights out and a dim ember light, and leaves the `targets` group. Parts ignore hits until `destroyer.is_damageable()` (out of the warp portal, or faded in, and not dying), and the Attack order can't pick them before then either (`DestroyerPart.attack_target` has a getter that asks the destroyer). Turrets and hangars wait for `is_vulnerable()` (active and not dying).

**Life cycle.**
1. `arrive(destination)`: face the centre, then, with `warp_in` (the default), **warp in** (below). With it off: tween visibility 0 → 1 over `fade_in_time` (4 s; every mesh's `transparency` and every light's energy), then `_activate()`.
2. Crawl towards the centre at `cruise_speed × (0.25 + 0.75 × fraction of thrusters intact)`, stopping `stop_distance` short (200 m in `destroyer.tscn`, the script default: in a level without a space station, the hull ends up spanning the middle of the zone, its bow about 175 m past the centre, so its thrusters sit well inside the boundary with room to get behind them; at 530 m the thrusters parked about 60 m from the old 1000 m boundary). Asteroids in its path are `shatter()`ed (no score). **With a space station in the level** (the Space Station mission has one at the centre), the spawner sends it instead to a point `destroyer_station_clearance` (300 m) outside the station's bounding sphere (427 m) on the side it came from, so it parks with its centre about 930 m from the station and its bow (375 m ahead of its centre) well clear. Measured over 30 arrivals: the closest any of its avoidance spheres came to the station's was 135 m.
3. Every `launch_interval` (40 s, first after 15 s), launch a squadron from the next intact hangar, within the fighter cap; if there's no room, retry in 5 s.

**Warp arrival** (*Warp in* exports; `_start_warp()`, `_warp_speed()`, `_update_warp()`, `_finish_warp()`). The spawner still places the destroyer on `zone_radius` in a random direction; `arrive()` then opens a portal `portal_margin` (50 m) further out along that direction and parks the ship just behind it, facing in. `zone_radius` usually matches the edge of the play area, so the portal opens just outside it; on the Space Station mission it is 3000 m, well inside the 4000 m boundary, so the destroyer doesn't spend minutes crawling in from the edge and you can watch the portal open from up close. The portal follows the level's `zone_radius`, so a bigger or smaller area needs no destroyer change.
1. **The portal opens** (`WarpPortal`, [effects/warp_portal.gd](../effects/warp_portal.gd)): a disc `portal_radius` (230 m) across the radius, its centre `portal_height` (30 m) above the ship's origin so the hull's cross-section fits. It bursts open over 1.5 s with a slight overshoot, a crimson light flash and a deep rumble (`explosion_medium.mp3` at pitch 0.3, through `SoundFX.play_at()` with a long reach so it's heard across the area; placeholder until there's a proper warp sound).
2. **After `warp_charge_time`** (1 s) the bow comes through at `warp_speed` (100 m/s).
3. **While it's coming through**, the part of the hull still behind the portal is hidden by a clip plane: `_use_clip_shader()` swaps the destroyer's toon materials for copies using `toon_clip.gdshader` at load, and `_set_clip()` sets each mesh's `clip_plane` instance uniform to the portal's plane. It works from any angle (including from behind the portal), and ink outlines follow because they're drawn from the depth buffer. Lights come on as they pass the plane. The hull and its parts have collision off (layers 0, restored later), so nothing collides with a half-visible ship, and nothing ever collides with the portal.
4. **Once the stern is out** (`_stern_extent()`, thrusters included; 8.9 s after the spawn): the portal shuts (1 s, with a quieter rumble) and frees itself, the clip plane goes, and the parts turn solid and **can be shot** (`is_damageable()`), a head start for the player.
5. **It brakes** to cruise speed over `warp_brake_time` (5 s, smoothstep), then `_finish_warp()`: the hull turns solid and `_activate()` starts turrets and hangars (13.9 s after the spawn; the first launch follows 15 s later). On the Space Station mission (2 runs at the 2.0 scale) its centre is then about 2,360 m from the centre of the field (warp-in at `zone_radius` 3000 m), with about 1,260 m between its thrusters and the 4000 m boundary. It crawls in at `cruise_speed` (10 m/s on `destroyer.tscn`, raised from the script's 8 when the area grew) and parks short of the station (step 2) about 158 s after the spawn, its centre 927 m from the field's centre and its bow 555–595 m from the station's. (With `zone_radius` 2000 m and 8 m/s it parked after about 70 s.)

If `stop_distance` were closer to the edge than the hull length plus its braking distance (about 1,100 m from the portal), it would reach it while still braking: still correct, just no slow approach. The HUD's "DESTROYER INBOUND" warning and Peppy's call-out start with the spawn, so they play as the portal opens. Calling `arrive()` again undoes an unfinished warp (`_end_warp()`); test scripts that move the destroyer set `warp_in = false` first.

**Turrets** pick the player if within `aggro_range` (450 m), else the nearest wingman in range (for show: wingmen can't be hurt). They turn at `turn_rate`, can only pitch from −5° to 80° (blind spots), need their barrels lined up within 3°, and need a clear line of fire past the hull and asteroids.

**Turret lock-on** makes flying slowly near the destroyer dangerous, so hanging back behind it to spray the bridge or engines (with three wingmen firing alongside) is high risk, high reward, while strafing runs at speed stay about as safe as before. Each turret keeps a `lock` (0..1) on its current target (reset when the target changes). While the target flies below `lock_speed` (50 m/s) the lock builds, at full rate (`lock_time`, 3 s from none to full) at or below `crawl_speed` (25 m/s) and proportionally slower in between; above `lock_speed` it breaks in `unlock_time` (1 s). The lock blends the fire interval, spread and turn rate from their normal values towards `locked_fire_interval` (0.15 s), `locked_spread_deg` (0.2°) and `locked_turn_rate` (3 rad/s), and bends the lead: `_lead_point()` adds `½·a·t²·lock`, with `a` the target's acceleration, estimated each frame from its velocity change and smoothed (`accel_tracking`), so circling doesn't dodge a locked turret. Measured by circling the player 150 m behind and above the engines at a fixed speed for 30 s (4 runs each): at 20 m/s about 2.2 hits/s (1.6–2.7), so full shields (13 hits) last about 6 s once a turret has locked on; at 35 m/s about 0.75; at 50 m/s and above none, as before lock-on (under 0.1 hits/s at every speed). Behind the engines, usually one or two turrets can see you. With the lock-on, the player's thruster heat is switched off (`thrusters_overheat`, see [8.2](#82-the-players-ship-ship)).

**Hangars** run their launch as a coroutine: door slides up (tween), fighters spawn at the launch marker one by one with `begin_launch()`, door closes.

**Obstacle proxies.** AI avoidance sees only spheres, so `_build_obstacle_proxies()` fills `hull_outline` (the hull seen from above, (x, z) points, set in `destroyer.tscn`) with a grid of `proxy_radius` (32 m) spheres every `proxy_spacing` (40 m across, 50 m along) at `proxy_height` (−4 m), keeping only the points inside the outline (scaled with the hull, so their number stayed the same). On top come `extra_proxies`, generated by the model script (`proxies.txt`): the bridge tower and superstructure, the hangar housings, and layers filling the raised deck and the keel (52 spheres; the hull grid only covers the main hull's height, and at 1.5× wingmen flew into the deck and keel on attack runs), plus one per thruster: 141 spheres in all. The gap between the prongs has no spheres. It's open for the player to fly through, but the avoidance margin (radius × 1.3 + 6 m) still makes the AI treat it as closed.

**Wingmen against it** (Attack orders, all three wingmen on one part, starting 700 m off the destroyer's side, 4 runs each; a different test from the one behind the earlier figures). All the figures below were written up while the hull was documented as 552 m or smaller; none have been re-measured at the 2.0 scale (737 m). At the 368 m size: turret (mid, right) 25–39 s with 12–21 hull scrapes, bridge 9.7–10.1 s with none, centre thruster 34–44 s with 14–39 scrapes. Scaled to 552 m with only the hull grid, turret runs got much worse (37–68 s, 55–70 scrapes). Now, with the deck and keel proxies and the structure attack changes in `AIPilot` (see [8.4](#84-the-ai-pilot-aipilot): mount-aware avoidance, clear-view runs and pull-outs): turret 16–88 s (median about 37) with 4–92 scrapes (median about 20), bridge 9.3–10.2 s with none, centre thruster 27–34 s with 10–17, hangar door (right) 17–25 s with none. **Turrets remain the weak spot**: wingmen often spend seconds without a clear view of one (the deck beside it blocks half the angles) and only fire on close passes, so kill times vary a lot. Rechecked after the lower keel was added (4 runs each): turret 16–30 s (4–49 scrapes), bridge 9.1–9.3 s (none), centre thruster 22–28 s (0–13), hangar door 17–19 s (0–3), all within or better than the ranges above (turret times swing too much for 4 runs to show a real change).

**`sync_to_physics` is off** because the destroyer moves itself outside the physics step in places (`arrive()`); with sync on, the physics server would overwrite those transforms.

### 8.11 Asteroids

**File:** [world/asteroid.gd](../world/asteroid.gd); the field is created in [main.gd](../main.gd)

`main.gd` scatters `asteroid_count` asteroids (640 within `field_radius` 3800 m, squashed vertically by `field_flatten` 0.25. History: the field was doubled from 160 within 900 m at 0.5 to 640 within 1800 m, keeping its density and thickness; 640 rocks add about 1 ms of physics time per frame in a busy fight, since every AI checks every obstacle. When the area grew to 4000 m the same 640 were spread to 3800 m rather than adding more, so the field is now about 9× sparser and twice as thick) with a **seeded** random generator (`field_seed`), so the field is the same every run. Sizes skew small (radius 3–28 m). Positions are kept out of the intro's flight lane and camera spot (`_blocks_intro`), because ships on autopilot don't dodge, and at least `station_clearance` (40 m) from the space station (8.11b). Adding the station changed the seeded layout from the first rejected rock on: still the same every run, just not the same as before.

Each asteroid builds its look on first use: 8 lumpy mesh variants made by pushing a low-poly sphere's vertices in and out with noise, shared by every asteroid (`static var _meshes`). Each instance picks one, scales and rotates it randomly, and spins only the visual (the collision sphere doesn't need to). Health is `1 + int(radius / 4)`. `shatter()` destroys it without awarding score. Asteroids set `highlight_on_crosshair` and `attack_target` to false: the crosshair doesn't turn red over them and the Attack order can't pick them (they still stop shots and can still be shot).

### 8.11b The space station (`SpaceStation`)

**Files:** [world/space_station.gd](../world/space_station.gd), [world/space_station.tscn](../world/space_station.tscn); model [models/space_station/](../models/space_station/)

A Cornerian wheel station at the centre of the Space Station mission (the `SpaceStation` node in `main.tscn`, at the origin, yawed 215° so its bow and lit hangar face the incoming formation at three-quarters). A spindle along its local Z (bow at -Z), a wheel about 800 m across joined to it by four spokes (the open quarters are wide enough to fly a formation through), docking arms and a hangar at the bow, solar wings and a comms dish at the stern. It's friendly scenery: solid, but not shootable.

**The model** is built from code like the destroyer: [build_space_station.py](../models/space_station/source/build_space_station.py) (game coordinates, sRGB colours, materials named `Station_*`) exports `space_station.glb` and writes `proxies.txt`. Each component is its own node modelled round its own pivot (`Core`, `Ring`, `Spoke0`–`Spoke3`, `Hangar`, `SolarL`, `SolarR`, `Dish`; pivots in the script's `PIVOTS`), so parts can later be made destructible.

**Surface detail.** The script's `add_ring_detail()`, `add_core_detail()` and `add_hangar_detail()` break up the large plain faces in the same spirit as the destroyer's `add_detail()`, each seeded on its own so changing detail never moves a window. All of it is solid, like the rest of the hull:
- **The wheel:** dark frames wrapped round it at the arc joints between the collars and the habitat modules (`FRAME_ANGLES`); a conduit, broken into runs with junction boxes, between the window rows on each side face; plates on the outside, one per lathe segment, in the two tones its arc isn't, between two more conduits; clusters of four radiator fins (`FIN_ANGLES`), one per 45°, which also break up its silhouette; a lit rail down the inside.
- **The spokes:** frames every 28 m (`SPOKE_RIBS`), with the transit-tube windows kept clear of them.
- **The spindle:** ribs down both of the hub's cones; two rows of cargo containers ahead of the hub (`CONTAINER_ROWS`, one in five or so blue) and six tanks behind it (`TANK_Z`). They stand out further than the spindle, so `FITTINGS` widens the AI spheres over them (three spheres grew: 39 → 48 and 53 m).
- **The hangar:** plates under it, machinery on its roof clear of the pylon.

Curved hulls are **smooth-shaded** (`SMOOTH_ANGLE` 30°: faces meeting at a shallower angle share normals, so box corners, chamfers and the spindle's steps stay hard). Flat-shaded, the wheel and spindle broke into a lighter or darker band per lathe segment.

The detail took the model from 14,810 to 20,286 faces (24,220 collision triangles). Measured at 1280 × 720 from four views (3 runs each, old model against new): no difference from 500–900 m away (1.8–1.9 ms GPU); from right beside the spindle 2.05–2.47 ms against 1.87–2.07 ms. Load time is unchanged.

**At load** (`_ready()`), `SpaceStation`:
- cel-shades the imported materials (`ToonMaterial.convert_tree`);
- builds one trimesh `ConcavePolygonShape3D` per component on a `StaticBody3D` on the World layer, leaving out the surfaces in `non_solid_materials` (windows and lights: thousands of tiny triangles). You crash into it with the usual crash rules (shield damage, deflection), bolts stop on it and it blocks line of sight. Thin parts hold: flying into a 0.8 m solar panel at 120 m/s bounces off;
- adds an `ObstacleProxy` per entry of `proxies` (158 spheres, pasted from `proxies.txt`): a chain round the wheel, rows down the spokes, one per 30 m slice of the spindle (each enclosing its slice: spheres the size of the spindle's radius let the AI clip the hub's rims), the docking clamps, hangar, dish and two rows over each solar wing. The middle of each quarter stays open.

**Keeping things out of it.** It joins the `station` group; `overlaps(point, radius, margin)` and `push_clear(point, margin)` test against its spheres, `bounding_radius()` (427 m) encloses them all. `main.gd` rejects asteroid positions within `station_clearance` (40 m) of it; `EnemySpawner` pushes wave spawn points clear of it and sends destroyers to a stop outside it (8.7, 8.10); enemy patrol points go through `_clear_of_obstacles()`, so they never land inside it.

**Measured** (headless scripts): no asteroid overlaps it; 0 of 305 wave fighters spawned inside it; 0 of 30 destroyers parked in or pathed through it. Flying the formation straight through the wheel on six lines (top and bottom quarters at 140–290 m from the axis, and off-axis lines past the solar wings), wingmen stayed within 2 m of their slots and never touched it. It costs physics time: in a dogfight around it, 4.7 ms per physics frame against 4.0 ms without it (4 runs each), mostly AI avoidance checking 158 more spheres.

**Known limitation: AI scrapes in a close dogfight.** With six to eight enemies chasing the player as they thread the wheel every 7 seconds (a worst case), AI ships touch the station in about 0.3–1% of their frames (6.6 per 1000 AI frames on average, 3.4–9.7 over 6 runs), mostly enemies on the hub and spokes while pursuing. They don't take damage (AI ships slide and recover, `AIPilot._think()`), so it shows as an occasional scrape. Making the spheres enclose the hub didn't change the rate, so it comes from how `AIPilot._avoid_obstacles()` steers (round the nearest sphere only, which in a cluster of overlapping spheres can push it into the next one), not from gaps in the coverage.

### 8.12 The HUD

**File:** [ui/hud.gd](../ui/hud.gd), scene [ui/hud.tscn](../ui/hud.tscn)

`hud.tscn` is a CanvasLayer with one full-screen `Control` running `hud.gd`. That script finds the ship, wing command and destroyer in `_process`, calls `queue_redraw()` every frame, and draws everything in `_draw()`:

| Element | Function | Where |
|---|---|---|
| Damage flash, "SHIELDS DOWN", "SHIP DESTROYED" | `_draw()` | full screen / centre |
| Smoothed crosshair (red over a target, not over asteroids) | `_draw_reticle` | centre |
| "RETURN TO THE COMBAT AREA" / "TURNING BACK" (planet missions, see [8.19](#819-planet-terrain-corneria)) | `_draw_boundary_warning` | top centre |
| Destroyer warning, part brackets, edge arrow | `_draw_destroyer` | |
| "Pilot senses": faint edge arrows for off-screen enemies within `sense_range` (150 m), fading with distance | `_draw_enemies`, `_draw_sense_arrow` | |
| Enemy brackets (one colour, whatever the AI state), only where useful: within `enemy_marker_radius` (320 px, set in `hud.tscn`; script default 180) of the crosshair, popping in and out at that edge with no fade (a combat-visor feel), and never while terrain, an asteroid or the destroyer hides the enemy from the camera, so brackets don't see through cover (`hide_hidden_enemies`; one World-layer ray per enemy from the camera each physics tick, `_update_hidden_enemies`). Clouds have no collision, so enemies in clouds keep their brackets. No arrows off screen, that's the radar's job | `_draw_enemies` | |
| Hit-direction arc: red, around the centre, on the side a shot came from | `_draw_hit_direction` | centre |
| Wingman markers: solid downward triangles in their colour, bold white initial (`WINGMAN_MARKER_SIZE` 36 × 29 px, letter `WINGMAN_INITIAL_SIZE` 15; the same whether selected or not). Drawn once per wingman into a texture by a one-shot `SubViewport` at the screen's real resolution (`_wingman_marker()`, redrawn after a window resize); each frame only places it | `_draw_wingmen` | |
| Diamonds on targets of Attack orders | `_draw_order_markers` | |
| Radar | `_draw_radar` | top left |
| Mouse steering cursor (hidden on gamepad) | `_draw_stick_cursor` | centre |
| Shield bar, thruster bar under it (empties as the thrusters heat), each with an icon on its left (shield, flame) in its colour | `_draw_gauges` | top right |
| Wing panel (per wingman, an icon for the current order above the call sign; on Form Up the icon fades slowly out and in while the wingman is still joining and won't fire with you yet: `joins_leader_fire()`, after `JOIN_BLINK_DELAY` 0.4 s so hard turns don't flicker it) | `_draw_wing_panel`, `_draw_wing_card`, `_draw_order_icon` | bottom right |

**Projecting world positions to the screen:** `cam.unproject_position(world_pos)` gives the pixel; check `cam.is_position_behind(world_pos)` first, because points behind the camera project to nonsense. Off-screen things get `_draw_edge_arrow()`, which works in camera space so even things behind you point the right way.

**The radar** (size `radar_radius`, 80 px; range `radar_range`, 500 m; both HUD exports) works in the ship's local space (`_ship.global_transform.affine_inverse() * position`), plotting x (right) and z (back) so ahead is up and it rolls with you. `_radar_height()` decides ▲ / ▼ / ■ with a 15° band (or 10 m up close). Wingmen in formation would land on your icon at 500 m scale, so they're pushed out to at least 9 px in their real direction. Enemies beyond `radar_range` are pinned to the rim in their direction as the same ▲ / ▼ / ■ icons, smaller and dimmer (`RADAR_FAR_SCALE` 0.65, `RADAR_FAR_ALPHA` 0.6; `_draw_radar_enemy()`), so a far-off wave can still be found and you can tell whether to climb or dive for it. **The destroyer** shows as a red silhouette of its own `hull_outline`, `RADAR_DESTROYER_LENGTH` (20 px) long whatever the range (to scale, the 736 m hull would cover most of the radar), turned to its heading relative to you (`_draw_radar_destroyer()`, drawn before the fighters so they stay on top); beyond `radar_range` it sits on the rim, smaller and dimmer like the fighters, and above or below you it gets a short line (`RADAR_DESTROYER_TICK` 6 px) like the wingmen. It shows from the moment it spawns, so it points to the warp portal while the "inbound" warning blinks. **Off-screen enemies get an edge arrow only when very close** ("pilot senses", `_draw_sense_arrow()`): within `sense_range` (150 m), at `sense_opacity` (0.85) inside `sense_full_range` (50 m), fading out to nothing at 150 m; `sense_arrow_length` 16 px; all HUD exports in the *Pilot senses* group. Arrows for every off-screen enemy made the radar pointless; these only flag the ones about to matter, and finding the rest is still the radar's job. In a 2-minute wave fight with the player weaving and not fighting back (3 runs), an average of 0.2–1.1 sense arrows were on screen (up to 3), against 2.7 for arrows on every off-screen enemy; it varies a lot with how closely enemies tail you. Edge arrows also remain for the destroyer and for targets of Attack orders, which are few and chosen.

**The hit-direction arc** (`_draw_hit_direction`): when an enemy shot hits you, the laser calls `Ship.notify_shot(origin)` before `take_hit()`, and the ship stores `last_shot_from` and sets `shot_flash` to 1, fading over `shot_flash_time` (0.8 s). The HUD draws a red arc around the screen centre (`HIT_MARKER_RADIUS`, `HIT_MARKER_SPREAD_DEG`, `HIT_MARKER_WIDTH`) on the side the shot came from, worked out in camera space: a shot from the right shows on the right, one from straight behind at the bottom. Crashes don't trigger it.

**Screen units.** The window stretches with `canvas_items` / `expand` from a base of 1152×648, so HUD coordinates are in that scaled space and the HUD looks the same at any resolution; the screen just gets wider on wider monitors.

### 8.13 Comms

**Files:** [comms/comms.gd](../comms/comms.gd), [comms/static.gdshader](../comms/static.gdshader), [comms/comms_speaker.gd](../comms/comms_speaker.gd), [comms/pilot.gd](../comms/pilot.gd), [comms/speakers/](../comms/speakers/)

**API:**
```gdscript
var comms := Comms.find(get_tree())       # null if the level has none (e.g. tests)
comms.say(speaker, "Text.")                                   # low priority, beeps
comms.say(speaker, "Text.", Comms.Priority.HIGH)              # interrupts low
comms.say(speaker, "Text.", Comms.Priority.LOW, preload("res://audio/line.ogg"))  # recorded
```
`say()` returns false if the line was dropped. `speaker` is a `CommsSpeaker`; every `Fighter` has a `speaker` export (Fox on `ship.tscn`, each wingman overridden in `levels/level_base.tscn`). **Characters** live in `comms/speakers/`, one file each. A `Pilot` (`comms/pilot.gd`) is a `CommsSpeaker` plus what a wingman needs: `accent_color` and the *Lines* group (`acknowledgements`, `celebrations`, `praise`, `celebration_chance`). An `Advisor` (`comms/advisor.gd`, Peppy) is a `CommsSpeaker` who doesn't fly, with destroyer lines; see Mission control below. To edit what Falco says, open `falco.tres`; to add a wingman character, create a new `Pilot` resource and set it as the wingman node's `speaker`.

**Life of a line:**
```
IDLE ──say()──▶ OPENING ──open──▶ TYPING ──last letter──▶ HOLDING ──hold + recording over──▶ CLOSING ──▶ IDLE
                (0.3 s, below)    (a letter every 1/40 s,  (1.5 s + 0.03 s per char)          (0.3 s,     or next
                                   pauses after . , ! ?)                                       reversed)   queued line
```

**Opening and closing.** One value, `_open_t`, runs from 0 (closed) to `expand_time + noise_time + unfold_time` (0.3 s), and `_apply_open()` lays the box out from it:

| `_open_t` | What you see |
|---|---|
| 0 → 0.09 s (`expand_time`) | the portrait square grows from a 2 px horizontal line (`line_height`) to full height |
| → 0.18 s (`noise_time`) | the square shows static |
| → 0.30 s (`unfold_time`) | the portrait and name appear as the text box unfolds to the right |

Typing starts only when the box is fully open, and a recorded line's audio starts with the typing. Closing runs `_open_t` back down, so it's the same steps in reverse, except that the portrait and name cut to static the moment the box starts folding back (opening shows them as it unfolds): the box folds away over the static, then the square collapses to a line and hides. The square and box animate their size (not `scale`, which would squash the borders) and clip their contents, so the text is cut off rather than squeezed while the box unfolds.

**Static** is a `ColorRect` with [comms/static.gdshader](../comms/static.gdshader): coarse blocks mixed with fine grain, re-rolled 30 times a second, thin scanlines and a rolling bright band, tinted towards the speaker's colour. Its clock is fed from `_process` instead of the shader's `TIME`, so it freezes while the game is paused. A speaker without a `portrait` shows faint static (`empty_portrait_static`, 30%) in its place.

**Priority rules:**
- Nothing on screen → the line plays (the box opens).
- A **LOW** line arriving while anything's on screen → dropped, except while the box is closing with nothing queued.
- A **HIGH** line arriving during a LOW line → interrupts it at once. From the **same speaker**, the new line simply starts typing. From a **different speaker** with the box open, the portrait shows static for `noise_time` (`SWITCHING`) while the box stays open, then the new line types. During opening, the line is just swapped in.
- A **HIGH** line arriving during a HIGH line → queued.
- **A queued line, or one arriving while the box closes,** turns the closing box around once it's folded back to static (`_open_t` at `expand_time`): the next speaker comes in through the static without the square collapsing.

**Details worth knowing:**
- The box is built in code (`_build()`): Panels with `StyleBoxFlat`s, a `TextureRect` for the portrait, a `ColorRect` for the static, Labels for name and text.
- The text label uses `VC_CHARS_AFTER_SHAPING`, so the whole line is laid out and wrapped up front and words don't jump to the next line mid-typing.
- **Beeps** are generated in code (`_make_beep()`): a 45 ms soft square wave built sample by sample into an `AudioStreamWAV`. They play on every `beep_every`-th letter at the speaker's `beep_pitch` (Falco lowest at 0.8, then Peppy 0.85, Fox 1.0, Slippy 1.15, Krystal highest at 1.35), skipping spaces and punctuation.
- **Recorded lines** play instead of beeps, and the line holds until the recording's length has passed. That's timed in code rather than read from the audio player, so a missing audio device can't freeze a line on screen.
- It's its own CanvasLayer (layer 5), so it shows during the intro while the HUD is hidden, and it pauses with the game.

**Portraits** go in each speaker's `portrait`: hand-drawn, 256×256 PNGs in [comms/portraits/](../comms/portraits/), one per character. The comms box draws them over a backdrop of the speaker's colour darkened by `portrait_backdrop_darken` (0.72), so art with a transparent background stands out, and samples mipmaps (`TEXTURE_FILTER_LINEAR_WITH_MIPMAPS`), so import portraits with mipmaps on.

**Mission control (Peppy).** Peppy doesn't fly: he advises from the Great Fox. He is an `Advisor` ([comms/advisor.gd](../comms/advisor.gd)), a `CommsSpeaker` with destroyer lines, in `comms/speakers/peppy.tres` (red). A `MissionControl` node ([comms/mission_control.gd](../comms/mission_control.gd), in `levels/level_base.tscn` so every mission has one, group `mission_control`) speaks for him. When the `EnemySpawner` brings in a destroyer it calls `announce_destroyer(destroyer)`: Peppy warns the team (`destroyer_warnings`), then says how to sink it, in full for the mission's first destroyer (`destroyer_hints`: bridge and all three engines) and as a short reminder after (`destroyer_reminders`). It then follows that destroyer's parts: the bridge falling while thrusters remain (`bridge_down`), one thruster left (`last_thruster`), all thrusters down while the bridge remains (`thrusters_down`), and the destroyer's `destroyed` signal (`destroyer_killed`, when the hull finally blows, about 5 s after the last part). Every line is HIGH priority, so it cuts off chatter and queues behind other HIGH lines: the hint always follows the warning. Each list avoids repeating its last line. The wingmen no longer call destroyers out.

### 8.14 Settings, input and menus

**Files:** [settings/settings.gd](../settings/settings.gd), [ui/settings_menu.gd](../ui/settings_menu.gd), [ui/title_screen.gd](../ui/title_screen.gd), [ui/pause_menu.gd](../ui/pause_menu.gd), [ui/scene_fader.gd](../ui/scene_fader.gd)

#### Input is defined in code, not the Input Map
The `Settings` autoload owns every gameplay action. `ACTIONS` lists them (id, display name, group for the controls screen). Each action has **three slots**: PRIMARY and ALTERNATE (keyboard or mouse) and GAMEPAD. `_default_bindings()` holds the defaults; `_apply_bindings()` writes them into Godot's InputMap, *replacing* any events an action already has. So **don't define gameplay actions in Project Settings → Input Map**; they'd be overwritten.

Keys are stored as **physical** keycodes (the key's position), so WASD-style bindings stay in the same place on AZERTY keyboards; `event_name()` shows the label printed on the player's own layout.

**Saving.** `user://settings.cfg` holds display settings and, per action, three short codes: `key:<code>`, `mouse:<button>`, `button:<joy button>`, `axis:<axis>:<±1>`. Actions missing from an older file keep their defaults, so adding an action never breaks existing saves.

**`bind()`** removes the same input from any other action, so one key never does two things, and reports what it took the key from.

**Menu buttons on a gamepad.** Godot's built-in `ui_accept` / `ui_cancel` have no gamepad buttons by default, so `_add_menu_gamepad_buttons()` adds A and B.

**Device tracking.** `Settings._input` sets `using_gamepad` from the last meaningful input (a pad button or a stick pushed past halfway → gamepad; a key, mouse click or a real mouse movement → keyboard/mouse), and emits `input_device_changed`. The HUD hides the mouse cursor and key hints on a gamepad.

#### Display
`set_fullscreen()` and `set_resolution()` apply and save. Windowed mode resizes and centres the window. Fullscreen fills the screen and renders the 3D view at the chosen resolution, scaled up (`scaling_3d_scale`), while the UI stays at native sharpness. The list offered is filtered to sizes that fit the screen.

#### The settings screen
Shared by the title screen and the pause menu (each instances `settings_menu.tscn` and listens for `closed`). The controls page builds one row per action in code. Rebinding: press a slot → it waits for the next input. In `_input`, it consumes everything while waiting (so menu navigation and pause don't react), Esc cancels, Backspace/Delete clears, sticks must be pushed past 60%, and it gives up after 6 s. Afterwards it ignores gamepad input for 0.35 s so a still-held stick doesn't move the focus.

#### Pause and scene changes
`PauseMenu` runs with `process_mode = ALWAYS`, toggles `get_tree().paused` on the `pause` action, and also pauses when the window loses focus. `SceneFader.change_scene(path)` fades to black, swaps the scene, waits two frames for the new one to appear, and fades in.

### 8.15 Visual style

**Files:** [effects/toon.gdshader](../effects/toon.gdshader), [player/ship_model.gd](../player/ship_model.gd), [effects/ink_outline.gdshader](../effects/ink_outline.gdshader) + [ink_outline.gd](../effects/ink_outline.gd), [effects/shield.gdshader](../effects/shield.gdshader) + [shield_effect.gd](../effects/shield_effect.gd), [world/space_sky.gdshader](../world/space_sky.gdshader), [world/space_environment.tres](../world/space_environment.tres), [world/space_dust.gd](../world/space_dust.gd), [effects/explosion.gd](../effects/explosion.gd) + [explosion_style.gd](../effects/explosion_style.gd) + [explosion_puff.gdshader](../effects/explosion_puff.gdshader) + presets in [effects/explosions/](../effects/explosions/), [effects/muzzle_flash.gd](../effects/muzzle_flash.gd)

**Font.** All text (menus, comms box, HUD) uses one fixed-width font, *Share Tech Mono* ([ui/fonts/](../ui/fonts/), SIL Open Font License: keep `OFL.txt` beside it). It is set once as the project font (`gui/theme/custom_font` in `project.godot`, Project Settings → GUI → Theme → Custom Font), so every `Label`, `Button` and dropdown picks it up without touching `menu_theme.tres`. The HUD draws its text in code, so it takes the same font with `get_theme_default_font()` in `_ready()`. The wingman initials and all the text in the wing panel (call signs, ALL, ORDERS TO, key hints) use a bold version made from it at runtime (a `FontVariation` with `variation_embolden`), since the font has only one weight. To change the font, drop a new `.ttf`/`.otf` into `ui/fonts/` and point that setting at it. Fixed-width letters are wider than the old default font's, so longer comms lines wrap onto the box's second line; everything else fits as it did.

**Cel shading** (`toon.gdshader`, light model in `toon_light.gdshaderinc`, shared with `terrain.gdshader`; `water.gdshader` has its own, see [8.19](#819-planet-terrain-corneria)). The surface itself (colour, texture, glow uniforms) lives in `toon_surface.gdshaderinc`, so `toon_clip.gdshader` can reuse it with a clip plane added (`#define TOON_CLIP`): the destroyer uses that while it comes out of its warp portal. It is a separate shader so the `discard` costs nothing on every other surface. `toon_unlined.gdshader` (`#define TOON_UNLINED`) is the same surface drawn in the transparent pass (`ALPHA *= 1.0`, `depth_draw_always`), so it gets no ink outlines: Corneria's foliage, given it by `ToonMaterial.convert_tree(root, unlined)` for the materials named in `unlined`. A custom `light()` function replaces smooth lighting with three hard bands. For each light, `N·L` (how directly the surface faces the light, times shadow attenuation) picks shadow, mid or lit tone, with a one-pixel anti-aliased edge (`band()`). On top: a thin rim of light on the lit side of the silhouette and a hard-edged glint. The shadow band has a minimum brightness (`shadow_tone`) **only for the sun**: applying it to omni lights (engine glows, explosions) would light up whole rectangular light clusters. Every lit surface uses this shader with its own `albedo`; glowing parts use `StandardMaterial3D` with emission instead. For imported textured models the shader also has an optional `albedo_texture` (multiplied with `albedo`) and a glow map (`emission` × `emission_texture` × `emission_energy`). Both default to no effect (white `albedo_texture`, black `emission`), so flat-colour materials are unchanged. `emission_texture` defaults to **white**, so a glow colour works without a texture (until October 2026 it defaulted to black, which silently zeroed every untextured glow: destroyer engines and windows, fighters' running lights, the station's windows). `ToonMaterial.convert_tree()` ([effects/toon_material.gd](../effects/toon_material.gd)) builds these from a model's PBR materials. It keeps colour, colour texture and glow, drops normal, metallic and roughness maps (fine bumps turn into speckles under hard bands), and leaves transparent materials alone. The Great Fox uses it ([8.19](#819-planet-terrain-corneria)); the Arwing still uses `ShipModel`'s flat-colour conversion.

**The ship model** (`player/ship_model.gd`, `ShipModel`). The player and wingmen fly an imported model, the *Arwing (Assault)* from Sketchfab in [models/arwing_assault/](../models/arwing_assault/), instanced as `Model/Arwing` in `ship.tscn`. Imported models come with ordinary PBR materials, which would look smooth and out of place, so the `ShipModel` script on the instance converts them when it loads. Every flat-colour material becomes a toon `ShaderMaterial` with the same colour, cached in a static dictionary so all four ships share one toon material per imported colour. Textured, emissive (the engine slot, the cannon lights) and transparent materials are kept as imported. **The pilot band.** `show_band` turns it on (currently **off**, to test how the ships read with only the overhead HUD markers; off, the fins and panels keep their plain colours like every other material). The materials in `band_materials` (`Material.002`, the blue fins, and `Material.004`, the panels set into them) instead get [arwing_band.gdshader](../player/arwing_band.gdshader): the toon shader plus a band in `accent_color` across every fin blade, yellow for Fox (the script default) and each wingman's colour via `set_accent()` from `Wingman._ready()`. The band is a shell `band_radius` (2.3 m) from `band_hub` (1.0, 0.3, -0.1), a point at the root of the right-hand fins in the ship's Model space, mirrored for the left; the upper and lower blades both radiate from there and their tips are about 3.3 m away, so the shell crosses all four at the same fraction of their length. It is `band_width` (0.4 m) wide with a `pinstripe_width` (0.06 m) `pinstripe_color` (white) stripe along each edge, which keeps Falco's blue band readable on the blue fins. Each mesh gets its own band material (each ship has its own colour, and each mesh its own `to_ship` transform from its vertices to Model space, set once since the parts don't move). It replaced painting the fin panels alone, which were small and half hidden behind the fins from the angles wingmen are usually seen at. The model is about 230,000 triangles, much denser than anything else in the game; the importer generates LODs, so distant ships draw fewer.

**Ink outlines** (`ink_outline.gdshader`). A screen-covering quad, attached to the camera, reads the depth and normal buffers. For each pixel it compares its four neighbours:
- a big jump in depth, on the nearer side → a silhouette line;
- similar depth but a sharply different normal → a crease line.

Lines fade out between 220 and 520 m so distant ships don't become black specks. **Only opaque geometry gets outlines**, because transparent materials don't write depth. That's used deliberately: space dust is made transparent so it isn't outlined, explosion puffs, clouds, water and Corneria's trees write `ALPHA` to stay solid-looking without lines, and fading objects (destroyer arriving, wingman near the camera) lose their outlines while transparent.

**Engine glow.** `Fighter._update_engine_glow()` does for the engine glow what the engine sound does for pitch (see [8.17](#817-sound)). The strength is 1.0 at cruise speed, plus `engine_glow_per_speed` (0.015) per m/s above or below it, clamped to `engine_glow_range` (0.5–2.3). Your ship overrides both in `ship.tscn` (0.0075 per m/s, 0.7–1.5) for a subtler range, and `wingman.tscn` sets the defaults back so wingmen are unchanged. It multiplies the `Model/Glow` mesh's size and emission energy and the `Model/EngineLight`'s energy. For your ship (cruise 60 m/s) that's 0.7 at minimum speed and 1.5 at full throttle. Size matters more than brightness: bloom washes any bright glow out to white, and from the chase camera you see the glow end-on, so a brighter or longer glow alone barely shows. Each ship gets its own copy of the glow material in `Fighter._ready()`, since the scene's material is shared. Ships without those nodes (enemy fighters) are skipped.

**Shield bubble.** An additive, unshaded sphere shader: a bright spot where the shot landed, a ripple spreading from it, or the whole bubble lit (`coverage = 1`) for collapse and reboot. `ShieldEffect` animates the uniforms.

**Sky.** A procedural sky shader: hashed noise for stars, layered value noise for faint nebulae, and a glow around the sun direction. The `Environment` resource adds ambient light, filmic tonemapping and glow (which makes emissive bolts, engines and explosions bloom).

**Corneria in the sky** (the shader's *Planet* uniforms; off by default). The Space Station mission uses its own copy of the environment, [world/asteroid_field_environment.tres](../world/asteroid_field_environment.tres) (set on `WorldEnvironment` in `main.tscn`), with `planet_enabled` on; the title screen and the shared `space_environment.tres` keep the plain sky. Because it's part of the sky, the planet is infinitely far away: it never gets closer, never clips against the camera's far plane and has no geometry. Each sky pixel within `planet_angular_radius` (22° on the Space Station mission; shader default 17°) of `planet_direction` (low on the left at the intro's handover, beside the station) is cast against a sphere to get a surface normal, then:
- **Surface:** continents from domain-warped 6-octave noise above a sea level set by `land_amount`; shallow water near the coasts, ice caps beyond `ice_latitude`, crisp cloud bands (`cloud_amount`). The land is split into biomes by a moisture noise (`biome_scale`, wetter near coasts, drier with `dryness`) and by temperature (cooler towards the poles and with height): forest (`land_forest`), grassland (`land_low`), dry plains (`land_dry`), desert (`land_desert`), tundra (`land_tundra`), with highlands (`land_high`) on top. Mountain ranges are ridged noise (`ridged()`) inside broad belts and away from the coast (`mountain_amount`), bare rock (`rock_color`) with snow above `snow_line`; city lights avoid them. A fine noise mottles the ground (`land_detail`). **Relief:** the land's height (highlands plus mountains) tilts the normal through screen-space derivatives (`dFdx`/`dFdy`, no extra noise samples), so slopes facing the sun are brighter and the far sides darker (`relief_strength`); clouds don't take that shading. `planet_axis`, `planet_spin` and `planet_seed` change which face and which continents you see (the Space Station mission uses seed 4). The noise hashes its grid corners with an integer hash (`corner_hash()`); the float `hash13()` it used before cut a straight seam through a cloud, and is now only used once per cell (stars, city lights), where it can't seam.
- **Light:** from the scene's first `DirectionalLight3D`, like the sun glow: a narrow day/night line, a dark night side (`night_brightness`: 0.025 by default, 0.004 on the Space Station mission, where 0.025 left land and clouds visibly grey at night: it's a fraction in linear light, so small values still show) with city lights on land; on the sunlit side, `day_brightness` and `day_saturation` (1 = unchanged; 2.5 and 0.6 on the Space Station mission: brighter and noticeably less saturated); a small sun glint on open water, a blue rim thickening towards the edge, and an atmosphere glow `atmosphere_width` beyond the edge on the sun's side.
- **Cost:** it doesn't animate (no `TIME`), so Godot keeps the sky's reflection map from being redrawn every frame. Drawing the background with the planet filling much of a 1080p screen took 2.01 ms of GPU time per frame against 1.86 ms with it off (3 runs each). The biomes, mountains and relief added about 0.08 ms more (2.43 → 2.51 ms in a later setup, against 1.69 ms with the planet off; 3 runs each).

To move it, change `planet_direction` (and the size with `planet_angular_radius`) on the environment's sky material. It's lit from the sun's direction, so how much of it is in daylight depends on where it sits relative to the sun.

**Space dust.** 280 tiny specks (`count`; was 350) in a box that wraps around the camera (`fposmod`), stretched along the ship's velocity. They're what makes speed visible in empty space.

**Surface hits** ([effects/surface_hit.tscn](../effects/surface_hit.tscn), the `HitBurst` script below with other settings). A bolt hitting something that can't be shot (the ground, buildings, hulls) throws up a smaller, rounder version of the hit burst, so a miss never reads as a hit: a 1.3 m pop (6 short spikes, `star_valley` 0.72) coloured from the bolt's `impact_color` (`tint_from_bolt`: white core, the colour lightened for the middle band, the colour itself for the rim; green for your bolts, red for the enemies'; its minimum on-screen size grows it at most `star_max_grow` 1.5 times, so it shrinks with distance past about 140 m), 6 sparks in the same colours glancing off the surface (along the bolt's reflection leaned towards the surface normal, in a 50° cone), and 4 pale dust puffs (`dust_count`, `dust_color`; the explosions' puff shader born cold, through `Explosion.trail()`'s settings) that swell to 3 m and fade over 0.7 s. The star draws at `render_priority` 1, after the dust, so the puffs never cover it. Materials are cached per scene and bolt colour. `Laser.surface_hit` (null = nothing) and `surface_hit_size` pick it per bolt type. It replaced the old glowing sphere and light (`Impact`); measured at 1280 × 720 with 30 hits a second on the ground in view (rendered, 2 runs each), the cost was within run-to-run noise (GPU 2.2–2.6 ms either way). Hits on water splash instead (below).

**Hit bursts** ([effects/hit_burst.gd](../effects/hit_burst.gd), settings on [hit_burst.tscn](../effects/hit_burst.tscn), shader [hit_burst.gdshader](../effects/hit_burst.gdshader)). A bolt hitting anything with `take_hit` (enemies, destroyer parts, asteroids, wrecks, your shields) throws up a cartoon star burst and a spray of sparks (`Laser.hit_burst`, null = the surface hit there too; `burst_size`). The star is a quad the shader turns to face the camera and cuts into a spiky star (8 spikes of varied length) in flat bands, a pale core, yellow and an orange rim, with no ink outlines (it's in the transparent pass). Over its 0.2 s it pops out to full size, then hollows from the middle and is gone, stepping through 5 poses rather than moving smoothly, like drawn animation. It's pulled towards the camera by its radius so the hull it hit doesn't hide it, and never drawn smaller than `star_min_angle` (0.014 radians of view), so a hit on a fighter 400 m off still shows; but that floor never makes it more than `star_max_grow` (2.5) times its real size, so beyond about 390 m it shrinks with distance again (without the cap, every distant hit was drawn as the same big blob: a miss 1 km off was 28 m across). `brightness` is just over 1: more and the bloom washes the bands out to a white blob. Eight flat-coloured sparks (thin rods along their flight) fly back out towards the shooter in a 65° cone. Per-burst values (`age`, `seed`) are instance uniforms, so every burst of a scene (and bolt colour) shares one material. `Level.prewarm_hit_bursts` builds one of each burst scene at load (drawn at the end of its life, when every pixel is discarded, so it never shows).

**Hit reactions** ([effects/hit_reaction.gd](../effects/hit_reaction.gd), `HitReaction`). What a target that's been hit but not destroyed shows. `EnemyFighter` and `DestroyerPart` make one in `_ready()` with `HitReaction.attach(target, flash_root, flinch_node, radius, anchored)` and call `hit(at, health_left)` from `take_hit()`; a scene can add its own `HitReaction` child to override the values.
- **Red flash:** every toon surface under `flash_root` glows `flash_color` and fades over `flash_time` (0.12 s). It's the `hit_flash` instance uniform in `toon_surface.gdshaderinc` (on every toon material, zero by default), set per mesh, so it works with shared materials and on the destroyer's clip shader too. It replaces both colour and glow, so it reads on the shadow side.
- **Flinch** (fighters only: the `Model` node): knocked `flinch_distance` (0.8 m) away from the hit and twisted `flinch_angle` (6°), easing back over `flinch_time` (0.25 s). Only the model moves; collision and hurtbox stay put. Before a dying fighter's model goes to its wreck, `release()` puts it back as it was.
- **Damage smoke:** with `smoke_below` (70 %) of its health left or less it trails smoke, with `fire_below` (40 %) or less fire too, so a light fighter (3 hits) smokes after the first hit and burns after the second; an elite (4 hits) after its second and third. Both are `Explosion.trail()` (the wreck's puff trail, moved there and shared): smoke born cold, fire short-lived and burning most of its life. They come out of the target's fixed smoke point if it has one (`attach()`'s `smoke_from`; fighters pass their `Model/SmokePoint` marker, at the engine, so the trail streams from the tail), puffing along its +Y; otherwise out of the spot the first damaging hit landed (kept in the target's space as it moves and turns), outward from its middle. Puffs grow to `puff_size_per_radius` (1.4) × the target's radius, at most `max_puff_size` (36 m). A flying fighter spreads them every way (`smoke_spread` 180°), which its speed draws out into a trail. **Anchored** targets (destroyer parts) can't trail, so theirs pour straight out of the hull in a narrow, faster, longer-lived plume (`anchored_spread` 30°, `anchored_drift`, `anchored_lifetime_scale`); from their centre or in every direction the hull hid it. A destroyed part keeps burning. The emitters are in the scene, not under the target: they follow it, and stop and fade when it's freed (a fighter's wreck then takes over with its own plume).

Measured at 1280 × 720 (rendered, 2 runs): a destroyer with all 14 parts smoking or burning in view costs 0.3 to 0.8 ms more GPU time per frame than intact (2.25 → 2.6–3.05 ms).

**Water splashes** ([effects/water_splash.gd](../effects/water_splash.gd), settings on [water_splash.tscn](../effects/water_splash.tscn); shader [water_splash.gdshader](../effects/water_splash.gdshader)). A bolt that hits water throws up a splash instead of the surface hit: `Laser._cast()` asks `Terrain.is_water_surface()` whether the hit point lies on the water (the sea and the ground share one World-layer body, so it goes by height: within 0.5 m of `water_level_at()`, which is the water's surface wherever the ground is below it, raised lakes and rivers included). The splash is two shapes drawn by a shader, not particles: an open unit cylinder each, which the vertex shader bends, per frame, into a **jet** (11 m tall at its peak, rising over the first 40% of the 1.1 s life and falling back, its top flaring and cut into 6 spikes) and a short wide **crown** round its foot (4.5 m, 11 spikes, opening out). Late in the life, noise holes eat them away from the top. They're toon-lit white and solid, one cartoon shape each, with no ink outlines: like the water they're drawn in the transparent pass (`ALPHA *= 1.0` and `depth_draw_always`, as the clouds). Per-splash values (`age` 0 to 1, `seed`, `size`) are instance uniforms set by the script, so every splash shares two materials. Because the shapes reach far outside the unit cylinder, each mesh gets a `custom_aabb`, or it would be culled at the screen's edge. The **foam ring** is drawn by the water shader itself (see the water wake below): `WaterMarks.add_ring()`. `Laser.water_splash` (null = the surface hit on water too) and `splash_size` (scales the shapes and ring, not the timing) pick it per bolt type; enemy and turret bolts splash too. `Level.prewarm_splash` builds one microscopic splash at load on missions with a terrain, like the explosion prewarm. Measured at 1280 × 720 (rendered, 2 runs each): 22 splashes a second (both guns held on the water) cost about 0.2 ms of GPU time per frame.

**Water wake** ([effects/water_wake.gd](../effects/water_wake.gd), a `WaterWake` node on `ship.tscn`, so wingmen have it too). Skimming low over water splits it. Its strength is `1 - smoothstep(full_height 3 m, start_height 12 m, height over the water)` times speed / `full_speed` (90 m/s), so 0.67 at cruise speed down low and more when boosting; nothing over land or without a `terrain` (space). Two parts:
- **On the water**, drawn per pixel by `water.gdshader` (its `marks` uniforms): a V of foam lines starting `wake_start` (1.5 m) either side of the track and spreading `wake_spread` (12 m/s) and fading over `wake_life` (3.5 s), with churned foam down the middle for `churn_life` (1.6 s). Noise at each spot makes the bands uneven (clean, even-width lines looked drawn on): the arms wander in and out more as they age (`noise2` at 9 m), swell and thin along their length, have ragged edges with flecks, and break into patches from the start (most of all in the first 0.3 s, so they fray in behind the ship rather than starting on a straight edge), more as they fade; the churn breaks up the same way instead of tapering to a thin straight line. The shader is fed by **`WaterMarks`** ([world/water_marks.gd](../world/water_marks.gd), group `water_marks`), which `Terrain` adds when it has a water material (the sea's, shared with the map's lakes and rivers). Each wake calls `track(ship, position, strength)` every physics frame; WaterMarks keeps a point every `wake_spacing` (10 m) per trail, up to 24 per trail and 8 trails, plus the ship's current spot, and every frame hands the shader the points (`wake[192]`: x, z, time, strength; a negative strength starts a new trail), the splash rings (`rings[32]`) and a box round each set, so water outside it skips the loops. Its own clock (`marks_time`) pauses with the game. A ship that leaves the water ends its trail, and coming back starts a new one, so the old wake fades out on its own. The arms are drawn only beside a segment of the trail, not round its ends (there the distance is to a point, and every trail point got a foam circle). Inside the loops the shader blurs edges by the pixel size passed in (`px_step()`), not `fwidth()`, which is undefined where neighbouring pixels skip differently.
- **Spray**: two sheets thrown up beside the ship ([effects/water_spray.gdshader](../effects/water_spray.gdshader) on a subdivided unit plane each, moving with the ship: the node is `top_level`, on the water under the ship, turned to its heading). The vertex shader shapes each into a curtain whose foot runs back and out from `spray_offset` (3 m, beside the wingtips), starting `spray_ahead` (3 m) ahead of the ship, and whose ragged top arcs up to `spray_height` (4.5 m, times strength) and back down over `spray_length` (8 m); blobs of noise stream back along it at `churn_speed` (30 m/s), cutting a lumpy top and holes. The foot wobbles in and out (`foot_wobble`, 0.9 m) and frays into gaps above the water (`foot_fray`, 30% of the height): a straight foot drew a hard seam along the water from the chase camera, right where the foam bands begin. Normals turn from facing out at the foot to facing up at the top, so the cel bands shade it. Why beside and ahead: from the chase camera, the water behind the ship is out of sight below it, so the V on the water mostly shows from above and the spray has to rise beside the ship to be seen at all. (Puff particles came first: left on the water, as spray really is, they were behind the camera within a fraction of a second.)

Measured at 1280 × 720 (rendered, 2 runs each) with the player and wingmen skimming at 4 m (four trails) and 22 splashes a second: about 0.5 ms more GPU time per frame than flying at 30 m without firing (2.55 vs 3.05–3.12 ms). The uneven bands cost most of that: their noise is worked out for every pixel near a wake.

**Explosions** ([effects/explosion.gd](../effects/explosion.gd)). `Explosion.spawn(parent, position, style, size, velocity)` sets off a cel-shaded explosion; `size` is the fireball's radius in metres, and an `ExplosionStyle` resource ([explosion_style.gd](../effects/explosion_style.gd)) says what it looks like, in units of that size so one style fits small and big blasts. Layers, in order: a white-hot **flash** (an additive billboard, 0.12 s), a **fireball** of puffs, lingering **smoke** puffs that appear after `smoke_delay` (0.45 s; at once they hid the fire), **sparks** (glowing rods stretched along their flight, `particle_flag_align_y`), tumbling **debris** (hull plates, or faceted rocks with `debris_rocks`), an optional **shockwave** ring (additive, racing out in a slightly tilted plane) and a burst of **light**. The puffs ([explosion_puff.gdshader](../effects/explosion_puff.gdshader)) are camera-facing quads drawn as balls: fire in hard bands (white-hot core, orange, deep red rim) that cools from the rim inwards over `cool_at` of its life into smoke, lit by the toon light model (the puff's `NORMAL` is a sphere's), then breaks up into growing holes from `dissolve_from` and is gone. They write `ALPHA` (in the transparent pass, with `depth_draw_always` so puffs sort and occlude properly), leaving ink outlines off the fire and smoke. The age comes from the particle system (`INSTANCE_CUSTOM.y`). The whole explosion is built in its node's space and the node is scaled by `size` (the particles use `local_coords`), so each style's materials, meshes and particle settings are built once and shared (`_assets()`); the light's range is set in metres. It drifts on with `inherit_velocity` of the exploding object's velocity, slowing by `drag`, and frees itself after `duration()`.

**Presets** (effects/explosions/): `fighter.tres` (enemy fighters, the player at 6 m, wreck second explosions), `asteroid.tres` (brown dust, rock chunks, little fire; sized `radius × Asteroid.explosion_scale`, 1.4, so the dust cloud at its biggest is about as wide as the rock: `size` is the nominal fireball radius, and the puffs drift and swell past it, so 0.6 gave a cloud under half the rock's width), `destroyer_part.tres` (with shockwave), `destroyer_chain.tres` (the 14 blasts along a dying destroyer), `destroyer_final.tres` (its last blast: 16 puffs, 5 s smoke, a near-level shockwave). Each user has its own export (`Fighter.explosion`, `Asteroid.explosion`, `DestroyerPart.explosion`, `Destroyer.death_blast_style` / `final_blast_style`, `Wreck.explosion`). **Prewarm:** the first explosion of a style used to stutter (one ~20 ms frame while its materials and pipelines were built), so `Level` sets off a microscopic one of each style in `prewarm_explosions` in front of the camera as the mission loads (`Explosion.prewarm()`). Measured at 1280 × 720 (rendered, 2 runs each): GPU time is unchanged against the old sphere (about 2.05 ms with 6 fighter kills a second or two destroyer deaths in view), CPU about +0.1 ms, and with the prewarm the first explosion frame is as fast as any other (7 ms vs 20 ms without).

**Wrecks** ([effects/wreck.gd](../effects/wreck.gd), [wreck.tscn](../effects/wreck.tscn)). A destroyed enemy fighter doesn't just vanish: `EnemyFighter.take_hit()` still does the first explosion, scores, emits `destroyed` and frees the fighter at once (so wave tracking, the radar, targeting and the AI see it gone as before), but first hands its `Model` and `Hurtbox` nodes to a `Wreck` (`Wreck.spawn()`, through the fighter's `wreck_scene` export; empty = no wreck). The wreck keeps the fighter's velocity, continuously aligns its nose with its velocity vector so falling under gravity looks natural, rolls out of control about its nose-to-tail axis only (`roll_rate`, a random 1.5–3.5 rad/s either way; it used to tumble on every axis, which looked wrong for a ship), goes dark (engine glow hidden, the `Fighter_Lights` material swapped for a dead grey) and trails a plume: GPU particles in world space (`smoke_rate` 26 a second), drawn with the explosions' puff shader in `smoke_style`'s colours (the fighter explosion preset), so the trail matches the blasts at either end: each puff burns as banded fire for the first `smoke_burn` (12 %) of its life, so only the stretch right behind the wreck is on fire, then cools into toon-lit smoke (no ink outlines) that swells from `smoke_start_size` 3 m to `smoke_end_size` 11 m and breaks up from `smoke_dissolve_from` (40 %) of its `smoke_puff_lifetime` (2.5 s). On planet missions (a `terrain` group exists) it also falls under `planet_gravity` (15 m/s²). Each physics frame it casts a ray along its own movement against World, Friendly and Enemy (`crash_mask`); when that hits something, when a friendly bolt hits it, or after `lifetime` (3 s), it explodes a second time (an `Explosion`, `explosion` style at `explosion_size` 6 m, plus the fighter's explosion sound, slightly lower) and is freed at once; the plume is a separate node that follows it and fades out on its own. **Debris:** that second explosion also throws out `debris_count` (3–5) smoking pieces ([wreck_debris.gd](../effects/wreck_debris.gd), `WreckDebris`): small dark toon chunks flying off at the wreck's velocity plus `debris_speed` (18–35 m/s) outward, slowing with `debris_drag`, tumbling, falling on planets and stopping at the World layer. Each trails a thinner, shorter version of the wreck's plume (the same `_make_smoke()`, `debris_smoke_*`: 30 puffs a second, 0.8 → 3.5 m, 1.2 s), burning right behind the piece, and burns out (shrinks away over its last 0.35 s) after `debris_lifetime` (1–2 s); its trail stops and fades. Purely visual: no collision body, no groups, can't be shot. Measured (headless, 4 wrecks): 17 pieces, all gone within 2 s and every particle node freed afterwards. **Shooting it:** it keeps the fighter's hurtbox (retargeted to the wreck), so your bolts and your wingmen's hit it exactly as they hit the live fighter, and any damage sets off the second explosion (`take_hit()`; no extra score, and `notify_kill()` ignores it, so no comms lines). Enemy bolts can't hit it (their mask leaves out hurtboxes). The crosshair turns red over it (`highlight_on_crosshair`), but the Attack order and Weapons Free never pick it (`attack_target` false, not in `targets`); if you fire at one, wingmen on Form Up join in as with any target, leading it by its public `velocity`. It has no collision body and no groups, so it can't damage or block anything, and crashing into you costs nothing. Details that matter if you change it: the ray excludes the dying fighter's own body (still in the physics world until the end of the frame) and uses `hit_from_inside`, because a ship flying at the wreck can move over the ray's start between frames; the puff shader billboards itself in `vertex()`, keeping the particle's scale; the smoke reads against space because it's toon-lit (the old soft, unlit puffs had to be a pale grey to show at all); and it's `GPUParticles3D` because `CPUParticles3D` bunched a fast wreck's puffs into clumps several metres apart. Measured (headless): a wreck in open space explodes at 3.0 s; one you keep firing at goes up within 0.1 s; one diving at the station from 150 m crashes into it at 2.0 s; one flying at the player hits them at 1.5 s with shields unchanged; on Corneria one killed in a dive hits the ground at 2.4 s.

### 8.16 The intro cutscene

**File:** [world/intro_cutscene.gd](../world/intro_cutscene.gd)

1. `play()`: put the ship at `IntroStart` on autopilot (`controls_enabled = false`), place the wingmen in their slots, hide the HUD, turn off the camera's own physics, park it at `IntroCameraSpot` with a narrow FOV.
2. **FLYBY:** the camera stays put and pans to follow the ship. Once the ship is `handover_distance` past it...
3. **CAMERA_FLY:** interpolate the camera from where it is to `chase_transform()` over 1.2 s with a smoothstep.
4. `_finish()`: snap the camera, re-enable it and the controls, fade the HUD in, emit `finished`.

Fire, Enter or gamepad A skips to `_finish()`. **To reframe the shot, move the two markers** (`IntroStart`, `IntroCameraSpot`; set in `levels/level_base.tscn`, overridden per mission, e.g. 250 m up on Corneria); on the Space Station mission the asteroid-free lane follows them automatically. The Space Station mission overrides them in `main.tscn` (`IntroStart` (60, 30, 3700), 300 m inside the 4000 m edge, and `IntroCameraSpot` (90, 34, 3400)), so the formation flies in from near the edge towards the space station at the centre: the fly-by shows the Great Fox large behind the fighters, as if they had just launched, and at handover the station sits dead ahead, about 3.2 km away.

### 8.17 Sound

**Files:** [audio/sfx/](../audio/sfx/), [effects/sound_fx.gd](../effects/sound_fx.gd), the *Sounds* export group and `_fire()` / `_update_engine_sound()` in [player/fighter.gd](../player/fighter.gd); sound nodes in [ship.tscn](../player/ship.tscn) and [enemy_fighter.tscn](../enemies/enemy_fighter.tscn)

All gameplay sounds are `AudioStreamPlayer3D`s, so they come from where things are and fade with distance; the current camera is the listener.

| Sound | How it plays |
|---|---|
| **Laser shot** (`laser.mp3`) | A `FireSound` child of each ship. `Fighter._fire()` plays it with a small random pitch change. `max_polyphony` (4 on your ship, 3 on enemies) lets shots overlap; the sound is 2 s long, so the oldest tail is cut when a new shot needs a voice |
| **Engine** (`thrusters.mp3`, looping) | An `EngineSound` child of each ship, autoplaying. `Fighter._update_engine_sound()` sets its pitch every tick: 1.0 at cruise speed, `engine_pitch_per_speed` (0.008) higher or lower per m/s, clamped to 0.5–2. For your ship (cruise 60 m/s) that's 0.68 at minimum speed and 1.56 at full throttle. Measured from cruise speed, so the light fighter (one fixed speed) keeps a steady pitch. `max_distance` 300 m keeps distant engines silent |
| **Ship explosion** (`explosion_medium.mp3`) | `explosion_sound` export on `Fighter`. Enemies and the player call `SoundFX.play_at()` where they die. The destroyer has its own export and plays it lower and slower on every other blast of its death chain, plus a deep final blast |
| **Warp portal** (`explosion_medium.mp3`, placeholder) | `open_sound` / `close_sound` exports on `WarpPortal`: a deep rumble (pitch 0.3) as the destroyer's portal opens, a quieter one (0.45) as it shuts. Played through `SoundFX.play_at()` with the portal's radius as `size` and a 6000 m `reach`, so it's heard across the area although the portal is 1400 m out |

**Why `SoundFX`:** an enemy frees itself the moment it dies, which would cut off any sound player inside it. `SoundFX.play_at()` makes a standalone player at the position and frees it when the sound finishes, with a backup timer in case `finished` never fires (no audio device, or headless tests).

**Wingmen and light fighters** get everything through scene inheritance (`wingman.tscn` inherits `ship.tscn`; `light_fighter.tscn` inherits `enemy_fighter.tscn`). Your engine is quieter than enemies' (−14 dB vs −6 dB) because the camera sits right behind it; the wingmen share that setting, being always near you. **Your ship isn't freed when it dies** (only hidden), so `Ship._die()` stops its engine. Sounds pause with the game. Destroyer turrets, destroyed parts and asteroids are silent so far.

#### Music
**Files:** [audio/level_music.gd](../audio/level_music.gd), [audio/music.gd](../audio/music.gd) (the `Music` autoload), [default_bus_layout.tres](../default_bus_layout.tres)

A soundtrack is a **`LevelMusic`** resource: an optional **lead** that plays once, then a **loop** that repeats forever, plus a `volume_db`. A mission picks its track with the `music` export on its root (`Level`); the title screen has the same export. Empty means silence.

- **Lead to loop without a gap.** `LevelMusic.build_stream()` turns the pair into an `AudioStreamInteractive` with two clips, the lead set to auto-advance into the loop. The engine switches at the exact sample, which waiting for `finished` and starting the loop can't do (`finished` fires a little late, leaving an audible gap). With no lead it's just the loop. Measured with generated tones on the real audio driver: the lead handed over to the loop on time (0.99 s for a 1 s lead), and the longest near-silence anywhere was 0.27 ms, at the seam.
- **Looping.** The loop is forced to loop and the lead not to, on copies, so the imported files' own settings don't matter. A loop offset set in the loop's import options is kept (it repeats from there). Ogg Vorbis, MP3 and plain WAV work; a compressed WAV that isn't set to loop on import gets a warning.
- **The `Music` autoload** owns the player, on the **Music** bus (`default_bus_layout.tres`, sent to Master; a music volume slider can drive it later). It lives outside the level, so when the level reloads after a death and asks for the same track, the track carries on instead of restarting its lead. A different track fades the old one out over `fade_time` (1 s) while the new one starts; `play(null)` or `stop()` fades out. While the game is paused, the music is `pause_duck_db` (−8 dB) quieter.
- **When it starts:** `Level._ready()` calls `Music.play(music)` right after building the world, so a mission's music starts with the intro fly-by.

### 8.18 Missions and levels

**Files:** [missions/mission.gd](../missions/mission.gd) + `missions/*.tres`, [ui/mission_select.gd](../ui/mission_select.gd), [levels/level.gd](../levels/level.gd), [levels/level_base.tscn](../levels/level_base.tscn), [main.tscn](../main.tscn) / [main.gd](../main.gd), [levels/corneria.tscn](../levels/corneria.tscn)

**Mission selector.** Start on the title screen hides the menu and opens `MissionSelect`, a screen built in code from its `missions` export (an array of `Mission` resources set on the node in `title_screen.tscn`). It's one button per mission, with the highlighted mission's `description` underneath, then Back. Keyboard, mouse and gamepad all work through the normal UI focus; Esc / B closes it. Picking a mission emits `chosen(mission)` and the title screen fades to `mission.scene_path`. A `Mission` is just data (`title`, `description`, `scene_path`), so objectives can be added to it later.

**Levels share a base scene.** `levels/level_base.tscn` holds every node a mission needs: ship, camera, wingmen (each pointing at its pilot file), wing command, spawner, HUD, comms, pause menu, intro markers and cutscene, sun, environment. Its root runs `Level` (`levels/level.gd`): build the world, intro and intro line, start the spawner when you get control, restart after death, keep the mouse captured. A mission scene **inherits** the base (like `wingman.tscn` inherits `ship.tscn`), keeps the same flat node names (`Ship`, `Falco`...), overrides what differs, and adds its world:

- **Space Station mission** (`main.tscn`, root `Main`): `main.gd` extends `Level` and overrides `_build_world()` to scatter the asteroids. Adds `SpaceDust`, a `PlayBoundary` (radius 4000 m), `EnemySpawner.zone_radius` 3000 m, the `ChaseCamera`'s `far` raised to 10000 m (so the Great Fox, at 5000 m, stays visible from across the area) and a `GreatFox` behind the intro start ([8.19](#819-planet-terrain-corneria)). Two seconds after the player gets control (`intro_advisor_delay`, after the intro cutscene), Peppy says "Stay sharp, team. I'm reading multiple enemy squadrons approaching our position." (`intro_advisor_line` on `Main`; `Level._begin_play()` times it, `_say_intro_advisor_line()` sends it through `MissionControl.say()` at HIGH priority. Fox's intro line is HIGH too, so if the intro was skipped and Fox is still talking, Peppy waits for him).
- **Corneria** (`levels/corneria.tscn`, root `Corneria`): plain `Level` with its own `intro_line`, enemy waves without destroyers (`destroyer_every = 0` on its `EnemySpawner`) and a `PlayBoundary`. Overrides the environment (daytime sky, see [8.19](#819-planet-terrain-corneria)), the sun, and the start positions: the formation starts 120 m over the sea south of the coast, heading north towards the bay and its arches (after a death the intro is skipped and ships start where the scene puts them). Adds `Terrain` (with the Corneria map), `Props`, `Clouds` (which build themselves), `PlayBoundary` and a `GreatFox` parked outside the boundary.

**Anything changed in the base reaches every mission** unless the mission overrides it. To change one mission only, select the node in that mission's scene and change it there (the editor shows inherited nodes greyed in the Scene dock).

### 8.19 Planet terrain (Corneria)

**Files:** [world/terrain.gd](../world/terrain.gd), [world/terrain_map.gd](../world/terrain_map.gd), [world/map_props.gd](../world/map_props.gd), [world/clouds.gd](../world/clouds.gd), [effects/terrain.gdshader](../effects/terrain.gdshader), [effects/water.gdshader](../effects/water.gdshader), [world/planet_environment.tres](../world/planet_environment.tres); the map in [models/corneria/](../models/corneria/), built by [build_corneria.py](../models/corneria/source/build_corneria.py); the camera's ground clearance in [player/chase_camera.gd](../player/chase_camera.gd)

**The Corneria map** is our own, laid out in Blender by a script like the destroyer and the enemy fighter, from hand-made models (the kit, below). It's 8 × 8 km, centred on the origin, north is −Z:

- **South:** open sea, where the mission starts (120 m up at (−450, 3400), heading north), with leaning rock spires (sea stacks) and two small islands offshore.
- **The bay** runs north into the land; six stone arches stand in a line up it (openings about 80 m wide and 120 m high), then a red suspension bridge with a 30 m deck to fly under carries a city street over the river mouth.
- **Corneria City** sits where the river meets the bay: a street grid of about 170 blocks rising to downtown towers (stepped, round and domed, glass slabs, twin towers with a skybridge) around a 340 m spire. Towers over 100 m carry red warning lights.
- **The river** comes from a waterfall off a 130 m plateau in the north-east (a lake on top), winding through the hills past the city.
- **The west:** rough hills, rocky ridgelines, five mesas, a canyon from the north-west mountains down to the river, cliffs along the coast, a lake, and the **military base** (runway, hangars, control tower, radar, headquarters, barracks, depot, radio mast) reached by a road through a graded valley from the bridge.
- **The east coast:** a harbour town with piers, boats and a lighthouse.
- **Mountains** wrap the north, east and west edges irregularly (peaks and saddles, spurs reaching inward), snow-capped above 260 m, fading into sea cliffs toward the south.
- About 6,000 low-poly pines in clumps on the gentle slopes, and round trees in the city's parks.

**How it gets into the game.** `build_corneria.py`, run in Blender with `FORCE_EXPORT`, writes three files next to its `source/` folder:
- `corneria_map.tres`, a **`TerrainMap`** resource: the ground height at each point of a 321 × 321 grid (25 m cells), one byte per cell saying what it is (`PAINT_AUTO` coloured by Terrain's height and slope rules, `PAINT_PAVED` for the city, town and base apron, `PAINT_HIGH_WATER` under the plateau lake, whose surface is `high_water_level` 120 m), and the **structure height** of each cell: the top of the tallest building, arch, bridge part or rock spire overlapping it (0 where there's none).
- `corneria_props.glb`: everything standing on the ground (city, streets, town, base, arches, bridge, road, sea stacks, trees, and the plateau lake and upper river). The sea isn't in it: Terrain makes the sea. Nor are the falls: they're the game's `Waterfall` node (below).
- `waterfall.txt`: the `Waterfall` node's transform (on the lip, where the upper river ends at the cliff's edge, the water flowing towards the head of the lower river), to paste onto it in `levels/corneria.tscn` when the river or the cliff moves.

To change the map, edit the script (layout constants at the top: city, base, plateau, river, bay, road waypoints...), run it in Blender through the MCP with `FORCE_EXPORT` (or `blender --background --python build_corneria.py -- --export`), then run Godot's `--import` (or let the editor reimport) and reload the scene. Never edit the two exported files by hand. Open surfaces the script still builds itself (the lakes, the river) are given an explicit facing: the game draws only the front of a face, while Blender's preview shows both.

**The kit.** The buildings, bridges, arches, sea stacks and trees are hand-made models in [models/corneria/source/corneria_kit.blend](../models/corneria/source/corneria_kit.blend), one collection per piece (`Kit_Spire`, `Kit_SteppedTower`, `Kit_House`...), specified in [models/corneria/ASSETS.md](../models/corneria/ASSETS.md) (sizes, origins, the palette, the rules for the cel-shaded look). The script (`load_kit()`) reads every `Kit_*` object once and copies it, through `Batch.kit()`, wherever it used to put a box: scaled to the size it picks, turned, and merged into the same objects as before (`City`, `Town`, `Base`...), so collision, `MapProps` and the AI's structure heights work as they did. Some ways it fits pieces to their spots:
- **Towers** come in parts: a base, a 20 m shaft section, a crown. `shafts()` stacks as many shafts as bring the tower nearest the height the layout picked, then stretches the stack to hit it exactly. The twin towers' shaft holds both towers, so each tower stacks its own half (`only=`), the east one to 86 %.
- **Low blocks** are a 10 m unit block stretched to any size; what stands on the roof keeps its height (`height=`). The kit asks for one of three wall colours.
- **Streets** are 30 m straight pieces (stretched to fit) between crossing pieces, laid once where two streets meet. **Street bridges** (spans and piers stretched down to the river bed) are ready but unused: no street crosses the river where the layout bridges one.
- **Materials** are matched by name to the script's palette (`PALETTE`), so the kit's own colours don't matter, and per-copy colours are a material swap (`swap=`: each parked car's body).
- **Faces** keep the way they were modelled to face (the script only recalculates its own shapes), and smooth shading and sharp edges come across, so curved towers aren't drawn as facets with an ink line on every edge.
- **Everything else** in the kit is placed at its origin (front at Blender −Y, the side facing the player's approach) and turned as the layout says: hangar doors face the runway, the headquarters is mirrored so its second wing points away from the parking lot.

Changing a piece means editing it in `corneria_kit.blend` and re-running the script (the `.glb` files in `models/corneria/kit/` are previews for checking a piece in Godot, not used by the game). The kit was checked with every part's faces pointing outward (the signed volume of each closed piece); a piece modelled inside out would show only its inside in the game. `models/corneria/source/` has a `.gdignore`, so Godot doesn't try to import the `.blend` files itself (that needs Blender on every machine that opens the project).

`Terrain.map` points at the map, so Terrain uses its heights instead of noise (below). The props are instanced as `Props` with **`MapProps`** on it: at load it cel-shades the materials with `ToonMaterial` (the foliage, `unlined_materials`: tree greens and trunks, also the green tufts on the sea stacks, without ink outlines, because thousands of small cones made a tangle of lines), gives the plateau water the level's water material, and builds trimesh collision on the World layer from the solid meshes (`solid_nodes`: everything but the streets, road and trees). So you crash into buildings, bolts hit them, and they block enemies' line of sight. The unlined foliage is drawn in the transparent pass, which casts no shadows, so `_add_shadow_casters()` gives each mesh holding some a child with just those surfaces, drawn only into the shadow maps (`SHADOW_CASTING_SETTING_SHADOWS_ONLY`; InkOutline never sees them); without it the trees looked as if they floated. Measured from the same eight viewpoints (2 runs each), unlined trees with their shadow stand-ins cost no measurable GPU time. Loading the mission takes about 0.9 s headless (the terrain mesh is most of it), and it renders as fast as the old 4 km test map did (about 650 FPS uncapped at 1280 × 720 with 12 enemies over the city, worst frame 2.2 ms, on the development machine). The kit roughly doubled the triangles drawn (1.2 to 2.3 million a frame, depending on the view) but not the cost: measured from eight viewpoints at 1280 × 720 (2 runs each), GPU time stayed within about 0.2 ms of the boxes' (2.0 to 2.8 ms a frame), CPU unchanged. `corneria_props.glb` grew from 4.7 to 22.6 MB.

**Terrain without a map** (any future planet mission) builds itself in `_ready()` from seeded noise (`terrain_seed`), so the landscape is the same every run. That map is `size` (4 km) square, centred on the origin. Height at any point is:

```
base_height (8 m)  +  hills (±70 m, ~900 m wide)
                   +  ridged mountains (up to 320 m), only where a slow "region" noise allows,
                      and none within 450 m of the centre (fading in over the next 500 m)
                   +  boundary ring (up to 520 m) rising from 72% to 90% of the half-width
then sinking to just below sea level in the last 6% of the map, so the edge meets the far ground.
```

Either way the heights live on a grid (25 m cells: 160 × 160 for the noise map, 320 × 320 for Corneria), built into 8 × 8 chunks of triangles (204,800 on Corneria). Each grid point is one vertex shared by the triangles around it, with a smooth normal from the slope to its neighbours (`_grid_normals()`), so the cel-shaded light bands follow the shape of the land instead of stepping from triangle to triangle.

**The ground's colour is chosen per pixel** by [terrain.gdshader](../effects/terrain.gdshader), not per triangle: sand below 6 m above the water, rock where it's steeper than `rock_slope`, snow above 260 m, otherwise light or dark grass in broad patches (`patch_scale` 350 m) with smaller patches a shade lighter or darker (`mottle`). Cells a map marks as paved get `paved_color`: Terrain hands the shader the map's paint as a one-texel-per-cell texture, and linear filtering rounds its corners. Every boundary is a hard edge (the cel look) moved back and forth by one world-space noise (`edge_scale` 40 m; how far per boundary: `sand_wobble`, `snow_wobble`, `slope_wobble`, `paint_wobble`), so none of them follow the triangles. Terrain's own exports (the colours, `sand_height`, `snow_height`, `rock_slope`, `sea_level`) are handed to the material in `_feed_ground()`; the rest are uniforms on the ground material (`Mat_ground` in `corneria.tscn`), and Terrain makes a material itself if it has none. Two optional greyscale textures, `grass_texture` (projected from above) and `rock_texture` (from three sides, so it doesn't stretch down cliffs), multiply the colours for hand-drawn detail; they're white, no effect, until set. `rock_facets` lights rock by its triangle's flat normal instead (crags rather than dunes), but it's off: from about 0.2 the light bands step round single triangles, saw-toothed, wherever they cross a slope. The shader's noise is the water's (`noise.gdshaderinc`, shared).

This replaced flat-shaded triangles with one colour each (chosen by the same rules, plus ±5% random brightness): grass came out as a checkerboard of triangles, and every beach, cliff and paved edge as a sawtooth along them. The cost didn't change measurably (GPU 2.2–2.5 ms at 1280 × 720 from four views over the map, 2 runs each, before and after), nor did load time.

Collision is a `ConcavePolygonShape3D` per chunk built from the very same triangles, on the World layer, so you crash into hills exactly where you see them (30 damage and a bounce, the normal crash).

- **`height_at(x, z)`** returns the ground height, interpolated within the same triangle the mesh uses (each cell splits along its (0,0)–(1,1) diagonal). It matches the collision exactly, and returns `-INF` outside the map. **`surface_height(x, z)`** also counts the water (the sea, and a map's high water). **`water_level_at(x, z)`** is the water's surface there, or `-INF` on dry land; **`is_water_surface(point)`** says whether a point lies on it (bolt splashes, see [8.15](#815-visual-style)). **`clearance_height(x, z)`** also counts a map's structure heights: it's what the AI, enemy spawns and the player's turn-back stay above. The chase camera uses `surface_height()` instead, so it doesn't jump onto a rooftop when you fly between towers. The wingmen's formation slots also start from `surface_height()`, then rise over structures gradually (ramped ahead and rate-limited, see [Formation near the ground](#formation-near-the-ground)). Ground-aware code finds the terrain through the `terrain` group (added in `_enter_tree()`, so nodes earlier in the scene can find it in their `_ready()`).
- **Lakes and the sea** are one opaque plane at `sea_level` (0), so every basin below it fills with water. With `water_to_horizon` (Corneria) the plane reaches the horizon, so there's sea beyond the coast instead of the far ground. Water above sea level (the plateau lake and its river) is part of the props, with its own collision, and gets the same material.
- **The water shader** (`water.gdshader`) is cel-shaded and has no ink outlines (there used to be a dark line along every shore and at the horizon): it uses `ALPHA` (`ALPHA *= 1.0`, so still solid) with `depth_draw_always`, which puts it in the transparent pass, after the outline quad and out of the depth texture the outlines read; whatever is under the water still gets lines, but the water, drawn after them, covers them. Terrain gives its material `water_render_priority` (-50), between the outline quad (-100) and other see-through things (0): sorted by distance alone, the huge plane could count as nearer than a laser bolt over the sea and be drawn over it (checked: bolts over the sea show the same as with opaque water). Terrain hands it the ground heights as a texture (`_feed_water()`: the height grid as half floats, plus `ground_grid`), so each pixel knows how deep the water is: surface height minus the ground under it, or `open_depth` (100 m) off the map. The heights it gets are reshaped first (`_sea_floor()`): a distance transform finds each grid point's distance to land, and from `water_depth_fade` 150 m out to 600 m the floor sinks to `open_sea_depth`, so the bands follow the coasts. Without that, Corneria's artificial border (every edge point at -6 m, ramping straight down to -28 m inside) drew depth bands and a light seam as straight lines kilometres long, and the map edge met the open sea in a hard line. It costs 33 ms at load. **Noise:** gradient noise on an integer hash. The first version used value noise on a float hash (`fract(p * 123.34)`...), which at world-scale coordinates rounded a shared grid corner differently in neighbouring cells, so every effect broke off along straight world-aligned seams that ran a long way at grazing angles; value noise cut at a threshold also made blocky, axis-aligned crest patches. The explosion puffs use the same integer hash. That drives hard **depth bands** (turquoise `shallow_color`, `water_color` from `mid_depth` 3 m, `deep_color` from `deep_depth` 12 m, edges made ragged by `depth_wobble`) and **shore foam** (solid within `foam_depth` 0.6 m, plus lines rolling in from `foam_reach` 4 m; the lines follow the depth, so on an evenly sloping beach they ran dead straight and even: noise bends them by up to `foam_wobble` (1.0) of the line spacing over `foam_wobble_scale` (10 m), varies their thickness, and leaves out `foam_gaps` (30%) of them, so they break into separate crests). On top: sparse squiggly **wave crests** (contour lines of a slowly warping noise, a fixed `crest_width` in metres so they never swell into blobs, fading out by `crest_fade_end` 1.8 km and wherever they'd get finer than a few pixels), **sun sparkles** (a hard glint on small drifting ripples, `ripple_scale` 7 m; the ripples flatten where they'd be smaller than a pixel, so far away the sparkles merge into one sun path instead of flickering), and the **sky** colour at grazing angles. Shadows (ships, clouds) darken it to `shadow_tone`. The ripples only reach the sparkles (a `varying` passed to `light()`), never `NORMAL`, so the cel-shaded light on the surface stays flat. All of it is uniforms on the level's water material (`Mat_water` in `corneria.tscn`).
- **Water and the far ground are solid:** thin collision slabs under each, so diving into a lake is a crash, not a swim.
- **Far ground:** a 30 km flat plane just under sea level fills the horizon beyond the map (under the water on Corneria).
- **Backdrop** (`backdrop`, on for Corneria): scenery beyond the map's edge, so the land seems to go on. Without it Corneria looked like a square island: every mountain pass opened onto a sea horizon 500 m past the play boundary, and the east headland ended in a straight line. `_build_backdrop()` lays rings of vertices round squares centred on the map. The first ring is the map's own grid line `backdrop_inset` (150 m, rounded to whole cells) in from the edge, sharing its vertices and normals, so the seam is exact; the map's sinking border passes underneath, hidden, so the exported map needs no change. Further rings are ever wider apart (`backdrop_first_step` 50 m, ×`backdrop_step_growth` 1.2 each) out to `backdrop_reach` 5.5 km past the edge, past the camera's far plane. Each vertex carries the edge height straight out (smoothed along the edge over `backdrop_smoothing` 400 m after the first few hundred metres, so small bumps don't streak), blending over `backdrop_blend` 1.5 km into its own ridged mountains: valleys at `backdrop_base` 40 m, crests (noise above `backdrop_crest` 0.5) up to 600 m more, `backdrop_scale` 2.2 km wide; green valleys, snow on the tops. Where the edge is sea (lower than `backdrop_land_height` 20 m), it stays sea floor. The share of land along the edge is averaged over `backdrop_coast_smoothing` 3 km and wobbled by noise (`backdrop_coast_wobble` 0.35), so the coast meanders out to sea instead of running straight out from where the map's coast meets its edge (the first try did that: a long, straight cliff). Same ground material as the map (the shader ignores paint off the map), no collision, no shadows, triangles wholly under the sea dropped, one mesh per side for culling. Cost on Corneria: 30k triangles, +70 ms at load.

**The waterfall** ([world/waterfall.gd](../world/waterfall.gd), scene [waterfall.tscn](../world/waterfall.tscn), shader [effects/waterfall.gdshader](../effects/waterfall.gdshader)). The falls off the plateau aren't a prop (the kit's `Kit_Waterfall`, stiff static planks, is no longer used): a `Waterfall` node in `corneria.tscn` sits on the lip, the cliff's edge where the upper river ends (`LIP` in the map script, the river's last point), on the river's surface (0.3 m up so the two don't flicker), the water flowing along its local +Z towards the head of the lower river. It's a `@tool` script, so the falls show (and reshape) in the editor.
- **Shape** (the *Shape* exports): one closed body of water along the arc water thrown off the lip would follow (`z = speed × t`, `y = −½ g t²`, the speed chosen to land `reach` 32 m out after a `drop` of 125 m, to just under the pool's surface), steep at first and bowing outwards, `width_top` 80 → `width_bottom` 88 m. Its cross-section is a lens: a front and a back surface meeting at the sides, `thickness_top` 11 m in the middle at the lip (about the river's depth there, so the river visibly pours over in one body) to `thickness_bottom` 7 m. A `run_up` (18 m) lies on the river before the lip, fading in (vertex alpha) over the river's own water, which stops 6 m short of the lip (`RIVER_SHORT_OF_LIP`: the terrain grid, 25 m, is coarser than the face, so the ground there already slopes down it).
- **Look** (the shader): each vertex's UV.y is its time of travel from the lip (seconds), so the streaks, scrolling by that time (`speed` 2.2 × real, which looked sluggish at this size), speed up as they fall, like real water. Flat bands: the water's blue, a lighter blue, white streaks; a white band over the lip; more and more white from 60 % of the way down to the foot; ragged sides that bite in more lower down. A band where the body turns away from you (`shade_below` 0.45 of facing) is drawn darker (`shade` 0.8), so its rounded sides read as a thick body from any angle. Optional `splits` (0 by default): wedges under the lip, as if rocks parted the water, where the cliff shows through. Unshaded and in the transparent pass (no ink outlines).
- **At the foot:** a **mist** emitter (`Explosion.trail()`'s puffs born cold, near-white, 9 a second, swelling 10 → 32 m over 3.5 s, spread along the whole foot, drifting up and downstream; prewarmed so it's already billowing; placed on the pool's surface from `Terrain.water_level_at()`) and **foam rings** on the water (`WaterMarks.add_ring()`, 3 a second, size 3–6, across the foot and 40 m downstream; they share the water's 32-ring budget with the bolt splashes).
- **The ground around it** is shaped for it by the map script: the upper river's channel is carved so its banks rise through the water (about 40 m out) and stand above it right to the lip (the lower river's carving is kept off the plateau's side of the lip, `falls_local()`), and a **plunge pool** is cut in front of the lip (`PLUNGE_HALF_WIDTH` 60 m either side, a sheer face down to the pool within about 20 m, joined to the lower river). The cliff there used to be a 2:1 slope the falls would have landed on. The plateau's water surface (`PAINT_HIGH_WATER` cells, which `Terrain.water_level_at()` uses) stops 12 m behind the lip, so the pool below isn't taken for water 120 m up.
- No collision: bolts and ships pass through. Moving the falls: `build_corneria.py`'s export writes `models/corneria/waterfall.txt`, the node's transform; paste it onto the node. Measured at 1280 × 720 looking at the falls from 150 m (rendered, 2 runs each): about +0.1 ms GPU (2.09–2.10 → 2.19–2.22 ms).

**Clouds** (`Clouds`): clusters of 5–9 squashed toon blobs in two layers. The defaults are 60 clusters at 220 m and 430 m (`layer_jitter` ±30) within 1700 m of the centre, none within 350 m of it; Corneria has 170 at 650 m and 950 m within 3600 m (high in the sky, above the city and most of the mountain rim, whose peaks reach about 720 m). Each cluster is merged into one mesh (blob spheres of `blob_detail` 20 × 12, enough vertices for the lumps) and scaled as a whole by a random `cluster_scale` (0.5–1.5); with `big_chance` (6%) it is a giant instead, scaled by `big_scale` (4–6.5) and placed in the highest layer plus `big_lift` (100 m), so its flat base sits about there rather than hanging through the layer below. Corneria gets 7 giants, 370–920 m across against a median cluster of about 125 m. The cloud shader works in the cluster's own space (lump size and height, flat base), so a giant is the same cloud, bigger. Corneria draws them with their own shader, [cloud.gdshader](../effects/cloud.gdshader): slowly drifting value noise (integer-hashed) pushes the blobs out into lumps (`lump_scale` 16 m, `lump_height` 12 m) and, per pixel, bends the normals down each lump's slope (`lump_shading`; per vertex the bands followed the sphere's triangles); anything more than `flat_base` (8 m) below the cluster's centre is squashed to `base_squash` (0.3) of its depth, with its normals squashed the same way, a broad, gently lumpy base (pressing it fully flat looked like a sheet of glass under every cloud). Faces turned downwards also shade softly towards `crevice_color` in the hollows between lumps (`crevice_threshold`, `crevice_softness`, `crevice_from`): seen from below they are all in the shade, and one even tone read as flat; a hard-edged band instead drew blotches like a cow's spots. Its `light()` has three bands of its own (white top, pale blue middle, blue-grey `shade_color` underside; the generic toon shadow made them look grey), the toon rim, and a silver lining when the sun is behind them. No ink outlines: the shader uses `ALPHA` (`ALPHA *= 1.0`: it starts at 1 minus the node's `transparency`, so assigning 1 would break the camera fade), which puts the clouds in the transparent pass, after the outline quad and out of the depth texture it reads, so they read as soft shapes against the sky and cover the lines of whatever is behind them; `depth_draw_always` keeps the blobs of a cluster hiding each other. They have no collision; while the camera is inside or within 40 m of one, it fades to 85% transparent, like the wingmen near the camera.

**Sky and light** (`planet_environment.tres`): a procedural day sky whose lower half matches the horizon colour (otherwise a dark band shows past the far ground), depth fog in the horizon colour that doesn't tint the sky: none up to `fog_depth_begin` (1.5 km), then building (`fog_depth_curve` 1.6, slow at first) to full at `fog_depth_end` (5 km, the camera's far plane, so the far plane's cut never shows; the map's edge, much nearer from the play boundary, is hidden by the backdrop instead). It used to be exponential (density 0.00035), which starts at the camera: about 10% at 300 m and 30% at 1 km, washing out everything you fly past. and a higher, slightly brighter sun with shadows out to 600 m.

**Camera:** `ChaseCamera` keeps at least `ground_clearance` (3 m) above `surface_height()` when the level has a terrain, so low flying never puts it underground.

**Ground-aware AI and spawning:** enemies and wingmen stay above the ground and the city's structures ([8.4](#84-the-ai-pilot-aipilot)), wingman slots rise when you fly low ([8.8](#88-wingmen)), enemy patrols and waves stay above the ground and inside the boundary ([8.5](#85-enemy-fighters), [8.7](#87-waves-and-the-spawner)). Hills and buildings block enemies' line of sight, like asteroids.

Measured on Corneria (three 3-minute runs, the player circling the city 60 m above the ground while waves attack and the wingmen cycle Form Up, Weapons Free and Cover Me): wingmen never touched the ground or a building; enemies scraped the ground once in 9 minutes (a slow light fighter on patrol climbing into a slope) and never hit a building. **The AI flies over the city, not through it.** A whole 25 m cell counts as tall as its tallest structure, so streets read as solid. With the player flying straight down a street 26–106 m up, the wingmen hop over the buildings (up to 150–250 m above the ground) and are in formation 72–88% of the time; in one of four runs a wingman brushed a tower wall sideways (they can't be hurt, they slide off). Enemies chase you over the rooftops rather than between them.

**Play boundary** ([world/play_boundary.gd](../world/play_boundary.gd)): a `PlayBoundary` node marks the edge of the area, a vertical cylinder of `radius` around the node: 3300 m around (0, 0, 500) on Corneria, reaching into the mountains on three sides and out over the sea to the south (the intro starts the formation 300 m behind the start point, which has to be inside too); 4000 m on the Space Station mission, just past the asteroids (3800 m); destroyers arrive well inside it there (`zone_radius` 3000 m, see [8.10](#810-the-destroyer)). Only horizontal distance counts. Past it the HUD blinks **RETURN TO THE COMBAT AREA**; past `radius + turn_back_margin` (200 m further, on the ring's slopes) the ship turns itself back, like Star Fox's all-range mode, and the HUD shows **TURNING BACK** ([8.2](#82-the-players-ship-ship)). A negative `turn_back_margin` keeps the warning but never takes control. A mission without a `PlayBoundary` has no edge. Enemy waves and patrols stay inside it on either mission ([8.5](#85-enemy-fighters), [8.7](#87-waves-and-the-spawner)). Tested on Corneria, flying east into the mountains from 120 m and 300 m above the ground: the warning came at the edge, the turn started at 201 m out, the ship went no further than 241 m out and didn't touch the slopes. (On the old 4 km test map, flying level and low straight at the ring's steepest ridges could still hit the slope before or during the turn; that's still possible wherever the mountains are steep.)

**The Great Fox** ([world/great_fox.tscn](../world/great_fox.tscn), script `GreatFox`): the team's mothership hovers outside the area, so the Star Fox team feels present. On Corneria it sits at (500, 700, 4500), over the sea about 730 m outside the boundary, behind the direction the formation flies in from. It shows in the background of the intro fly-by, and you see it whenever you turn back towards the sea. It is yawed 70° so it shows a three-quarter profile, and it bobs 3 m over 14 s (`bob_height`, `bob_period`). It is **scenery only**: no collision, not in any group, not shootable, and the AI doesn't know it exists. So it must stay out of reach. With the old 2.5 s boost, flying straight at it, the turn-back stopped the ship about 257 m short of the hull (farthest point reached: 3,549 m from the boundary's centre). Full throttle is as fast as that boost and doesn't run out, so it now gets 95 m farther (3,644 m): roughly 160 m short of the hull. Move it further out if you shrink the margin or grow the boundary. Fog makes it a hazy silhouette at that distance, which helps it read as huge. Drawing it costs about 0.05 ms a frame.

On the **Space Station mission** it sits at (0, 30, 5000), behind `IntroStart` (60, 30, 3700), so the formation's fly-in starts about 1.3 km in front of it. It moved out from 3,600 m when the boundary grew from 2000 to 4000 m (turn back at 4200 m): flying straight at it at full throttle (130 m/s), the turn-back stopped the ship about 4,345 m from the centre, 384–394 m from its hull (3 runs, aimed at its middle and at both ends). (Earlier history, measured at the original size, boundary 1000 m and the Great Fox at 1,800 m, follows.) Its bow points into the field, yawed -25° so the intro camera sees its profile, and the formation appears in front of its lit hangar openings, as if they had just launched. That field had no edge before; it got a `PlayBoundary` (radius 1000 m, turn back at 1200 m) to keep the player away from the hull. Boosting straight at it (the old 2.5 s boost), the turn-back stopped the ship 195–220 m short (farthest point 1,340 m from the centre); at full throttle, which is as fast and doesn't run out, the farthest point is 1,349 m. At 1,700 m it came within 112 m, which is why it's at 1,800 m. A side effect: waves now spawn at least 250 m inside the boundary and patrols roam at least 150 m inside it, so fighters stay within 750–850 m of the centre, about the extent of the asteroids. There's no fog in space, so it's crisp.

The model is in [models/great_fox/](../models/great_fox/) (see its README.txt: no licence came with the download). It is a Sketchfab glTF export with a tilt baked in. The `Model` node's transform in `great_fox.tscn` undoes that, so the scene's -Z is the bow, +Y is up and the origin is the middle of the hull (464 × 310 × 97 m at scale 1). At load, `GreatFox._ready()` swaps its PBR materials for cel-shaded copies with `ToonMaterial.convert_tree()` ([8.15](#815-visual-style)): the textures (panel lines, Star Fox emblem, logo) and glow maps (hangar openings, windows, engines) stay, and the bump and metal maps go. The editor still shows the originals. The originals were double-sided and the cel shader isn't, but a check against a magenta background showed no holes. One visible difference: the engine housing's metal panels used to reflect the sky and now show their light-grey texture. Its textures were downscaled to 1024 px, and its DirectX normal maps are flipped on import (`process/normal_map_invert_y`). To add it to another mission, instance `world/great_fox.tscn` in the mission scene and place it outside that mission's reach.

---

## 9. Code conventions and recurring idioms

### Style
- **Static types everywhere**, `:=` for inferred types.
- **`##` doc comments** above classes, exports and functions; `#` comments for the *why* inside function bodies. The codebase favours explaining intent ("so wingmen fan out instead of clumping") over restating code.
- **`_leading_underscore`** for private members and Godot callbacks; public API has no underscore.
- **Exports grouped** with `@export_group`; every tuning number is an export rather than a magic number in code.
- **`#region` / `#endregion`** to fold big scripts into sections.
- Tabs for indentation (Godot's default).
- One responsibility per script, and systems talk through groups and signals rather than direct paths.

### Idioms you'll see repeatedly

**Frame-rate independent smoothing: `1.0 - exp(-k * delta)`.**
```gdscript
_basis = _basis.slerp(ship_basis, 1.0 - exp(-follow_sharpness * delta))
```
"Move a fraction of the way towards the target each frame" with a fixed fraction would behave differently at different frame rates. This formula gives the same result per second at any frame rate. Read `k` as "how many times per second it closes most of the gap": higher is snappier. It appears in the camera, turn rates, model banking, formation rotation and FOV.

**`move_toward(value, target, rate * delta)`**: change at a constant rate, without overshooting. Used for speed, damage flash and the formation assist.

**`smoothstep(a, b, x)`**: 0 below `a`, 1 above `b`, smooth in between. Used for fades by distance.

**Local space via transforms.**
- `node.global_transform * local_point` → a point in the node's frame, in world space (formation slots: `leader.global_transform * slot_offset`).
- `node.global_transform.affine_inverse() * world_point` → a world point in the node's frame (radar, camera fade, turret aim).
- `-global_basis.z` is forward, `global_basis.x` is right, `global_basis.y` is up.

**Guard against freed nodes.** Nodes can be freed at any time (a target explodes). Before using any stored reference, check `is_instance_valid(node)`. Don't cast a possibly-freed reference with `as` before checking.

**Guard against double hits.** Several bolts can land in the same frame. `take_hit` starts with `if health <= 0: return` (or `is_destroyed`) so a thing can't die twice and award score twice.

**Duck typing with `has_method` and `get`.** `has_method("take_hit")` to see if something's shootable; `node.get("velocity")` returns null if there's no such property, which the lead-point code uses to handle both moving and static targets.

**Shared resources need per-instance copies.** A material in a `.tscn` is shared by every instance. To change it for one instance (the shield bubble), `duplicate()` it first, as `ShieldEffect._ready()` does. `ShipModel` does the opposite on purpose: one toon material per imported colour, shared by every ship, plus separate band materials per ship.

**Static variables for shared or persistent data.** `Asteroid._meshes` (built once, shared), `DestroyerPart._charred` (one material for all wrecks), `Level._skip_intro_once` and `WingCommand._last_destroyer_caller` (survive a scene reload).

**Coroutines for sequences.** `await` on timers and tweens for multi-step events (destroyer death, hangar launch, scene fade). After any `await`, check `is_inside_tree()`: the scene may have been reloaded or the node freed while waiting.

**Timers that respect pause:** `get_tree().create_timer(seconds, false)`. The `false` (`process_always`) makes the timer stop while the game is paused.

---

## 10. Recipes: common changes step by step

### Tune something
1. Find the node: `Ship` in `player/ship.tscn` (flight, guns, shields), `EnemySpawner` / `Falco` / `Slippy` / `Krystal` / `HUD` / `Comms` in `levels/level_base.tscn`, the root of `enemies/light_fighter.tscn` (basic enemies).
2. Change the export in the Inspector. Hover any property for its documentation.
3. Prefer overriding on a scene over changing a script default, so the script stays a sensible baseline.

**Difficulty levers:** enemy bolt `damage` (`weapons/enemy_laser.tscn`), enemy `spread_deg`, `fire_interval`, `max_health`, `view_cone_deg` / `detection_distance` (enemy *Senses*), wave sizes and `max_fighters` (spawner), shield regen and reboot (ship).

### Add a comms line
1. Decide who says it and when: find the event (a signal, or the place in code where it happens).
2. Get the speaker: `ship.speaker`, `wingman.speaker`, or `preload("res://comms/speakers/falco.tres")`.
3. Call `Comms.find(get_tree())`, check it's not null, then `say(speaker, "Your line.", priority)`. Use LOW for chatter, HIGH for anything the player must not miss.

*Example:* a wingman reacting to your shields going down. `Ship` already emits `shields_depleted`. In `WingCommand._ready()`, connect `leader.shields_depleted` to a function that picks a wingman and says a HIGH line like *"Fox, your shields are down!"*.

### Add a character portrait
1. Import an image into the project (drop it in a folder such as `comms/portraits/`). In its import settings, turn **Mipmaps > Generate** on: the square is much smaller than a typical image.
2. Open the speaker's `.tres` in `comms/speakers/`, and drag the image onto **Portrait** in the Inspector.

It's cropped to fill the 84×84 square, so use a square image, ideally 256×256 like the existing ones (the HUD scales up with the window, to about 140 px at 1080p). A transparent background shows a dark backdrop in the speaker's colour.

### Add a recorded voice line
1. Drop an `.ogg` or `.wav` into the project (for example `audio/voice/`).
2. Pass it as the fourth argument: `comms.say(speaker, "Text.", Comms.Priority.LOW, preload("res://audio/voice/line.ogg"))`.

The text still types out; the box stays up until the recording ends.

### Add an input action
1. Add an entry to `Settings.ACTIONS` (id, display name, group).
2. Add its defaults to `Settings._default_bindings()`: `[primary, alternate, gamepad]`, using `_key()`, `_mouse()`, `_button()`, `_axis()` or `null`.
3. Read it with `Input.is_action_pressed(&"my_action")` or `event.is_action_pressed(&"my_action")`.

The controls screen lists it automatically, and old save files pick up the default.

### Add a new wingman order
1. In `wingman.gd`: add the value to `enum Order`, an `assign_my_order()` function (set `order`, set `standing_order` if it persists, call `command_follow()` or `command_attack()`, emit `order_changed`), a label in `order_label()` (tests and debugging use it), and behaviour in `_decide()` (like `WEAPONS_FREE` → `_free_goal()`). Update `is_in_formation()` if it matters.
2. In `wing_command.gd`: add `order_my_order()` calling `_issue(func(w): w.assign_my_order(), "doing my order")`, and handle a new input action in `_unhandled_input`.
3. In `settings.gd`: add the action (see above).
4. In `hud.gd`: give it a colour in `_draw_wing_card()`, an icon in `_draw_order_icon()` (a few lines and circles; keep it readable at 16 px and distinct from the others), and, if it attacks, a colour in `_draw_order_markers()`.

### Add a new enemy type
1. Make a new inherited scene from `enemies/enemy_fighter.tscn` (*Scene → New Inherited Scene*), as `light_fighter.tscn` does.
2. Change exports (health, speeds, turn rates, fire rate, bolt scene) and the model. **Keep `Model/MuzzleL` and `Model/MuzzleR`** (Fighter fires from them) and collision layer 4; move `Model/SmokePoint` to the new model's engine (its damage smoke comes out there).
3. For new behaviour, write a script that `extends EnemyFighter` and override `_decide()` or `_update_state()`.
4. Point `EnemySpawner.enemy_scene` at it, or extend the spawner to mix types.

### Add something shootable
1. Pick a layer: World (indestructible-feeling scenery) or Enemy (a target).
2. Implement `take_hit(damage: int, at: Vector3)` with a double-hit guard.
3. Add a `radius` property (aim assist, wingman fire tolerance, avoidance) and `signal destroyed`.
4. Join `targets` if wingmen can be ordered onto it, `obstacles` if AI should steer around it.
5. Award score with `get_tree().call_group("hud", "add_score", n)`.

### Add a HUD element
1. Write a `_draw_my_thing()` function in `hud.gd` and call it from `_draw()`.
2. For world markers, check `cam.is_position_behind()`, then `cam.unproject_position()`. Use `_draw_edge_arrow()` off screen only for rare, important things (the destroyer, Attack targets): routine positions belong on the radar.
3. Keep clear of the occupied corners: radar top left, bars top right, comms bottom left (on its own layer above the HUD), wing panel bottom right.

### Add a sound effect
See [8.17](#817-sound) for how the existing sounds are wired. Two patterns:
- **Sound that belongs to something that stays around** (an engine, a gun): add an `AudioStreamPlayer3D` child in its scene, fetch it in the script, call `play()`. Set `max_polyphony` if it can overlap itself.
- **Sound that must outlive what made it** (an explosion of something that's freed at once): `SoundFX.play_at(parent, stream, position, volume_db, pitch)`. Optional `size` and `reach` (the player's `unit_size` and `max_distance`, default 25 and 1200 m) make a sound carry farther (the warp portal uses its radius and 6000 m).

Put the audio file in `audio/sfx/`. A looping sound needs **Loop** ticked in the Import tab (then *Reimport*). Before sounds multiply, consider adding an `SFX` audio bus (*Audio* panel at the bottom of the editor) and a volume option in `Settings`.

### Change the ship model
The art is an imported model instanced under `Model` in `player/ship.tscn`; wingmen inherit it.

1. Put the model's folder (`.gltf` + `.bin` + textures, or a `.glb`) under `models/`, and let the editor import it (or run `--import`).
2. In `ship.tscn`, replace the `Model/Arwing` instance with the new one. Rotate it so its nose points along −Z and scale it to roughly 8 m wingspan (the Arwing needed −90° around Y and a scale of 0.0055).
3. Give it the `player/ship_model.gd` script, and set **Band Materials** to the names of the imported materials the pilot band should cross (`Material.002` and `Material.004` on the Arwing: the fins and their panels), then move `band_hub` and `band_radius` to the new model's fins (Model space).
4. Move `Model/MuzzleL` / `MuzzleR` to where the shots should leave, `Model/Glow` and `EngineLight` to the engine, and check `Model/Shield` and `CollisionShape3D` still roughly cover the hull.
5. Keep `Model`, the two muzzles, `Model/Shield` and −Z as forward: code relies on them. `Wingman._collect_meshes()` picks up the new meshes for the camera fade automatically.

Check the licence: the Arwing is CC-BY 4.0, which requires crediting its author (see `models/arwing_assault/license.txt`).

### Add music to a level
1. **Files:** put the audio in `audio/music/` (Ogg Vorbis is a good default). Looping in the import options isn't needed; `LevelMusic` loops the loop file itself. If the loop shouldn't repeat from its very start, set its loop offset in the import options.
2. **Track:** in the FileSystem dock, *New Resource → LevelMusic*, save it next to the files (for example `audio/music/corneria.tres`). Set `loop`, optionally `lead`, and `volume_db`.
3. **Use it:** select the root of the mission scene (`Main` in `main.tscn`, `Corneria` in `levels/corneria.tscn`) and drag the track onto `Music`. Setting it on `levels/level_base.tscn` would give every mission that doesn't override it the same track. The title screen root has the same export.
4. **Test:** run the scene and listen for the lead-to-loop switch. Headless tests can't hear it: with the dummy audio driver, streams never advance.

### Add a mission
1. **Scene:** in the editor, *Scene → New Inherited Scene* from `levels/level_base.tscn`, and save it under `levels/`. Rename the root.
2. **Override what differs:** environment and sun, the ships' start positions and intro markers (keep them clear of anything solid), `intro_line` (and optionally `intro_advisor_line`, Peppy's reply: `MissionControl.say()`), `spawn_enemies`. Wave settings go on its `EnemySpawner` (`destroyer_every = 0` for no destroyers).
3. **Add its world** as child nodes. A node that builds itself (like `Terrain` or `Clouds`) needs no level script. For an edge to the area, add a `PlayBoundary` node (`world/play_boundary.gd`) at its centre. If the level itself must generate things, give the root a script that `extends Level` and overrides `_build_world()`, as `main.gd` does.
4. **List it:** create a `Mission` resource in `missions/` (title, description, `scene_path`), and add it to the `missions` array on the `MissionSelect` node in `ui/title_screen.tscn`.
5. **Test:** open the scene and press F6, then try it through the title screen.

---

## 11. Testing and debugging

### Playing it
The quickest check is always to play. Open a mission scene (`main.tscn`, `levels/corneria.tscn`) and press F6 to skip the title screen and mission selector. While it runs, the editor's **Scene** dock has a **Remote** tab showing the live scene tree: click any node to see its current properties (an enemy's `state`, a wingman's `order` and `_assist`, the ship's `shields`).

`print()` writes to the editor's Output panel. `print_debug()` adds the file and line.

### Headless scenario scripts
The changes in this project were verified with throwaway scripts that run the real game with no window, drive it, and print results. That's worth reusing for anything with timing or AI involved. A complete example:

```gdscript
extends SceneTree
# Run: godot --headless --path . --fixed-fps 60 -s path/to/this_script.gd

var frame := 0


func _initialize() -> void:
	var main: Node = load("res://main.tscn").instantiate()
	root.add_child(main)
	current_scene = main


func _physics_process(_delta: float) -> bool:
	frame += 1
	if frame == 2:
		# Set up: skip the intro, hold the waves back.
		current_scene.get_node("IntroCutscene").skip()
		get_first_node_in_group("enemy_spawner").first_wave_delay = 99999.0
		var wing: WingCommand = get_first_node_in_group("wing_command")
		wing.order_weapons_free()
	if frame == 600:  # 10 s later at 60 fps
		var falco: Wingman = current_scene.get_node("Falco")
		print("PASS" if falco.order == Wingman.Order.WEAPONS_FREE else "FAIL", " Falco still on Weapons Free")
		return true  # quit
	return false
```

Tips:
- **`--fixed-fps 60`** makes every run deterministic in timing; `--headless` runs with no window or GPU.
- **Wrap runs in a timeout** if you script them (`timeout 120 godot ...`). A parse error in the test script can leave Godot waiting forever.
- Autoloads can't be referenced by name inside a `-s` script; use `root.get_node("Settings")`.
- Simulate input with `Input.action_press(&"fire")` / `Input.action_release(...)`, or `Input.parse_input_event(event)` for specific buttons.
- `EnemyFighter._enter_state(...)` forces a state; freeing `EnemySpawner` gives a controlled setup (note `Level` will then error trying to start it after the intro).
- Headless runs use a dummy audio driver: sounds "play" but never finish (SoundFX players still clean up through their backup timer).
- **Screenshots:** run *without* `--headless` (add `--resolution 1280x720`) and save `root.get_texture().get_image().save_png("shot.png")` from the script.

### Common errors
| Message | Usual cause |
|---|---|
| *Could not find type "X" in the current scope* | Class cache stale after adding a `class_name` script outside the editor: focus the editor or run `--import` |
| *Invalid get index 'x' (on base: 'previously freed')* | A stored reference to a node that's been freed: add an `is_instance_valid()` check |
| *Invalid call. Nonexistent function 'x' in base 'Nil'* | A `get_first_node_in_group` or `as` cast returned null |
| *Node not found: "Model/MuzzleL"* | A scene is missing a node a script expects with `$` or `@onready` |
| Changes to an Input Map action don't stick | `Settings` overwrites gameplay actions at startup: change `_default_bindings()` instead |

---

## 12. Gotchas

- **The level base reaches every mission.** A wingman's line, the spawner's wave sizes or the intro markers changed in `levels/level_base.tscn` change every mission that doesn't override them. To change one mission only, edit the node in that mission's scene.
- **Read the formation slot through `Wingman.slot_position()`.** It is `current_slot_offset()` (which includes the Cover Me trail) around the leader, raised above the ground and buildings on planets. Computing `leader.global_transform * slot_offset` yourself puts the slot underground when the player flies low.
- **Vertex colours aren't converted from sRGB.** Colours set with `SurfaceTool.set_color()` reach the shader as-is, unlike `source_color` uniforms, so code that builds coloured meshes (like `Terrain`) converts with `Color.srgb_to_linear()` first, or the colours come out washed out.

- **Enemy hurtboxes are areas.** A friendly raycast that should hit enemies needs layer 8 (`LAYER_HURTBOX`) in its mask, `collide_with_areas = true`, and `Hurtbox.resolve(hit.collider)` before using the collider; otherwise it gets the `Area3D`, which has no `take_hit` and isn't an `EnemyFighter`. A new enemy type that should be as easy to hit needs its own `Hurtbox` child.

- **The Input Map is overwritten.** See above: gameplay actions live in `settings.gd`.
- **Laser speed includes ship speed** (`laser_speed + speed`), and every lead-point calculation assumes the same. Keep them consistent if you change how bolts move.
- **Twin lasers assume two muzzles** (`_cannons[0]` and `[1]`; `parallel_fire` aims from the point between them).
- **The ship's materials are replaced at runtime.** `ShipModel` swaps the Arwing's imported materials for toon ones when the game starts, so the editor viewport shows the original smooth look. To change a colour, change it in code or the band exports, not in the imported materials. Reimporting the model (or changing its import settings) can rename meshes and materials; `band_materials` are matched by name.
- **Base scenes reach further than they look.** `wingman.tscn` inherits `ship.tscn` and `light_fighter.tscn` inherits `enemy_fighter.tscn`. A value set on the base applies to the child unless the child overrides it: give the player a new collision mask and the wingmen get it too; upgrade the "elite" and every level 1 enemy is upgraded. After changing a base scene, check the child scene and override there.
- **Neither you nor the wingmen are in the `obstacles` group,** so AI avoidance doesn't steer around friendly ships. Wingmen stay clear of each other through formation slots, pursuit staggering and crowd checks, and clear of you through formation flight and, on Weapons Free, `_steer_clear_of_leader()`. A new friendly AI behaviour needs its own way of staying clear.
- **Wingmen and enemies only see the player.** Enemies never target wingmen; nothing damages wingmen. Destroyer turrets shoot at wingmen only when you're out of range, for show.
- **Destroyed destroyer parts stay in the scene.** Use `Wingman.target_gone()` or check `is_destroyed`, not just `is_instance_valid()`.
- **`queue_free()` takes effect at the end of the frame.** Within the same frame the node still exists; `is_queued_for_deletion()` tells you. The spawner waits a frame before counting enemies for this reason.
- **Transparent things have no outlines.** Anything using transparency (including fades) loses its ink lines while transparent.
- **The toon shadow floor is sun-only.** Don't apply it to omni or spot lights.
- **Physics interpolation is off.** Ships and camera update at 60 Hz, so very high refresh-rate monitors may show slight judder.
- **The asteroid field is seeded.** Same layout every run (apart from the intro lane); change `field_seed` for a different one.
- **AI obstacle avoidance knows spheres and boxes.** Cover large non-spherical things with `ObstacleProxy` spheres or, for big blocky shapes, `ObstacleBox` boxes (a few boxes replace hundreds of spheres; every AI ship checks every obstacle every frame).
- **A destroyer's off-screen arrow can hide under the comms box** when it points bottom left.
- **Editing `project.godot` by hand while the editor is open:** reload the project (*Project → Reload Current Project*) before saving anything in the editor, or it may overwrite your change.

---

## 13. Where to start contributing

A suggested path, each step a bit bigger than the last. Each touches a different system, so by the end you'll have worked in most of the codebase.

1. **Tune by feel.** Change the radar range or size (`HUD → radar_range`, `radar_radius`), Slippy's `slot_offset`, or the light fighter's `fire_interval`, and play. *Touches: exports, scenes.*
2. **Add an acknowledgement.** Add a third line to a character's `acknowledgements` (open `comms/speakers/falco.tres`, `slippy.tres` or `krystal.tres`). *Touches: comms, exports.*
3. **Shields-down callout.** When your shields are knocked out, have a wingman say a HIGH-priority warning (see the comms recipe; the `shields_depleted` signal already exists). *Touches: signals, comms.*
4. **A new weapon.** Make a heavy laser with a different color, more damage, and slower fire rate, and equip it on the destroyer's turrets. *Touches: inheritance, scenes, weapons.*
5. **A volume setting.** Add an audio bus for comms, a volume slider to the settings screen, and save it in `Settings`. *Touches: settings, menus, audio.*
6. **A wave counter callout or end condition.** For example, a comms line at each new wave, or a "mission complete" after the first destroyer dies. *Touches: spawner, main flow, HUD or comms.*
7. **A new enemy type**, such as a slow bomber with more health that ignores the player and heads for the centre. *Touches: inheritance, AI, spawner.*

---

## 14. Glossary

| Term | Meaning here |
|---|---|
| **Fox** | The player's call sign |
| **Aim point** | Where a fighter's bolts are aimed this frame (`Fighter.aim_point`) |
| **Assist** | How strongly formation flight applies to a wingman, 0..1 (`Wingman._assist`) |
| **Autoload** | A node Godot creates at startup and keeps across scenes (`Settings`, `SceneFader`, `Music`) |
| **Break / break side** | Pulling away after an attack run; which way a wingman pulls (`break_side`) |
| **Twin lasers** | Bolts flying parallel to the crosshair line, one from each muzzle (`parallel_fire`) |
| **Engage** | What an AI pilot is shooting at this frame (`AIPilot._engage`) |
| **Fire target** | What you've been hitting recently; wingmen in formation join in (`Ship.fire_target`) |
| **Formation flight** | The wingman assist that turns and slides with the slot near formation |
| **In formation** | Within 10 m and 20° of the slot (`Wingman.is_in_formation()`); required to fire with you |
| **Lead point** | Where a moving target will be when a bolt arrives |
| **Order / standing order** | What you told a wingman / what it returns to after an Attack |
| **Pilot interface** | The overridable `_get_*` / `_wants_*` functions `Fighter` asks each tick |
| **Proxy** | An invisible sphere the AI avoids (`ObstacleProxy`); `ObstacleBox` is the box version |
| **Slot** | A wingman's formation position in your local space (`slot_offset`) |
| **Speaker** | A comms character resource (`CommsSpeaker`) |
| **Pilot** | A `CommsSpeaker` that flies: accent colour + battle lines (`comms/pilot.gd`), set as a wingman's `speaker` |
| **State** | What a wingman is physically doing (FOLLOW / ATTACK), or an enemy's AI state |
| **Threat** | An enemy currently chasing you (`WingCommand.threats()`) |
