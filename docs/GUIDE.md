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

1. **Title screen** → Start opens the **mission selector** → picking a mission fades into its level (Asteroid Field or Corneria).
2. **Intro cutscene:** the formation flies past a fixed camera, Fox says *"We're approaching the combat zone."* on the comms, and the camera swoops in behind you.
3. **Waves:** enemy fighters arrive in waves that grow from 3 to 8 fighters. Every 5th wave a **destroyer** (capital ship) also arrives, launches more fighters and shoots with hull turrets. One wingman calls it out on the comms.
4. **Orders:** you select wingmen with the D-pad (or 1–4) and give orders: **Attack** your target, **Cover Me**, **Form Up**, or **Weapons Free**. A wingman acknowledges on the comms.
5. **Death:** your shields absorb every hit until they're knocked out; the next hit destroys you. After 3 s the level restarts, skipping the intro.

There's no win condition yet: the waves are endless.

**What's on screen:** the radar (top left), shield and boost bars (top right), the comms box (bottom left), the wing panel (bottom right), and markers over enemies, wingmen and their targets.

---

## 3. Godot concepts this project uses

This is a Godot **4.7** project written in **GDScript**. If you know another engine or language, most of this will feel familiar; this section is about the parts that are specific to Godot and how this project uses them. The official docs are excellent and searchable: <https://docs.godotengine.org/en/stable/>.

### Nodes, scenes and instancing
Everything in a running game is a **node** in a single tree. A node has a type (`Node3D`, `CharacterBody3D`, `Camera3D`, `Label`...) and can have children. A **scene** (`.tscn` file) is a saved branch of nodes. Scenes can contain other scenes: that's **instancing**.

- `player/ship.tscn` is the player's ship: a body, a collision shape, a model (an instance of the imported Arwing scene, `models/arwing_assault/scene.gltf`), two muzzle markers, an engine glow and light, and a shield bubble.
- `wing/wingman.tscn` **inherits** `ship.tscn` (it's an instance of it with a different script and a few overrides), so wingmen use exactly the same model.
- `levels/level_base.tscn` holds everything every mission shares: the ship, the three wingmen, the HUD, the comms, the pause menu, the intro and so on. Each mission's scene **inherits** it and adds its own world: `main.tscn` (Asteroid Field) adds the asteroids and space dust, `levels/corneria.tscn` adds the Corneria map (terrain and props) and clouds. See [8.18](#818-missions-and-levels).

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
Shaders are small GPU programs, written in Godot's GLSL-like shading language (`.gdshader`). This project has four: toon lighting, ink outlines, the shield bubble and the procedural sky. See [section 8.15](#815-visual-style).

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
main.tscn / main.gd      The Asteroid Field mission (inherits levels/level_base.tscn): the asteroid field
levels/                  The shared level base (level_base.tscn + Level script) and other missions (corneria.tscn)
missions/                Mission resources listed by the mission selector
player/                  The player's ship, the shared flight model, the chase camera
ai/                      Shared AI brain for every computer-flown ship
wing/                    Wingmen and the order system
enemies/                 Enemy fighters, waves, the destroyer and its parts
weapons/                 Laser bolts (one script, three scenes)
world/                   Asteroids, the intro cutscene, speed dust, the sky; planet terrain (and TerrainMap, MapProps), clouds, the play boundary, the Great Fox
effects/                 Explosions, muzzle flashes, one-shot sounds, the shield bubble, toon shading, ink outlines
audio/                   Sound effects (audio/sfx/), level music (LevelMusic + the Music autoload)
models/                  3D models: the Arwing (player and wingmen), the Great Fox scenery, the destroyer, the enemy fighter and the Corneria map (ours; each built by a Blender script in its source/ folder)
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

Node3D: Laser, Impact, ObstacleProxy        Node: WingCommand, EnemySpawner, IntroCutscene
CanvasLayer: Comms, PauseMenu, SceneFader   Control: HUD overlay, SettingsMenu
Resource: CommsSpeaker, Pilot (extends CommsSpeaker), LevelMusic, Mission
```

Note that a **wingman is a subclass of `AIPilot`, not of `Ship`**, even though its scene inherits `ship.tscn`. The scene gives it the same body and model; the script gives it a different brain.

### A level's scene tree (the Asteroid Field)

```
Main (main.gd, extends Level)       inherits levels/level_base.tscn; everything below comes from the base except ★
├── WorldEnvironment, Sun          lighting and sky
├── Ship (ship.tscn)               you
├── ChaseCamera (chase_camera.gd)
│   └── InkOutline                 full-screen outline pass
├── SpaceDust ★                    speed streaks
├── Asteroids ★                    filled in by main.gd's _build_world()
├── PlayBoundary ★                 edge of the area, radius 1000 m (play_boundary.gd)
├── GreatFox ★                     the team mothership, scenery behind the intro start (great_fox.tscn)
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
   | `obstacles` | asteroids, enemies, destroyer `ObstacleProxy` spheres | AI obstacle avoidance |
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

**4. The gun fires.** `Fighter._update_weapons` counts down a cooldown (`fire_interval`, 0.11 s) and, if `_wants_fire()` (which returns `is_firing` for the ship), calls `_fire()`, which plays the ship's `FireSound` (see [8.17](#817-sound)). Muzzles alternate left and right.

**5. The bolt is launched.** `_fire()` instantiates `laser_scene` (`weapons/laser.tscn`) and adds it to the level. Because the ship has `parallel_fire` on, the bolt's direction is the line from the point between the two muzzles to the aim point, so it leaves its muzzle (at the root of the blue fins) **parallel** to that line: twin lasers, as in *Star Fox 64* (see [8.1](#81-the-flight-model-fighter)). It calls `Laser.launch(origin, direction, speed, shooter)`; the bolt's speed is `laser_speed + speed`, so it inherits the ship's speed. With `muzzle_flash_size` above 0, `MuzzleFlash.spawn()` puts a 70 ms flash on the muzzle.

**6. The bolt flies and checks for hits.** Each physics tick, [laser.gd](../weapons/laser.gd) moves the bolt by `velocity × delta`, and **raycasts along that step** (so a fast bolt can't skip through a thin object between frames). It then stretches its glowing mesh behind it (`trail_length`, 8 m on `laser.tscn`), never longer than the distance it has flown so far, so the streak starts at the muzzle instead of poking back through the ship. The ray uses the bolt's `collision_mask`: player bolts (mask 5) hit World + Enemy, never Friendly.

**7. The hit lands.** If the ray hits something, `_cast()`:
- calls `notify_shot(origin)` on it if it has that method (enemy fighters use it to start evading; your ship records it for the HUD's hit-direction arc),
- if the hit destroyed it, calls `notify_kill(victim)` on the shooter if the shooter has that method and still exists (wingmen use it for kill celebrations and the Weapons Free cooldown; the player's ship for wingman praise),
- calls `take_hit(damage, position)` on it if it has that method,
- spawns an `Impact` flash, and frees the bolt.

**8. The enemy takes damage.** [enemy_fighter.gd](../enemies/enemy_fighter.gd) `take_hit` subtracts health. At 0 it spawns a big `Impact`, plays its explosion sound through `SoundFX.play_at()`, calls `get_tree().call_group("hud", "add_score", 1)`, emits `destroyed`, and `queue_free()`s itself (removed at the end of the frame).

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
_update_speed          throttle / boost → speed
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

**Speed.** `_get_target_speed()` is clamped between `min_speed` and `boost_speed`. Boost overrides it while `boost_energy` lasts (2.5 s of boost from full, refilling over 4 s, but only while boost is released). Acceleration is faster when boosting or above max speed.

**`_velocity_offset()`** adds velocity on top of "fly along the nose". It's zero for everyone except wingmen in formation, who use it to slide a little sideways to hold their slot (see [8.8](#88-wingmen)).

**The pilot interface** (override these in a subclass):

| Function | Returns |
|---|---|
| `_think(delta)` | (nothing) runs first each tick |
| `_get_stick() -> Vector2` | x = yaw right, y = pitch down, each −1..1 |
| `_get_roll() -> float` | positive rolls left; 0 = auto-level |
| `_get_target_speed() -> float` | desired speed |
| `_wants_boost() -> bool`, `_wants_fire() -> bool` | |
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

**Throttle** (`throttle_up` / `throttle_down`) maps −1..1 onto min..cruise..max speed. **Roll** is `roll_left` / `roll_right`. **`controls_enabled = false`** (used by the intro) zeroes all input and flies at `autopilot_speed`.

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

The camera sits at `offset` (2.6 m up, 11 m back) in a *lagging copy* of the ship's orientation. Each tick, `_basis` slerps towards the ship's basis by `1 − exp(−follow_sharpness × delta)`, so in a turn the camera swings a little behind, which makes turns feel weighty. It looks at a point 30 m ahead of the ship. Above cruise speed it pulls back (`boost_pullback` per unit of speed), and while boosting the FOV widens from 70° to 84°.

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
if we just scraped something:      steer away from its surface for 0.8 s
_stick = _steer_towards(goal)      world point → stick deflection
if lead_turns and engaging:        add _tracking_stick(target)
```

`_decide()` also sets four fields that the rest of the pipeline reads: `_target_speed`, `_engage` (what to shoot at, or null), `_level_up`, and through `_aim()`, `_firing`.

**Steering** (`_steer_towards`): convert the goal into the ship's local space; the x/y of the normalised direction, times `steer_gain`, is the stick. If the goal is behind, turn as hard as possible.

**Shooting** (`_aim`): if `_engage` is set, aim at its **lead point** (where it will be when a bolt gets there: `position + velocity × distance / bolt_speed`) and fire when the nose is within `fire_tolerance_deg` plus the target's angular size, inside `attack_range`. `aim_scatter` (metres) then moves the aim point randomly by up to that much in each axis, so even a perfectly lined-up pilot misses some shots: 4 on wingmen, 2 on elite fighters, 0 on light fighters. Otherwise fire only if `_wants_idle_fire()` (wingmen use this to fire along with you).

**Attack runs** (`_attack_goal(target, side)`) have two behaviours depending on the target:
- **Fighters:** sit `pursuit_distance` (50 m) behind and match speed, closing distance only when roughly facing the target (otherwise it orbits). Break off if too close or meeting head-on.
- **Anything else** (asteroids, destroyer parts): full-speed **strafing runs**. Approach, fire, and at `break_distance` from its surface, break away to a waypoint to the side and up, fly out, then turn in again.

Breaking off uses a two-phase pattern: `APPROACH` and `BREAK`. In `BREAK`, the AI flies to `_waypoint` until it gets there or `_waypoint_timeout` runs out, then switches back to `APPROACH`. `_fly_to_then_attack(point, timeout)` starts a BREAK on purpose; wingmen use it for the opening split and for peeling off when crowded.

**Obstacle avoidance** (`_avoid_obstacles`): looks along the current flight path for `avoid_lookahead_time` (1.5 s) of travel. For the nearest member of `obstacles` whose sphere (radius × 1.3 + margin) crosses that path, it replaces the goal with a point skirting its near side. While attacking, obstacles beyond the target are ignored (the run breaks off before reaching them). Everything is treated as a **sphere**, which is why the destroyer hull is covered in invisible `ObstacleProxy` spheres.

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

**File:** [weapons/laser.gd](../weapons/laser.gd); scenes [laser.tscn](../weapons/laser.tscn) (player and wingmen, green; speed is `laser_speed` on `ship.tscn`, 500 m/s; 8 m `trail_length`), [enemy_laser.tscn](../weapons/enemy_laser.tscn) (red, 4 damage, 250 m/s from `enemy_fighter.tscn`), [turret_laser.tscn](../weapons/turret_laser.tscn) (red, bigger, slower, 8 damage, 3 s lifetime)

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

A bolt also excludes its shooter's RID from its raycasts so it can't hit the ship that fired it. Bolts move in straight lines and free themselves after `lifetime`. With `trail_length` above 0 (8 m on `laser.tscn`, about one frame of travel), the `Bolt` mesh is stretched behind the bolt's position and grows from the muzzle over the first frames, so a fast bolt reads as a continuous streak; enemy and turret bolts keep their modelled mesh.

### 8.7 Waves and the spawner

**File:** [enemies/enemy_spawner.gd](../enemies/enemy_spawner.gd)

- `start()` (called by `Level._begin_play()` when you get control, if the mission's `spawn_enemies` is on) schedules wave 1 after `first_wave_delay`.
- Each wave: `first_wave_size + (wave − 1) × wave_growth` fighters, capped at `max_wave_size` (8) and by `fighter_room()`. They appear `spawn_distance` (600 m) away, roughly ahead of you, and patrol around that point, so you usually find them before they find you.
- Every `destroyer_every`-th wave (5, 10, 15...) also spawns a destroyer at the edge of the zone (1000 m from the centre) if none is alive, and asks `WingCommand` to announce it. `destroyer_every = 0` means never (Corneria).
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
- **Formation flight eases in.** Its pull towards the slot (`_slot_pull`, used by `_formation_velocity()`) is capped by the same braking curve. It can only build up or change at `slot_pull_rate` (45 m/s²), and while formation flight is off it's kept equal to the wingman's actual motion relative to the slot, so engaging it changes nothing at first. Formation flight also only fades in while the wingman's nose is within about 37–73° of the leader's heading (`ASSIST_MIN_ALIGNMENT` / `ASSIST_FULL_ALIGNMENT`). That way it never drags a wingman around mid-turn. In formation the heading stays within about 20°.
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

- `_assist` (0..1) is how strongly it applies: full within 25 m of the slot, fading to 0 by 70 m, blended in and out over time so joining looks like a quick settle. It drops to 0 at once when the wingman gets an attack state, is dodging an obstacle, or is on Weapons Free. Ground avoidance doesn't drop it (see Formation near the ground below).
- **Rotation** (`_update_rotation` override): after the normal stick-driven turn, the heading is slerped towards the follow goal with the leader's roll, and the leader's current spin is *anticipated* so the wingman turns with you instead of after you. Since that turn bypasses the stick, the override also measures how far the ship actually turned (`_turn_rates`) and the model banks with that, scaled to the leader's turn rates while in formation: before this, wingmen flew your turns perfectly level.
- **Velocity** (`_velocity_offset` override): the wingman moves with the slot's measured velocity plus a spring towards it (`slot_spring`), capped at `max_slot_correction`. This lets it slide sideways or brake a little, which a nose-forward flight model can't do on its own.
- `velocity_heading_blend` points the nose partly along the direction of travel, hiding most of the sideways slide.

`formation_flight = false` turns it off and the wingman flies like any other AI ship (useful for comparing).

#### Formation near the ground
On a planet, flying low would put the slots below you (Falco's and Krystal's are 1.5 m down) into the ground. `slot_position()` is the slot in the world, and on a planet mission it is raised to at least `formation_ground_clearance` (6 m) above the ground or water, both under the slot and `formation_ground_lookahead` (1 s) of your flight ahead of it, so the slot starts climbing before a rise. All formation code reads the slot through `slot_position()`. Near the slot (`_near_slot()`), a wingman also uses that 6 m clearance and the 1 s look-ahead for its own ground check instead of the AI's 25 m and 2 s, and the ground check doesn't switch formation flight off.

Why it's built this way (measured with you flying 15 m above the hills): with the normal 25 m / 2 s ground check, and formation flight letting go whenever it fired, wingmen held formation only 77% of the time on Form Up, because every rise you were about to climb over pulled them out. Shortening the check got formation back to 97% but they scraped the ground 1–3 times a minute, mostly where they had to climb a slope by themselves. Raising the slot ahead of rises, and keeping formation flight on, gives 99% in formation and about 0.1 scrapes a minute. Remaining scrapes come when you yourself fly into the ground or bounce off it.

#### Formation fire
Wingmen only fire with you on **Form Up**, and only when `is_in_formation()`: within 10 m of the slot and pointing within 20° of your heading (`_joins_leader_fire()`). That stops a wingman that's out of position from spraying shots across the formation. Covering wingmen never join in: Cover Me trades your wing's firepower for defence.

#### Shared targets
Two wingmen chasing the same fighter would settle into the same spot behind it and block each other. So a wingman gives way to any **senior** (lower `wing_index`) on the same target: it hangs back `pursuit_stagger` (30 m) per senior (`_pursuit_offset()`), and if it still ends up within `crowd_distance` of one for `crowd_time`, it peels off and comes back from another angle (`_check_crowding()`).

#### Weapons Free
`_free_goal()`:
1. Look for a target (`_pick_free_target()`): enemy fighters within `free_detect_range` of the wingman *and* `free_engage_radius` of you. Any untaken enemy beats any taken one (score = distance + 10000 × wingmen already on it).
2. If there's none: if farther than `free_leash` (325 m) from you, head back; otherwise fly to a roam point. Roam points are random spots within `free_roam_radius` (208 m), mostly ahead of you, stored *in your local space* so they move with you. `_steer_clear_of_leader()` keeps the route from passing through your ship (you're not an AI obstacle).
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

**Comms lines.** Each character's `acknowledgements`, `destroyer_callout`, `celebrations`, `praise` and `celebration_chance` live in their `Pilot` file (`comms/speakers/falco.tres`...), so every character has its own voice, the same in every mission. `_acknowledge()` avoids repeating a wingman's last line; `announce_destroyer()` avoids repeating the last caller, tracked in a `static var` so it survives level restarts. **Kill celebrations** are in `Wingman.notify_kill()`: when a wingman's shot destroys an enemy fighter (rocks and destroyer parts don't count), it says a random line from its pilot's `celebrations` with `celebration_chance` (25%), never while on Form Up, at low priority. **Praise for your kills:** `Ship.notify_kill()` calls `WingCommand.praise_player_kill()` when your shot destroys an enemy fighter. A random wingman, with its pilot's `celebration_chance` (the same 25%), says one of its `praise` lines (Falco "Nice shot, Fox!", Slippy "Way to go, Fox!", Krystal "Nice flying, captain!"...), never the same line twice in a row, at low priority. Unlike their own celebrations this happens on any order, Form Up included. Measured: 24–26% of 2,000 simulated kills, spread over all three wingmen. A kill by a wingman's bolt fired alongside yours in formation counts as theirs, not yours.

### 8.10 The destroyer

**Files:** [enemies/destroyer.gd](../enemies/destroyer.gd), [destroyer_part.gd](../enemies/destroyer_part.gd), [destroyer_turret.gd](../enemies/destroyer_turret.gd), [destroyer_hangar.gd](../enemies/destroyer_hangar.gd), [obstacle_proxy.gd](../enemies/obstacle_proxy.gd); scene [destroyer.tscn](../enemies/destroyer.tscn); model [models/destroyer/](../models/destroyer/)

**The model.** A broad armoured body splitting into two blade prongs (with an open gap between them and a glowing emitter at their root), a raised deck, a bridge tower with a flared neck under the bridge, an engine block with three thrusters, and hangar housings on both flanks. It's about 368 m long and 175 m wide (1.5× the old box-built wedge), dark gunmetal with crimson bands, amber windows and red-orange engines. It's our own design, built from code: [build_destroyer.py](../models/destroyer/source/build_destroyer.py) runs in Blender (Scripting tab, the Blender MCP, or `blender --background --python build_destroyer.py -- --export`) and exports four `.glb` files next to it:

| File | What | Pivot |
|---|---|---|
| `destroyer_hull.glb` | everything that isn't a part | ship origin |
| `destroyer_bridge.glb` | bridge block, windows, sensor domes, antenna | `BRIDGE_POS` (0, 75, 120) |
| `destroyer_thruster.glb` | one thruster (used three times), nozzle towards +Z | the nozzle centre |
| `destroyer_hangar_door.glb` | one door, stripes facing −X (the right door is turned 180°) | the door centre |

Everything in the script is in game coordinates (−Z is the bow), so its numbers match `destroyer.tscn`. Its colours are the **sRGB values the game ends up with**: the script converts them to the linear values Blender and glTF store. They're deliberately dark because the toon light is bright (the old hull's 0.46 grey rendered near-white). It also writes `collision.txt`, the hull's convex collision pieces ready to paste into `destroyer.tscn`. **If you change the shape, re-export, paste the new collision pieces, and update `hull_outline` / `extra_proxies` and any part positions in the scene.** `Destroyer._ready()` cel-shades the imported materials with `ToonMaterial`, like the Great Fox; the editor shows the originals.

**Structure.** The hull is the `AnimatableBody3D` root, on the World layer: it blocks shots, sight and ships, but can't be damaged. Its collision is eight convex pieces (body, both prongs, keel, deck, superstructure, tower, neck) plus boxes for the engine block and hangar housings. Damage goes to **parts**, separate `StaticBody3D` children on the Enemy layer, each holding its model as a `Model` child:

| Part | Count | Health | Score | Notes |
|---|---|---|---|---|
| Bridge | 1 | 70 | 3 | Must die to kill the ship. `radius` 27 |
| Thruster | 3 | 46 | 2 | Must all die to kill the ship; each lost one slows it. `radius` 15 |
| Hangar door | 2 | 29 | 2 | Blown off → no more launches from that side. `radius` 15; slides up `open_height` 19.5 m |
| Turret | 8 | 12 | 1 | Disabled when destroyed. `radius` 6; 1.5× the old size, gunmetal |
| The destroyer itself | | | +10 | |

Health didn't change with the 1.5× scale-up: bigger parts are just easier to hit, in the player's favour. `radius` (aim assist, wingman fire tolerance, HUD brackets) grew with them.

`Destroyer._ready()` finds every `DestroyerPart` below it and sorts them into `bridge`, `thrusters`, `turrets`, `hangars`. When any part emits `destroyed`, `_on_part_destroyed` checks the **kill rule**: bridge destroyed and no thrusters left → `_die()`, a chain of 14 explosions scattered over the hull (`_random_hull_point()`, inside `hull_outline`), a final blast, a fade-out, then `destroyed` and `queue_free()`.

A destroyed part stays in place, charred (`_char_meshes`), with its lights out and a dim ember light, and leaves the `targets` group. Parts ignore hits until `destroyer.is_vulnerable()` (fully faded in and not dying).

**Life cycle.**
1. `arrive(destination)`: face the centre, tween visibility 0 → 1 over 4 s (every mesh's `transparency` and every light's energy), then `_activate()`.
2. Crawl towards the centre at `cruise_speed × (0.25 + 0.75 × fraction of thrusters intact)`, stopping `stop_distance` short (300 m in `destroyer.tscn`, so the bigger hull doesn't park over the middle; the script default is 200). Asteroids in its path are `shatter()`ed (no score).
3. Every `launch_interval` (40 s, first after 15 s), launch a squadron from the next intact hangar, within the fighter cap; if there's no room, retry in 5 s.

**Turrets** pick the player if within `aggro_range` (450 m), else the nearest wingman in range (for show: wingmen can't be hurt). They turn at `turn_rate`, can only pitch from −5° to 80° (blind spots), need their barrels lined up within 3°, and need a clear line of fire past the hull and asteroids.

**Hangars** run their launch as a coroutine: door slides up (tween), fighters spawn at the launch marker one by one with `begin_launch()`, door closes.

**Obstacle proxies.** AI avoidance sees only spheres, so `_build_obstacle_proxies()` fills `hull_outline` (the hull seen from above, (x, z) points, set in `destroyer.tscn`) with a grid of `proxy_radius` (16 m) spheres every `proxy_spacing` (20 m across, 25 m along), keeping only the points inside the outline. On top come `extra_proxies` (the bridge tower and superstructure, the hangar housings) and one per thruster: 89 spheres in all. The gap between the prongs has no spheres. It's open for the player to fly through, but the avoidance margin (radius × 1.3 + 6 m) still makes the AI treat it as closed.

**Wingmen against it** (Attack orders on a turret, the bridge and the centre thruster, 4 runs each; the old ship's numbers from the same test in brackets): turret 3.6–4.1 s (4.1–5.2), bridge 5.9–6.4 s with no hull contact (13.6–38.8 s, scraping the hull in 2 runs), centre thruster 18–33 s (38–46 s, or not killed in 60 s in 2 runs). The centre thruster is still the hard one: sitting between the other two behind the engine block, wingmen scrape the hull in 3 runs out of 4 (mostly a few frames, once 83).

**`sync_to_physics` is off** because the destroyer moves itself outside the physics step in places (`arrive()`); with sync on, the physics server would overwrite those transforms.

### 8.11 Asteroids

**File:** [world/asteroid.gd](../world/asteroid.gd); the field is created in [main.gd](../main.gd)

`main.gd` scatters 160 asteroids with a **seeded** random generator (`field_seed`), so the field is the same every run. Sizes skew small (radius 3–28 m). Positions are kept out of the intro's flight lane and camera spot (`_blocks_intro`), because ships on autopilot don't dodge.

Each asteroid builds its look on first use: 8 lumpy mesh variants made by pushing a low-poly sphere's vertices in and out with noise, shared by every asteroid (`static var _meshes`). Each instance picks one, scales and rotates it randomly, and spins only the visual (the collision sphere doesn't need to). Health is `1 + int(radius / 4)`. `shatter()` destroys it without awarding score. Asteroids set `highlight_on_crosshair` and `attack_target` to false: the crosshair doesn't turn red over them and the Attack order can't pick them (they still stop shots and can still be shot).

### 8.12 The HUD

**File:** [ui/hud.gd](../ui/hud.gd), scene [ui/hud.tscn](../ui/hud.tscn)

`hud.tscn` is a CanvasLayer with one full-screen `Control` running `hud.gd`. That script finds the ship, wing command and destroyer in `_process`, calls `queue_redraw()` every frame, and draws everything in `_draw()`:

| Element | Function | Where |
|---|---|---|
| Damage flash, "SHIELDS DOWN", "SHIP DESTROYED" | `_draw()` | full screen / centre |
| Smoothed crosshair (red over a target, not over asteroids) | `_draw_reticle` | centre |
| "RETURN TO THE COMBAT AREA" / "TURNING BACK" (planet missions, see [8.19](#819-planet-terrain-corneria)) | `_draw_boundary_warning` | top centre |
| Destroyer warning, part brackets, edge arrow | `_draw_destroyer` | |
| Enemy brackets (one colour, whatever the AI state), only where useful: within `enemy_marker_radius` (320 px, set in `hud.tscn`; script default 180) of the crosshair, popping in and out at that edge with no fade (a combat-visor feel), and never while terrain, an asteroid or the destroyer hides the enemy from the camera, so brackets don't see through cover (`hide_hidden_enemies`; one World-layer ray per enemy from the camera each physics tick, `_update_hidden_enemies`). Clouds have no collision, so enemies in clouds keep their brackets. No arrows off screen, that's the radar's job | `_draw_enemies` | |
| Hit-direction arc: red, around the centre, on the side a shot came from | `_draw_hit_direction` | centre |
| Wingman markers: solid downward triangles in their colour, bold white initial (`WINGMAN_MARKER_SIZE` 36 × 29 px, letter `WINGMAN_INITIAL_SIZE` 15; ×1.4 when selected). Drawn once per wingman and state into a texture by a one-shot `SubViewport` at the screen's real resolution (`_wingman_marker()`, redrawn after a window resize); each frame only places it | `_draw_wingmen` | |
| Diamonds on targets of Attack orders | `_draw_order_markers` | |
| Radar | `_draw_radar` | top left |
| Mouse steering cursor (hidden on gamepad) | `_draw_stick_cursor` | centre |
| Shield and boost bars | `_draw_gauges` | top right |
| Wing panel (call sign + an icon for the current order per wingman) | `_draw_wing_panel`, `_draw_wing_card`, `_draw_order_icon` | bottom right |

**Projecting world positions to the screen:** `cam.unproject_position(world_pos)` gives the pixel; check `cam.is_position_behind(world_pos)` first, because points behind the camera project to nonsense. Off-screen things get `_draw_edge_arrow()`, which works in camera space so even things behind you point the right way.

**The radar** (size `radar_radius`, 80 px; range `radar_range`, 500 m; both HUD exports) works in the ship's local space (`_ship.global_transform.affine_inverse() * position`), plotting x (right) and z (back) so ahead is up and it rolls with you. `_radar_height()` decides ▲ / ▼ / ■ with a 15° band (or 10 m up close). Wingmen in formation would land on your icon at 500 m scale, so they're pushed out to at least 9 px in their real direction. Enemies beyond `radar_range` are pinned to the rim as small dim dots (`RADAR_FAR_DOT`) in their direction, so a far-off wave can still be found. **Off-screen enemies get no edge arrow**: with one, the radar was pointless. Edge arrows remain for the destroyer and for targets of Attack orders, which are few and chosen.

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
`say()` returns false if the line was dropped. `speaker` is a `CommsSpeaker`; every `Fighter` has a `speaker` export (Fox on `ship.tscn`, each wingman overridden in `levels/level_base.tscn`). **Characters** live in `comms/speakers/`, one file each. A `Pilot` (`comms/pilot.gd`) is a `CommsSpeaker` plus what a wingman needs: `accent_color` and the *Lines* group (`acknowledgements`, `destroyer_callout`, `celebrations`, `celebration_chance`). To edit what Falco says, open `falco.tres`; to add a wingman character, create a new `Pilot` resource and set it as the wingman node's `speaker`.

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

Typing starts only when the box is fully open, and a recorded line's audio starts with the typing. Closing runs `_open_t` back down, so it's the same steps in reverse: the box folds back as the portrait gives way to static, then the square collapses to a line and hides. The square and box animate their size (not `scale`, which would squash the borders) and clip their contents, so the text is cut off rather than squeezed while the box unfolds.

**Static** is a `ColorRect` with [comms/static.gdshader](../comms/static.gdshader): coarse blocks mixed with fine grain, re-rolled 30 times a second, thin scanlines and a rolling bright band, tinted towards the speaker's colour. Its clock is fed from `_process` instead of the shader's `TIME`, so it freezes while the game is paused. Speakers without a `portrait` (all of them, for now) show faint static (`empty_portrait_static`, 30%) in its place.

**Priority rules:**
- Nothing on screen → the line plays (the box opens).
- A **LOW** line arriving while anything's on screen → dropped, except while the box is closing with nothing queued.
- A **HIGH** line arriving during a LOW line → interrupts it at once. From the **same speaker**, the new line simply starts typing. From a **different speaker** with the box open, the portrait shows static for `noise_time` (`SWITCHING`) while the box stays open, then the new line types. During opening, the line is just swapped in.
- A **HIGH** line arriving during a HIGH line → queued.
- **A queued line, or one arriving while the box closes,** turns the closing box around once it's folded back to static (`_open_t` at `expand_time`): the next speaker comes in through the static without the square collapsing.

**Details worth knowing:**
- The box is built in code (`_build()`): Panels with `StyleBoxFlat`s, a `TextureRect` for the portrait, a `ColorRect` for the static, Labels for name and text.
- The text label uses `VC_CHARS_AFTER_SHAPING`, so the whole line is laid out and wrapped up front and words don't jump to the next line mid-typing.
- **Beeps** are generated in code (`_make_beep()`): a 45 ms soft square wave built sample by sample into an `AudioStreamWAV`. They play on every `beep_every`-th letter at the speaker's `beep_pitch` (Slippy lowest, Krystal highest), skipping spaces and punctuation.
- **Recorded lines** play instead of beeps, and the line holds until the recording's length has passed. That's timed in code rather than read from the audio player, so a missing audio device can't freeze a line on screen.
- It's its own CanvasLayer (layer 5), so it shows during the intro while the HUD is hidden, and it pauses with the game.

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

**Files:** [effects/toon.gdshader](../effects/toon.gdshader), [player/ship_model.gd](../player/ship_model.gd), [effects/ink_outline.gdshader](../effects/ink_outline.gdshader) + [ink_outline.gd](../effects/ink_outline.gd), [effects/shield.gdshader](../effects/shield.gdshader) + [shield_effect.gd](../effects/shield_effect.gd), [world/space_sky.gdshader](../world/space_sky.gdshader), [world/space_environment.tres](../world/space_environment.tres), [world/space_dust.gd](../world/space_dust.gd), [effects/impact.gd](../effects/impact.gd), [effects/muzzle_flash.gd](../effects/muzzle_flash.gd)

**Font.** All text (menus, comms box, HUD) uses one fixed-width font, *Share Tech Mono* ([ui/fonts/](../ui/fonts/), SIL Open Font License: keep `OFL.txt` beside it). It is set once as the project font (`gui/theme/custom_font` in `project.godot`, Project Settings → GUI → Theme → Custom Font), so every `Label`, `Button` and dropdown picks it up without touching `menu_theme.tres`. The HUD draws its text in code, so it takes the same font with `get_theme_default_font()` in `_ready()`. The wingman initials use a bold version made from it at runtime (a `FontVariation` with `variation_embolden`), since the font has only one weight. To change the font, drop a new `.ttf`/`.otf` into `ui/fonts/` and point that setting at it. Fixed-width letters are wider than the old default font's, so longer comms lines wrap onto the box's second line; everything else fits as it did.

**Cel shading** (`toon.gdshader`, light model in `toon_light.gdshaderinc`, shared with `toon_vertex.gdshader` and `water.gdshader`). A custom `light()` function replaces smooth lighting with three hard bands. For each light, `N·L` (how directly the surface faces the light, times shadow attenuation) picks shadow, mid or lit tone, with a one-pixel anti-aliased edge (`band()`). On top: a thin rim of light on the lit side of the silhouette and a hard-edged glint. The shadow band has a minimum brightness (`shadow_tone`) **only for the sun**: applying it to omni lights (engine glows, explosions) would light up whole rectangular light clusters. Every lit surface uses this shader with its own `albedo`; glowing parts use `StandardMaterial3D` with emission instead. For imported textured models the shader also has an optional `albedo_texture` (multiplied with `albedo`) and a glow map (`emission` × `emission_texture` × `emission_energy`). Both default to no effect (white and black), so flat-colour materials are unchanged. `ToonMaterial.convert_tree()` ([effects/toon_material.gd](../effects/toon_material.gd)) builds these from a model's PBR materials. It keeps colour, colour texture and glow, drops normal, metallic and roughness maps (fine bumps turn into speckles under hard bands), and leaves transparent materials alone. The Great Fox uses it ([8.19](#819-planet-terrain-corneria)); the Arwing still uses `ShipModel`'s flat-colour conversion.

**The ship model** (`player/ship_model.gd`, `ShipModel`). The player and wingmen fly an imported model, the *Arwing (Assault)* from Sketchfab in [models/arwing_assault/](../models/arwing_assault/), instanced as `Model/Arwing` in `ship.tscn`. Imported models come with ordinary PBR materials, which would look smooth and out of place, so the `ShipModel` script on the instance converts them when it loads. Every flat-colour material becomes a toon `ShaderMaterial` with the same colour, cached in a static dictionary so all four ships share one toon material per imported colour. Textured, emissive (the engine slot, the cannon lights) and transparent materials are kept as imported. One material, `accent_material` (`Material.004`, the inset panels in the blue fins), gets its own copy per ship, painted in `accent_color`: yellow for Fox (set on `ship.tscn`), and each wingman's colour via `set_accent()` from `Wingman._ready()`. The model is about 230,000 triangles, much denser than anything else in the game; the importer generates LODs, so distant ships draw fewer.

**Ink outlines** (`ink_outline.gdshader`). A screen-covering quad, attached to the camera, reads the depth and normal buffers. For each pixel it compares its four neighbours:
- a big jump in depth, on the nearer side → a silhouette line;
- similar depth but a sharply different normal → a crease line.

Lines fade out between 220 and 520 m so distant ships don't become black specks. **Only opaque geometry gets outlines**, because transparent materials don't write depth. That's used deliberately: space dust is made transparent so it isn't outlined, and fading objects (destroyer arriving, wingman near the camera) lose their outlines while transparent.

**Engine glow.** `Fighter._update_engine_glow()` does for the engine glow what the engine sound does for pitch (see [8.17](#817-sound)). The strength is 1.0 at cruise speed, plus `engine_glow_per_speed` (0.015) per m/s above or below it, clamped to `engine_glow_range` (0.5–2.3). It multiplies the `Model/Glow` mesh's size and emission energy and the `Model/EngineLight`'s energy. For your ship that's 0.63 at minimum speed, 1.45 at full throttle and 2.28 boosting. Size matters more than brightness: bloom washes any bright glow out to white, and from the chase camera you see the glow end-on, so a brighter or longer glow alone barely shows. Each ship gets its own copy of the glow material in `Fighter._ready()`, since the scene's material is shared. Ships without those nodes (enemy fighters) are skipped.

**Shield bubble.** An additive, unshaded sphere shader: a bright spot where the shot landed, a ripple spreading from it, or the whole bubble lit (`coverage = 1`) for collapse and reboot. `ShieldEffect` animates the uniforms.

**Sky.** A procedural sky shader: hashed noise for stars, layered value noise for faint nebulae, and a glow around the sun direction. The `Environment` resource adds ambient light, filmic tonemapping and glow (which makes emissive bolts, engines and explosions bloom).

**Space dust.** 350 tiny specks in a box that wraps around the camera (`fposmod`), stretched along the ship's velocity. They're what makes speed visible in empty space.

**Impacts.** `Impact.spawn(parent, position, color, size)` creates a glowing sphere and a light that expand and fade over 0.35 s, then free themselves. Used for hits and every explosion.

### 8.16 The intro cutscene

**File:** [world/intro_cutscene.gd](../world/intro_cutscene.gd)

1. `play()`: put the ship at `IntroStart` on autopilot (`controls_enabled = false`), place the wingmen in their slots, hide the HUD, turn off the camera's own physics, park it at `IntroCameraSpot` with a narrow FOV.
2. **FLYBY:** the camera stays put and pans to follow the ship. Once the ship is `handover_distance` past it...
3. **CAMERA_FLY:** interpolate the camera from where it is to `chase_transform()` over 1.2 s with a smoothstep.
4. `_finish()`: snap the camera, re-enable it and the controls, fade the HUD in, emit `finished`.

Fire, Enter or gamepad A skips to `_finish()`. **To reframe the shot, move the two markers** (`IntroStart`, `IntroCameraSpot`; set in `levels/level_base.tscn`, overridden per mission, e.g. 250 m up on Corneria); on the Asteroid Field the asteroid-free lane follows them automatically.

### 8.17 Sound

**Files:** [audio/sfx/](../audio/sfx/), [effects/sound_fx.gd](../effects/sound_fx.gd), the *Sounds* export group and `_fire()` / `_update_engine_sound()` in [player/fighter.gd](../player/fighter.gd); sound nodes in [ship.tscn](../player/ship.tscn) and [enemy_fighter.tscn](../enemies/enemy_fighter.tscn)

All gameplay sounds are `AudioStreamPlayer3D`s, so they come from where things are and fade with distance; the current camera is the listener.

| Sound | How it plays |
|---|---|
| **Laser shot** (`laser.mp3`) | A `FireSound` child of each ship. `Fighter._fire()` plays it with a small random pitch change. `max_polyphony` (4 on your ship, 3 on enemies) lets shots overlap; the sound is 2 s long, so the oldest tail is cut when a new shot needs a voice |
| **Engine** (`thrusters.mp3`, looping) | An `EngineSound` child of each ship, autoplaying. `Fighter._update_engine_sound()` sets its pitch every tick: 1.0 at cruise speed, `engine_pitch_per_speed` (0.008) higher or lower per m/s, clamped to 0.5–2. For your ship that's 0.8 at minimum speed and about 1.7 boosting. Measured from cruise speed, so the light fighter (one fixed speed) keeps a steady pitch. `max_distance` 300 m keeps distant engines silent |
| **Ship explosion** (`explosion_medium.mp3`) | `explosion_sound` export on `Fighter`. Enemies and the player call `SoundFX.play_at()` where they die. The destroyer has its own export and plays it lower and slower on every other blast of its death chain, plus a deep final blast |

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

- **Asteroid Field** (`main.tscn`, root `Main`): `main.gd` extends `Level` and overrides `_build_world()` to scatter the asteroids. Adds `SpaceDust`, a `PlayBoundary` (radius 1000 m) and a `GreatFox` behind the intro start ([8.19](#819-planet-terrain-corneria)).
- **Corneria** (`levels/corneria.tscn`, root `Corneria`): plain `Level` with its own `intro_line`, enemy waves without destroyers (`destroyer_every = 0` on its `EnemySpawner`) and a `PlayBoundary`. Overrides the environment (daytime sky, see [8.19](#819-planet-terrain-corneria)), the sun, and the start positions: the formation starts 120 m over the sea south of the coast, heading north towards the bay and its arches (after a death the intro is skipped and ships start where the scene puts them). Adds `Terrain` (with the Corneria map), `Props`, `Clouds` (which build themselves), `PlayBoundary` and a `GreatFox` parked outside the boundary.

**Anything changed in the base reaches every mission** unless the mission overrides it. To change one mission only, select the node in that mission's scene and change it there (the editor shows inherited nodes greyed in the Scene dock).

### 8.19 Planet terrain (Corneria)

**Files:** [world/terrain.gd](../world/terrain.gd), [world/terrain_map.gd](../world/terrain_map.gd), [world/map_props.gd](../world/map_props.gd), [world/clouds.gd](../world/clouds.gd), [effects/toon_vertex.gdshader](../effects/toon_vertex.gdshader), [effects/water.gdshader](../effects/water.gdshader), [world/planet_environment.tres](../world/planet_environment.tres); the map in [models/corneria/](../models/corneria/), built by [build_corneria.py](../models/corneria/source/build_corneria.py); the camera's ground clearance in [player/chase_camera.gd](../player/chase_camera.gd)

**The Corneria map** is our own, built in Blender from code like the destroyer and the enemy fighter. It's 8 × 8 km, centred on the origin, north is −Z:

- **South:** open sea, where the mission starts (120 m up at (−450, 3400), heading north), with leaning rock spires (sea stacks) and two small islands offshore.
- **The bay** runs north into the land; six stone arches stand in a line up it (openings about 80 m wide and 100 m high), then a red suspension bridge with a 30 m deck to fly under carries a city street over the river mouth.
- **Corneria City** sits where the river meets the bay: a street grid of about 170 blocks rising to downtown towers (stepped, round and domed, glass slabs, twin towers with a skybridge) around a 340 m spire. Towers over 100 m carry red warning lights.
- **The river** comes from a waterfall off a 130 m plateau in the north-east (a lake on top), winding through the hills past the city.
- **The west:** rough hills, rocky ridgelines, five mesas, a canyon from the north-west mountains down to the river, cliffs along the coast, a lake, and the **military base** (runway, hangars, control tower, radar, headquarters, barracks, depot, radio mast) reached by a road through a graded valley from the bridge.
- **The east coast:** a harbour town with piers, boats and a lighthouse.
- **Mountains** wrap the north, east and west edges irregularly (peaks and saddles, spurs reaching inward), snow-capped above 260 m, fading into sea cliffs toward the south.
- About 6,000 low-poly pines in clumps on the gentle slopes.

**How it gets into the game.** `build_corneria.py`, run in Blender with `FORCE_EXPORT`, writes two files next to its `source/` folder:
- `corneria_map.tres`, a **`TerrainMap`** resource: the ground height at each point of a 321 × 321 grid (25 m cells), one byte per cell saying what it is (`PAINT_AUTO` coloured by Terrain's height and slope rules, `PAINT_PAVED` for the city, town and base apron, `PAINT_HIGH_WATER` under the plateau lake, whose surface is `high_water_level` 120 m), and the **structure height** of each cell: the top of the tallest building, arch, bridge part or rock spire overlapping it (0 where there's none).
- `corneria_props.glb`: everything standing on the ground (city, streets, town, base, arches, bridge, road, sea stacks, trees, and the plateau lake, upper river and falls). The sea isn't in it: Terrain makes the sea.

To change the map, edit the script (layout constants at the top: city, base, plateau, river, bay, road waypoints...), run it in Blender through the MCP with `FORCE_EXPORT` (or `blender --background --python build_corneria.py -- --export`), then run Godot's `--import` (or let the editor reimport) and reload the scene. Never edit the two exported files by hand. Open surfaces (the falls, the lakes, domes) are given an explicit facing in the script: the game draws only the front of a face, while Blender's preview shows both.

`Terrain.map` points at the map, so Terrain uses its heights instead of noise (below). The props are instanced as `Props` with **`MapProps`** on it: at load it cel-shades the materials with `ToonMaterial`, gives the plateau water the level's water material, and builds trimesh collision on the World layer from the solid meshes (`solid_nodes`: everything but the streets, road and trees). So you crash into buildings, bolts hit them, and they block enemies' line of sight. Loading the mission takes about 0.9 s headless (the terrain mesh is most of it), and it renders as fast as the old 4 km test map did (about 650 FPS uncapped at 1280 × 720 with 12 enemies over the city, worst frame 2.2 ms, on the development machine).

**Terrain without a map** (any future planet mission) builds itself in `_ready()` from seeded noise (`terrain_seed`), so the landscape is the same every run. That map is `size` (4 km) square, centred on the origin. Height at any point is:

```
base_height (8 m)  +  hills (±70 m, ~900 m wide)
                   +  ridged mountains (up to 320 m), only where a slow "region" noise allows,
                      and none within 450 m of the centre (fading in over the next 500 m)
                   +  boundary ring (up to 520 m) rising from 72% to 90% of the half-width
then sinking to just below sea level in the last 6% of the map, so the edge meets the far ground.
```

Either way the heights live on a grid (25 m cells: 160 × 160 for the noise map, 320 × 320 for Corneria), built into 8 × 8 chunks of flat-shaded triangles (204,800 on Corneria). Every triangle gets its own colour from its height and steepness: sand below 6 m above the water, rock where it's steeper than `rock_slope`, snow above 260 m, otherwise light or dark grass in patches, each with a little random brightness (`shade_jitter`) for the low-poly look. Cells a map marks as paved get `paved_color` instead. The colours are vertex colours, drawn by `toon_vertex.gdshader` (the toon light model with `COLOR` as the albedo). Collision is a `ConcavePolygonShape3D` per chunk built from the very same triangles, on the World layer, so you crash into hills exactly where you see them (30 damage and a bounce, the normal crash).

- **`height_at(x, z)`** returns the ground height, interpolated within the same triangle the mesh uses (each cell splits along its (0,0)–(1,1) diagonal). It matches the collision exactly, and returns `-INF` outside the map. **`surface_height(x, z)`** also counts the water (the sea, and a map's high water). **`clearance_height(x, z)`** also counts a map's structure heights: it's what the AI, enemy spawns and the player's turn-back stay above. The chase camera and the wingmen's formation slots use `surface_height()` instead, so they don't jump onto a rooftop when you fly between towers. Ground-aware code finds the terrain through the `terrain` group (added in `_enter_tree()`, so nodes earlier in the scene can find it in their `_ready()`).
- **Lakes and the sea** are one opaque plane at `sea_level` (0), so every basin below it fills with water. With `water_to_horizon` (Corneria) the plane reaches the horizon, so there's sea beyond the coast instead of the far ground. `water.gdshader` is a flat toon blue with soft drifting bands of shimmer. Because it's opaque, shorelines get ink outlines. Water above sea level (the plateau lake) is part of the props, with its own collision.
- **Water and the far ground are solid:** thin collision slabs under each, so diving into a lake is a crash, not a swim.
- **Far ground:** a 30 km flat plane just under sea level fills the horizon beyond the map (under the water on Corneria).

**Clouds** (`Clouds`): clusters of 5–9 squashed toon blobs in two layers. The defaults are 60 clusters at 220 m and 430 m (±30) within 1700 m of the centre, none within 350 m of it; Corneria has 170 at 330 m and 560 m within 3600 m (above most of the city, below the peaks). Each cluster is merged into one mesh. They have no collision; while the camera is inside or within 40 m of one, it fades to 85% transparent, like the wingmen near the camera.

**Sky and light** (`planet_environment.tres`): a procedural day sky whose lower half matches the horizon colour (otherwise a dark band shows past the far ground), exponential fog in the horizon colour (density 0.00035: about 65% at 3 km) that doesn't tint the sky, and a higher, slightly brighter sun with shadows out to 600 m.

**Camera:** `ChaseCamera` keeps at least `ground_clearance` (3 m) above `surface_height()` when the level has a terrain, so low flying never puts it underground.

**Ground-aware AI and spawning:** enemies and wingmen stay above the ground and the city's structures ([8.4](#84-the-ai-pilot-aipilot)), wingman slots rise when you fly low ([8.8](#88-wingmen)), enemy patrols and waves stay above the ground and inside the boundary ([8.5](#85-enemy-fighters), [8.7](#87-waves-and-the-spawner)). Hills and buildings block enemies' line of sight, like asteroids.

Measured on Corneria (three 3-minute runs, the player circling the city 60 m above the ground while waves attack and the wingmen cycle Form Up, Weapons Free and Cover Me): wingmen never touched the ground or a building; enemies scraped the ground once in 9 minutes (a slow light fighter on patrol climbing into a slope) and never hit a building. **The AI flies over the city, not through it.** A whole 25 m cell counts as tall as its tallest structure, so streets read as solid. With the player flying straight down a street 26–106 m up, the wingmen hop over the buildings (up to 150–250 m above the ground) and are in formation 72–88% of the time; in one of four runs a wingman brushed a tower wall sideways (they can't be hurt, they slide off). Enemies chase you over the rooftops rather than between them.

**Play boundary** ([world/play_boundary.gd](../world/play_boundary.gd)): a `PlayBoundary` node marks the edge of the area, a vertical cylinder of `radius` around the node: 3300 m around (0, 0, 500) on Corneria, reaching into the mountains on three sides and out over the sea to the south (the intro starts the formation 300 m behind the start point, which has to be inside too); 1000 m on the Asteroid Field, just past the asteroids (900 m) and where destroyers appear (1000 m). Only horizontal distance counts. Past it the HUD blinks **RETURN TO THE COMBAT AREA**; past `radius + turn_back_margin` (200 m further, on the ring's slopes) the ship turns itself back, like Star Fox's all-range mode, and the HUD shows **TURNING BACK** ([8.2](#82-the-players-ship-ship)). A negative `turn_back_margin` keeps the warning but never takes control. A mission without a `PlayBoundary` has no edge. Enemy waves and patrols stay inside it on either mission ([8.5](#85-enemy-fighters), [8.7](#87-waves-and-the-spawner)). Tested on Corneria, flying east into the mountains from 120 m and 300 m above the ground: the warning came at the edge, the turn started at 201 m out, the ship went no further than 241 m out and didn't touch the slopes. (On the old 4 km test map, flying level and low straight at the ring's steepest ridges could still hit the slope before or during the turn; that's still possible wherever the mountains are steep.)

**The Great Fox** ([world/great_fox.tscn](../world/great_fox.tscn), script `GreatFox`): the team's mothership hovers outside the area, so the Star Fox team feels present. On Corneria it sits at (500, 700, 4500), over the sea about 730 m outside the boundary, behind the direction the formation flies in from. It shows in the background of the intro fly-by, and you see it whenever you turn back towards the sea. It is yawed 70° so it shows a three-quarter profile, and it bobs 3 m over 14 s (`bob_height`, `bob_period`). It is **scenery only**: no collision, not in any group, not shootable, and the AI doesn't know it exists. So it must stay out of reach. Boosting straight at it, the turn-back stopped the ship about 257 m short of the hull (farthest point reached: 3,549 m from the boundary's centre). Move it further out if you shrink the margin or grow the boundary. Fog makes it a hazy silhouette at that distance, which helps it read as huge. Drawing it costs about 0.05 ms a frame.

On the **Asteroid Field** it sits at (0, 30, 1800), straight behind `IntroStart` (0, 0, 300), so the formation's fly-in starts 1.5 km in front of it. Its bow points into the field, yawed -25° so the intro camera sees its profile, and the formation appears in front of its lit hangar openings, as if they had just launched. That field had no edge before; it got a `PlayBoundary` (radius 1000 m, turn back at 1200 m) to keep the player away from the hull. Boosting straight at it, the turn-back stopped the ship 195–220 m short (farthest point 1,340 m from the centre). At 1,700 m it came within 112 m, which is why it's at 1,800 m. A side effect: waves now spawn at least 250 m inside the boundary and patrols roam at least 150 m inside it, so fighters stay within 750–850 m of the centre, about the extent of the asteroids. There's no fog in space, so it's crisp.

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

**`move_toward(value, target, rate * delta)`**: change at a constant rate, without overshooting. Used for speed, boost energy, damage flash and the formation assist.

**`smoothstep(a, b, x)`**: 0 below `a`, 1 above `b`, smooth in between. Used for fades by distance.

**Local space via transforms.**
- `node.global_transform * local_point` → a point in the node's frame, in world space (formation slots: `leader.global_transform * slot_offset`).
- `node.global_transform.affine_inverse() * world_point` → a world point in the node's frame (radar, camera fade, turret aim).
- `-global_basis.z` is forward, `global_basis.x` is right, `global_basis.y` is up.

**Guard against freed nodes.** Nodes can be freed at any time (a target explodes). Before using any stored reference, check `is_instance_valid(node)`. Don't cast a possibly-freed reference with `as` before checking.

**Guard against double hits.** Several bolts can land in the same frame. `take_hit` starts with `if health <= 0: return` (or `is_destroyed`) so a thing can't die twice and award score twice.

**Duck typing with `has_method` and `get`.** `has_method("take_hit")` to see if something's shootable; `node.get("velocity")` returns null if there's no such property, which the lead-point code uses to handle both moving and static targets.

**Shared resources need per-instance copies.** A material in a `.tscn` is shared by every instance. To change it for one instance (the shield bubble), `duplicate()` it first, as `ShieldEffect._ready()` does. `ShipModel` does the opposite on purpose: one toon material per imported colour, shared by every ship, plus a separate accent material per ship.

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
1. Import an image into the project (drop it in a folder such as `comms/portraits/`).
2. Open the speaker's `.tres` in `comms/speakers/`, and drag the image onto **Portrait** in the Inspector.

It's cropped to fill the 84×84 square, so square images work best.

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
2. Change exports (health, speeds, turn rates, fire rate, bolt scene) and the model. **Keep `Model/MuzzleL` and `Model/MuzzleR`** (Fighter fires from them) and collision layer 4.
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
- **Sound that must outlive what made it** (an explosion of something that's freed at once): `SoundFX.play_at(parent, stream, position, volume_db, pitch)`.

Put the audio file in `audio/sfx/`. A looping sound needs **Loop** ticked in the Import tab (then *Reimport*). Before sounds multiply, consider adding an `SFX` audio bus (*Audio* panel at the bottom of the editor) and a volume option in `Settings`.

### Change the ship model
The art is an imported model instanced under `Model` in `player/ship.tscn`; wingmen inherit it.

1. Put the model's folder (`.gltf` + `.bin` + textures, or a `.glb`) under `models/`, and let the editor import it (or run `--import`).
2. In `ship.tscn`, replace the `Model/Arwing` instance with the new one. Rotate it so its nose points along −Z and scale it to roughly 8 m wingspan (the Arwing needed −90° around Y and a scale of 0.0055).
3. Give it the `player/ship_model.gd` script, and set **Accent Material** to the name of the imported material that should carry each ship's colour (`Material.004` on the Arwing: the panels in the fins).
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
2. **Override what differs:** environment and sun, the ships' start positions and intro markers (keep them clear of anything solid), `intro_line`, `spawn_enemies`. Wave settings go on its `EnemySpawner` (`destroyer_every = 0` for no destroyers).
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
- **Read the formation slot through `Wingman.slot_position()`.** It is `current_slot_offset()` (which includes the Cover Me trail) around the leader, raised above the ground on planets. Computing `leader.global_transform * slot_offset` yourself puts the slot underground when the player flies low.
- **Vertex colours aren't converted from sRGB.** Colours set with `SurfaceTool.set_color()` reach the shader as-is, unlike `source_color` uniforms, so code that builds coloured meshes (like `Terrain`) converts with `Color.srgb_to_linear()` first, or the colours come out washed out.

- **Enemy hurtboxes are areas.** A friendly raycast that should hit enemies needs layer 8 (`LAYER_HURTBOX`) in its mask, `collide_with_areas = true`, and `Hurtbox.resolve(hit.collider)` before using the collider; otherwise it gets the `Area3D`, which has no `take_hit` and isn't an `EnemyFighter`. A new enemy type that should be as easy to hit needs its own `Hurtbox` child.

- **The Input Map is overwritten.** See above: gameplay actions live in `settings.gd`.
- **Laser speed includes ship speed** (`laser_speed + speed`), and every lead-point calculation assumes the same. Keep them consistent if you change how bolts move.
- **Twin lasers assume two muzzles** (`_cannons[0]` and `[1]`; `parallel_fire` aims from the point between them).
- **The ship's materials are replaced at runtime.** `ShipModel` swaps the Arwing's imported materials for toon ones when the game starts, so the editor viewport shows the original smooth look. To change a colour, change it in code or the accent export, not in the imported materials. Reimporting the model (or changing its import settings) can rename meshes and materials; `accent_material` is matched by name.
- **Base scenes reach further than they look.** `wingman.tscn` inherits `ship.tscn` and `light_fighter.tscn` inherits `enemy_fighter.tscn`. A value set on the base applies to the child unless the child overrides it: give the player a new collision mask and the wingmen get it too; upgrade the "elite" and every level 1 enemy is upgraded. After changing a base scene, check the child scene and override there.
- **Neither you nor the wingmen are in the `obstacles` group,** so AI avoidance doesn't steer around friendly ships. Wingmen stay clear of each other through formation slots, pursuit staggering and crowd checks, and clear of you through formation flight and, on Weapons Free, `_steer_clear_of_leader()`. A new friendly AI behaviour needs its own way of staying clear.
- **Wingmen and enemies only see the player.** Enemies never target wingmen; nothing damages wingmen. Destroyer turrets shoot at wingmen only when you're out of range, for show.
- **Destroyed destroyer parts stay in the scene.** Use `Wingman.target_gone()` or check `is_destroyed`, not just `is_instance_valid()`.
- **`queue_free()` takes effect at the end of the frame.** Within the same frame the node still exists; `is_queued_for_deletion()` tells you. The spawner waits a frame before counting enemies for this reason.
- **Transparent things have no outlines.** Anything using transparency (including fades) loses its ink lines while transparent.
- **The toon shadow floor is sun-only.** Don't apply it to omni or spot lights.
- **Physics interpolation is off.** Ships and camera update at 60 Hz, so very high refresh-rate monitors may show slight judder.
- **The asteroid field is seeded.** Same layout every run (apart from the intro lane); change `field_seed` for a different one.
- **AI obstacle avoidance only knows spheres.** Cover large non-spherical things with `ObstacleProxy` children.
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
| **Proxy** | An invisible sphere the AI avoids (`ObstacleProxy`) |
| **Slot** | A wingman's formation position in your local space (`slot_offset`) |
| **Speaker** | A comms character resource (`CommsSpeaker`) |
| **Pilot** | A `CommsSpeaker` that flies: accent colour + battle lines (`comms/pilot.gd`), set as a wingman's `speaker` |
| **State** | What a wingman is physically doing (FOLLOW / ATTACK), or an enemy's AI state |
| **Threat** | An enemy currently chasing you (`WingCommand.threats()`) |
