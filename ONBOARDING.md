# Onboarding guide

> This is the quick reference. For a full explanation of how the code works, with walkthroughs and step-by-step recipes, read [docs/GUIDE.md](docs/GUIDE.md).

***Star Fox: Ascent***, a Star Fox fangame: a 3D arcade space shooter with *Star Wars: Rogue Squadron*-style squad orders. You fly an Arwing through an asteroid field with three AI wingmen (Falco, Slippy and Krystal), fight waves of enemy fighters, and give your wingmen orders.

This guide assumes you know Godot 4 basics: scenes, nodes, signals and GDScript. It covers what's specific to this project. Read sections 1–4 before touching code; use the rest as reference.

---

## 1. Get it running (5 minutes)

1. Install **Godot 4.7** (standard build, not .NET). The project uses Jolt Physics and Forward+, both built in.
2. Open the folder in the Godot project manager and press **F5**.
3. Almost every asset (meshes, sky, effects) is generated in code or built from primitives. The exceptions are the sound effects in `audio/sfx/`, the player/wingman ship model in `models/arwing_assault/`, the Great Fox in `models/great_fox/`, the destroyer, enemy fighter, Corneria map and space station in `models/destroyer/`, `models/enemy_fighter/`, `models/corneria/` and `models/space_station/` (built by Blender scripts there) and the UI font in `ui/fonts/`; all are in the repo, and Godot imports them the first time the project opens.

**Controls**

| Action | Keyboard / mouse | Gamepad |
|---|---|---|
| Steer | Mouse (moves a virtual stick), arrow keys | Left stick |
| Throttle | W / S | RT / LT |
| Roll | Q / E or A / D | Right stick left/right |
| Fire | Left mouse button / Space | RB |
| Wingmen: attack target | F | Y |
| Wingmen: cover me (toggle) | C | X |
| Wingmen: weapons free | V | A |
| Wingmen: regroup / cancel orders | R | B |
| Pause | Esc | Start |
| Skip intro | Fire / Enter | A |

---

## 2. Project map

```
main.tscn / main.gd        Space Station mission: inherits levels/level_base.tscn, main.gd (extends Level) scatters the asteroids
levels/
  level.gd                 Level: shared mission logic (build world, intro + line, spawner start, death/restart, mouse)
  level_base.tscn          Every shared node (ship, camera, wingmen, spawner, HUD, comms, pause, intro); missions inherit it
  corneria.tscn            Corneria: the 8 km map (terrain + props: city, arches, base...), clouds, day sky, enemy waves (no destroyer), play boundary
missions/
  mission.gd + *.tres      Mission: title, description, scene_path (listed by the mission selector)
player/
  fighter.gd               Fighter: shared flight model + guns for every ship (base class)
  ship.gd / ship.tscn      Ship: the player (input -> Fighter), shields, death
  ship_model.gd            ShipModel: on the imported model; converts its materials to toon, paints the accent colour
  chase_camera.gd          ChaseCamera: third-person camera
ai/
  ai_pilot.gd              AIPilot: shared AI (steering, obstacle and ground avoidance, attack runs)
wing/
  wingman.gd / .tscn       Wingman: formation flying + orders
  wing_command.gd          WingCommand: wingman selection + orders (attack / cover me / form up)
enemies/
  enemy_fighter.gd / .tscn EnemyFighter: patrol / chase / evade / seek state machine (the .tscn is the elite fighter)
  light_fighter.tscn       Basic fighter used in level 1: inherits enemy_fighter.tscn, fixed speed, slower turns/fire, 3 HP (elite: 4)
  hurtbox.gd               Hurtbox: enlarged hit zone (Area3D) on enemy fighters; bolts and crosshair hit it, crashes don't
  fighter_model.gd         FighterModel: on the imported fighter model; cel-shades it, paints accent + lights per fighter type
  enemy_spawner.gd         EnemySpawner: waves, destroyer every 5th wave, global fighter cap
  destroyer.gd / .tscn     Destroyer: capital ship (warp arrival, movement, launches, kill rule); destroyer.tscn is the previous ship
  juggernaut.tscn          The Juggernaut: the current destroyer (Destroyer script), spawned by every mission
  juggernaut_turret.tscn   The Juggernaut's turret (DestroyerTurret, meshes saved out of juggernaut_turret.glb)
  destroyer_part.gd        DestroyerPart: a destructible subsystem (bridge / thruster / turret / hangar)
  destroyer_turret.*       DestroyerTurret: hull turret (extends DestroyerPart)
  destroyer_hangar.gd      DestroyerHangar: hangar door that launches squadrons (extends DestroyerPart)
  obstacle_proxy.gd        ObstacleProxy: invisible sphere the AI steers around (covers the old destroyer hull)
  obstacle_box.gd          ObstacleBox: invisible box the AI steers around (covers the Juggernaut hull)
weapons/
  laser.gd                 Laser: bolt movement + hit detection (shared by both sides); splash on water (water_splash)
  laser.tscn               Player-side bolt (green, 1800 m/s on ship.tscn, 16 m streak; Bolt + Glow, see laser_bolt/laser_glow)
  enemy_laser.tscn         Enemy fighter bolt (red)
  turret_laser.tscn        Destroyer turret bolt (bigger, slower, 8 damage)
  laser_bolt.gdshader      Bolt look: additive (no ink outline), white core, tail fade, 1 px minimum width; on a tapered open cylinder (0.2 m radius player bolt, 12 rings) bent to a pointed head
  laser_glow.gdshader      Soft halo along a bolt, even along it and fading towards the tail, laid out on screen; shrinks with distance (no minimum size)
world/
  asteroid.gd              Asteroid: procedural, destructible rocks
  intro_cutscene.gd        IntroCutscene: level intro fly-by
  space_dust.gd            Speed streaks around the camera
  space_sky.gdshader       Procedural starfield sky; optional distant planet (Corneria on the Space Station mission: `planet_*` uniforms; land biomes, mountain ranges and sun-lit relief: `land_*`, `dryness`, `mountain_amount`, `snow_line`, `relief_strength`)
  space_environment.tres   Shared Environment (sky, glow, tonemap) used by the title and the base level
  asteroid_field_environment.tres  Its copy for the Space Station mission, with the planet on (keep the two in step)
  terrain.gd               Terrain: low-poly ground (noise, or a TerrainMap), lakes, far ground, backdrop beyond the edge, collision; height_at() / surface_height() / clearance_height() / water_level_at() / is_water_surface()
  water_marks.gd           WaterMarks (added by Terrain): splash rings + wake trails fed to water.gdshader each frame (rings[32], wake[192])
  terrain_map.gd           TerrainMap: a hand-made landscape exported from Blender (heights, paint, structure heights)
  map_props.gd             MapProps: on an imported map props model; toon materials (foliage unlined, with shadow-only stand-ins), water material, trimesh collision
  waterfall.gd/.tscn       Waterfall (Corneria): the falls; @tool, builds a lens-section body of water along a thrown-water arc (80→88 m wide, 11→7 m thick, 125 m drop, 32 m reach, 18 m run-up fading in on the river), mist puffs (9/s, 10→32 m) and foam rings (3/s) at the foot; transform from models/corneria/waterfall.txt
  clouds.gd                Clouds: flyable cartoon cloud clusters that fade near the camera (Corneria draws them with effects/cloud.gdshader)
  planet_environment.tres  Day sky + horizon fog for planet missions
  play_boundary.gd         PlayBoundary: edge of a mission area; HUD warning, then the ship turns itself back
  great_fox.gd / .tscn     GreatFox: the team mothership as scenery outside a mission area (no collision; slow bob)
  space_station.gd / .tscn SpaceStation: solid friendly scenery (Space Station mission centre): toon materials, trimesh collision, AI avoidance spheres; keeps asteroids, waves and destroyers out
effects/
  hit_burst.gd/.tscn       HitBurst: a bolt hitting anything with take_hit: cartoon star (0.2 s, 5 poses, min on-screen size but at most star_max_grow 2.5× its own, so far hits still shrink) + 8 sparks back at the shooter; no ink; settings on the .tscn
  surface_hit.tscn         HitBurst for bolts hitting things that can't be shot (ground, buildings, hulls): rounder 1.3 m pop in the bolt's impact_color (star_max_grow 1.5), 6 sparks glancing off, 4 dust puffs (0.7 s)
  hit_burst.gdshader       The star: camera-facing quad cut into a banded spiky star (core, yellow, orange rim) that pops out and hollows (instance uniforms age/seed)
  hit_reaction.gd          HitReaction: on EnemyFighter / DestroyerPart: red flash (hit_flash instance uniform, 0.12 s), flinch (fighters, 0.8 m / 6°), smoke at ≤ 70 % health, fire at ≤ 40 % (Explosion.trail), from the target's smoke point (fighters: Model/SmokePoint, the engine) or else where it was first hit
  explosion.gd             Explosion.spawn(parent, at, style, size, velocity): flash, fireball, smoke, sparks, debris, shockwave, light; Explosion.prewarm(); Explosion.trail(): a world-space puff trail (wrecks, debris, damage smoke)
  explosion_style.gd       ExplosionStyle resource: every look value, in units of size (fireball radius, m)
  explosion_puff.gdshader  Puff: banded fire cooling into toon-lit smoke, breaking up; transparent pass, no ink outlines
  cloud.gdshader           Cartoon clouds (Clouds on Corneria): drifting noise lumps, squashed, shaded bottoms with soft crevices, own three-band light + silver lining; no ink outlines (transparent pass)
  explosions/*.tres        Presets: fighter, asteroid, destroyer_part, destroyer_chain, destroyer_final
  wreck.gd / .tscn         Wreck: a destroyed enemy fighter's model flying on, smoking, nose aligned with velocity vector, rolling, until it crashes, is shot (friendly bolts, via the fighter's hurtbox) or 3 s pass, then a second explosion (no damage, no score) that throws 3–5 smoking debris pieces
  wreck_debris.gd          WreckDebris: a smoking piece from a wreck's second explosion (tumbles, trails smoke, burns out after 1–2 s; visual only)
  water_splash.gd/.tscn    WaterSplash: a bolt hitting water (shader jet ~11 m + crown, foam ring on the water); settings on the .tscn
  water_splash.gdshader    The splash shapes: a unit cylinder bent into a spiky jet or crown that rises, falls and breaks up (instance uniforms age/seed/size)
  waterfall.gdshader       The falls' body: water blues + white streaks moving with the water (UV.y = time of travel), lip and foot foam, ragged sides, darker band on its rounded sides, optional rock splits (off); unlined
  water_spray.gdshader     The wake's spray: a unit plane bent into a ragged curtain beside the ship
  water_wake.gd            WaterWake (on ship.tscn): spray sheets + foam V on the water when skimming (below 12 m, full at 3 m)
  muzzle_flash.gd          MuzzleFlash.spawn(...): brief flash on a gun muzzle when a fighter fires
  shield_effect.gd         ShieldEffect: the blue shield bubble on the player ship (+ shield.gdshader)
  toon.gdshader            Cel shading used by every lit surface (surface in toon_surface.gdshaderinc, light model in toon_light.gdshaderinc); optional colour texture + glow map
  toon_clip.gdshader       toon.gdshader plus a clip plane (instance uniform clip_plane); the destroyer while it warps in
  toon_unlined.gdshader    toon.gdshader in the transparent pass: no ink outlines (Corneria's foliage, via MapProps.unlined_materials)
  warp_portal.gd / .gdshader  WarpPortal: the destroyer's swirling arrival portal (opens, close(), frees itself; no collision)
  toon_material.gd         ToonMaterial.convert_tree(): cel-shaded copies of an imported model's PBR materials (keeps texture + glow; used by GreatFox)
  terrain.gdshader         The planet ground: colour per pixel (sand/grass/rock/snow/paved, ragged edges), smooth light bands; set up by Terrain
  noise.gdshaderinc        Gradient noise on an integer hash, shared by water.gdshader and terrain.gdshader
  water.gdshader           Sea/lake surface: depth bands, shore foam, wave crests, sun sparkles (depth from Terrain's heights)
  ink_outline.gd           InkOutline: screen-space ink lines; a child of each Camera3D (+ ink_outline.gdshader)
ui/
  title_screen.*           Title screen (Start / Settings / Exit; the project's main scene)
  mission_select.gd        MissionSelect: Start opens it; one button per Mission, description, Back
  hud.gd / hud.tscn        In-game HUD (drawn in code)
  pause_menu.*             Pause menu (Resume / Settings / Quit to Title)
  settings_menu.*          Settings screen (display + controls pages), shared by title and pause menus
  scene_fader.gd           SceneFader autoload: fade-to-black scene changes
  menu_theme.tres          Shared theme (buttons, labels, dropdowns) for all menus
  fonts/                   Share Tech Mono (fixed-width, SIL OFL: keep OFL.txt): the project font for menus, comms and HUD (gui/theme/custom_font)
audio/
  level_music.gd           LevelMusic: a soundtrack = optional lead (plays once) + loop (forever), volume
  music.gd                 Music autoload: plays the current LevelMusic on the Music bus; survives restarts, fades, ducks on pause
  sfx/                     Sound effects
settings/
  settings.gd              Settings autoload: input actions + bindings, fullscreen / resolution, saved to user://settings.cfg
comms/
  comms.gd                 Comms: in-game dialogue box (portrait + typed text, beeps or recorded voice, priorities)
  static.gdshader          Static shown in the comms portrait square while the box opens, closes or switches speaker
  comms_speaker.gd         CommsSpeaker: a character's name, colour, portrait and beep pitch
  pilot.gd                 Pilot: a CommsSpeaker that flies; adds accent colour + battle lines (acks, celebrations, praise for your kills)
  advisor.gd               Advisor: a CommsSpeaker who doesn't fly (Peppy); adds destroyer warning, hint and progress lines
  mission_control.gd       MissionControl: has the Advisor call out destroyers and their progress (node in level_base.tscn)
  speakers/*.tres          One file per character: Fox (CommsSpeaker), Falco, Slippy, Krystal (Pilot), Peppy (Advisor)
  portraits/*.png          Comms portraits, one per speaker: 256×256, imported with mipmaps
models/
  arwing_assault/          Imported Arwing (glTF, CC-BY 4.0, credit in license.txt): the player and wingman model
  great_fox/               Imported Great Fox III (glTF, textures cut to 1024 px; no licence came with it, see README.txt)
  destroyer/               Both destroyers: destroyer_*.glb (previous ship), juggernaut_*.glb (current: hull, bridge, keel/pod thrusters, door, turret, collision, markers) + juggernaut_turret_*.res (turret meshes saved by its import settings)
    source/                build_destroyer.py (previous ship) + collision.txt + proxies.txt; juggernaut_c2.py (builds and exports the Juggernaut in Blender; _c1*.py are earlier passes) + juggernaut.blend; concepts/ and juggernaut_preview/ (design rounds, renders)
  SPACE_ASSETS.md          Asset brief for the Space Station mission's models (the Juggernaut's design stages; station, fighter, asteroids still to do)
  enemy_fighter/           The Venomian "Mantis" enemy fighter (our own model), one .glb for every fighter type
    source/                build_enemy_fighter.py (builds and exports it in Blender)
  corneria/                The Corneria map (our own): corneria_map.tres (TerrainMap) + corneria_props.glb (everything on the ground); ASSETS.md (the kit's spec)
    kit/                   Kit_*.glb: previews of each kit piece (not used by the game)
    source/                build_corneria.py (lays out the map in Blender and exports both) + corneria_kit.blend (the hand-made pieces); .gdignore'd
  space_station/           The Cornerian wheel station at the centre of the Space Station mission, about 800 m across (our own): space_station.glb
    source/                build_space_station.py (builds and exports it in Blender; surface detail in add_ring/core/hangar_detail(), curved hulls smooth below SMOOTH_ANGLE 30°; 20,286 faces) + proxies.txt (AI avoidance spheres)
```

Every script with a `class_name` (`Fighter`, `Ship`, `Wingman`, `EnemyFighter`, `WingCommand`, `Laser`, and so on) can be used as a type anywhere.

---

## 3. The mental model

### Scene flow

```
title_screen.tscn --Start--> MissionSelect --pick--> SceneFader.change_scene(mission.scene_path) --> main.tscn / levels/corneria.tscn
                                                              |
        main._ready(): spawn asteroids (input actions come from the Settings autoload)
                       |
                       +-- first load:          IntroCutscene.play() --finished--> _begin_play()
                       |                         (Fox's intro line on the comms 0.5 s in)
                       +-- restart after death:  _begin_play() immediately (intro line plays here)
                                                              |
                                               EnemySpawner.start()  (waves begin)
```

**Death:** `Ship.died` → `Level` waits `restart_delay` → reloads the same mission. A static flag, `_skip_intro_once`, makes the reload skip the intro.

### One flight model, many pilots

Every ship (the player, wingmen, enemies) is a `Fighter`. `Fighter` owns the physics: speed, turning, banking, auto-levelling, collisions and firing. It doesn't decide anything. It asks its *pilot* each physics frame through overridable methods:

```
Fighter (player/fighter.gd)          flight model + guns
├── Ship (player/ship.gd)            pilot = player input
└── AIPilot (ai/ai_pilot.gd)         pilot = AI helpers; subclasses override _decide()
    ├── Wingman (wing/wingman.gd)    formation, orders
    └── EnemyFighter                 patrol / chase / evade / seek
```

**`Fighter._physics_process` runs in this order:**

1. `_think(delta)`: the pilot makes decisions (read input, run the AI).
2. Rotate from `_get_stick()` / `_get_roll()`. When roll input is 0, the ship rolls towards `_get_level_up()`.
3. Change speed towards `_get_target_speed()`.
4. `move_and_slide()`, then collision response.
5. `_aim(delta)`: set `aim_point`, where the guns aim (twin lasers fly parallel to the line through it).
6. Fire if `_wants_fire()` and the cooldown allows.

**The pilot interface:**

| Override | Meaning |
|---|---|
| `_get_stick() -> Vector2` | x = yaw right, y = pitch down (screen-style), -1..1 |
| `_get_roll() -> float` | Positive rolls left. 0 means auto-level. |
| `_get_target_speed()` | Clamped to `[min_speed, boost_speed]` |
| `_wants_fire()` | |
| `_get_level_up()` | "Up" to auto-level towards (wingmen use the leader's up) |
| `_get_pitch_rate()` | Pitch rate at full stick (default `pitch_rate`; wingmen raise it to somersault) |
| `_get_acceleration(fast)` | Speed change rate (default `acceleration`, or `boost_acceleration` when `fast`) |

For AI ships, `AIPilot._think()` calls **`_decide(delta) -> Vector3`**, which returns the world point to fly towards. It then handles steering and obstacle avoidance itself. A subclass's `_decide()` also sets `_target_speed`, `_engage` (what to shoot, if anything) and `_level_up`.

Useful `AIPilot` helpers:
- `_attack_goal(target, side)`: chases fighters from behind, and makes strafing runs (approach, then break off) on anything that doesn't move. Strafing runs need a clear view (`_clear_view()`, one World-layer ray): blocked, the pilot repositions, and pull-out points are chosen to see the target (`_viewpoint()`, `VIEW_RING` 8 directions). Avoidance ignores obstacles a structure target is mounted on (whose clearance zone holds it); not for fighters.
- `_lead_point(target)`: where to aim so the bolts meet a moving target.
- `_fly_to_then_attack(point, timeout)`, `_begin_attack()`.

---

## 4. Conventions you must know

### Coordinates
**-Z is forward** for every ship, marker and model. +X is right and +Y is up. Formation slots (`Wingman.slot_offset`) are in the leader's local space.

### Collision layers
Defined as constants on `Fighter`.

| Layer | Bit | Who's on it | Collides with |
|---|---|---|---|
| World | 1 (`LAYER_WORLD`) | Asteroids, destroyer hull | everything |
| Friendly | 2 (`LAYER_FRIENDLY`) | Player (`collision_mask` = 5: World + Enemy) + wingmen (World only) | World + Enemy (player) |
| Enemy | 4 (`LAYER_ENEMY`) | Enemy fighters, destroyer parts | World only (parts collide with nothing) |
| Enemy hurtbox | 8 (`LAYER_HURTBOX`) | `Hurtbox` areas on enemy fighters (6.6 × 3.8 × 5.2 m; the collision box is 6.2 × 2 × 5.6) | nothing: only friendly bolts and the crosshair ray see it |

- **Crashing:** if the player's ship collides with anything, it takes `crash_damage` 30 (once per `crash_cooldown` 0.5 s) and bounces off over `crash_recover_time` 0.6 s: the nose swings smoothly (`crash_turn_sharpness` 5) to a glancing deflection (`crash_deflect` 0.5), a fading push (`crash_push_speed` 10 m/s, `crash_push_fade` 4/s) carries it clear, steering is ignored meanwhile, and the camera shakes (`crash_shake` 0.6). All in the *Crash* export group on `Ship`. Wingmen and enemies just slide or steer around.

**Laser masks:** player bolts use mask `13` (World + Enemy + Enemy hurtbox) and enemy bolts use `3` (World + Friendly), so neither side can shoot itself. The player's crosshair ray uses World + Enemy + Enemy hurtbox. Both query areas (`collide_with_areas`) and pass the collider through `Hurtbox.resolve()` to get the fighter. **If you add something new, decide its layer first.**

### Groups (how systems find each other)

| Group | Members | Used by |
|---|---|---|
| `player` | `Ship` | HUD, enemies, space dust |
| `wingmen` | `Wingman` ×3 | WingCommand, HUD |
| `enemies` | `EnemyFighter` | HUD, Cover Me |
| `targets` | Asteroids, enemies, intact destroyer parts | Order targeting (`WingCommand.pick_target()`) |
| `obstacles` | Asteroids, enemies, destroyer and space station `ObstacleProxy` spheres, Juggernaut `ObstacleBox` boxes | AI obstacle avoidance |
| `hud` | HUD overlay | `call_group("hud", "add_score", n)` |
| `comms` | `Comms` | `Comms.find(get_tree())` from anything that talks |
| `wing_command` | `WingCommand` | HUD |
| `mission_control` | `MissionControl` (Peppy) | `EnemySpawner` calls `announce_destroyer(destroyer)` on it |
| `wing_command`, `enemy_spawner`, `destroyer` | singletons in the level | HUD |
| `terrain` | `Terrain` (planet missions only; joined in `_enter_tree`) | `ChaseCamera` ground clearance, AI ground avoidance, wingman slots, `EnemySpawner`, `Ship` turn back |
| `boundary` | `PlayBoundary` (missions with an edge; joined in `_enter_tree`) | `Ship` turn back, HUD warning, enemy patrols, `EnemySpawner` |
| `station` | `SpaceStation` (Space Station mission; joined in `_enter_tree`) | `main.gd` asteroid placement, `EnemySpawner` (wave spawn points, destroyer destination) |

### What makes something shootable
There's no base class for this. Lasers and the AI check for methods and properties instead:

| Member | Required? | Purpose |
|---|---|---|
| `take_hit(damage: int, at: Vector3)` | Yes | Called by `Laser` on hit. Its presence also makes it the crosshair's target. |
| `radius: float` | Recommended | Aim assist, fire tolerance and avoidance (`Fighter.radius_of()` falls back to 5) |
| `signal destroyed` | Recommended | Wingman orders end when it fires |
| `notify_shot(from: Vector3)` | Optional | Told where the shot came from, just before `take_hit` (enemies use it to evade, the player's ship for the HUD's hit-direction arc) |
| `is_destroyed: bool` | Optional | For things that stay in the scene after dying (destroyer parts): the crosshair ignores them when true |
| `highlight_on_crosshair: bool` | Optional (default on) | Whether the crosshair turns red over it (`Fighter.highlights_crosshair()`). Off on asteroids; on, as exports, on enemy fighters and destroyer parts |
| `attack_target: bool` | Optional (default on) | Whether the Attack order can pick it (`Fighter.is_attack_target()`, checked in `WingCommand.pick_target()` and `order_attack()`). Off on asteroids |

Guard `take_hit` against being called again after death. Several bolts can land in the same frame, so check `if health <= 0: return` first.

### Processing order (physics priorities)
Ships run at priority 0 → wingmen at 5 (they follow this frame's leader position) → `ChaseCamera` at 10 → `IntroCutscene` at 20. Keep this in mind if you add something that reads another node's position.

### Input
Input actions are **registered in code** by the `Settings` autoload (`settings/settings.gd`), not in the Input Map. It replaces the events of any Input Map action with the same name, so don't define gameplay actions in *Project Settings → Input Map*.
- **Slots:** each action has three binding slots: Primary and Alternate for keyboard/mouse, and one Gamepad slot. `_default_bindings()` holds the defaults.
- **Saving:** the player's choices are saved to `user://settings.cfg`, along with fullscreen and resolution. Delete that file to get the defaults back.
- **Mouse steering:** mouse movement isn't an action, so it isn't rebindable (`Ship._unhandled_input`).
- **Menus:** the title screen, pause menu and settings screen use Godot's built-in `ui_*` actions. Godot's defaults have no gamepad accept or cancel button, so `Settings` adds A to `ui_accept` and B to `ui_cancel` at startup.
- **Input device:** `Settings.using_gamepad` follows the last real input, and changes emit `input_device_changed`. On a gamepad the HUD hides the mouse steering cursor and the select-key hints on the wing cards. There's no on-screen control list; the controls live in Settings → Controls. `Settings.describe*()` can produce binding text if one is added later (e.g. on the pause screen).

### Tuning
Gameplay numbers are `@export`s grouped in the Inspector (`Speed`, `Handling`, `Weapons`, `Senses`, `Patrol`, `Evade`, `Formation`, `AI`…). Scenes override them per ship type. For example, `wingman.tscn` raises the turn rates, and `enemy_fighter.tscn` sets its own speeds, spread and laser. **Change balance in the scenes or the Inspector, not in script defaults**, unless you mean to change every ship.

---

## 5. Systems reference

### Player (`Ship`)
- **Mouse steering:** the mouse moves a virtual stick, shown as the cursor ring on the HUD. It stays where you leave it; `mouse_recenter` makes it drift back to centre.
- **Shields:** 100. Enemy bolts do 4. The shields stop every shot while they have at least 1 point; once they are knocked out (`shields_down`), the next hit destroys the ship and `died` fires. Damaged shields recharge at 10/s after 3 s without a hit. Knocked-out shields stay offline for 12 s (`shield_reboot_time`) before recharging from zero. `shields_depleted` / `shields_online` signal the transitions. The bubble effect is `effects/shield_effect.gd` + `effects/shield.gdshader` on the `Model/Shield` node.
- **Throttle:** min, cruise and max speed 20, 60 and 130 m/s (`ship.tscn`), reached at `acceleration` 60 m/s² (raised from 35; wingmen keep 35 in `wingman.tscn`): cruise to full throttle in about 1.2 s (was 2.0), cruise to minimum in about 0.7 s (was 1.1).
- **Thruster heat** (*Thrusters* exports on `Ship`): throttling up or down heats them in proportion to the throttle; `heat_time` 5.2 s at full throttle overheats them (half throttle 10.4 s). Released, they cool in `cool_time` 3 s. Overheated, the throttle is ignored (back to cruise) for `overheat_time` 3 s while the heat drains. Signals `thrusters_overheated` / `thrusters_cooled`. Player only. **`thrusters_overheat`** off (as on `ship.tscn` now) turns it all off and hides the bar: the throttle is unlimited, and destroyer turret lock-on is what stops you hanging back to spray the destroyer.
- **What wingmen engage:** `aim_target` is whatever is under the crosshair right now. `fire_target` is what you've been shooting in the last 1.5 s; wingmen in formation engage it.
- **Cutscenes:** setting `controls_enabled = false` puts the ship on autopilot, flying straight at `autopilot_speed`.

### Wingmen (`Wingman`) and orders (`WingCommand`)
- **The squad:** up to three wingmen in `levels/level_base.tscn` (shared by every mission).

  | Wingman | `wing_index` | Slot | Breaks off | Selected with |
  |---|---|---|---|---|
  | **Falco** | 0 | Left | Left | D-pad left / 1 |
  | **Slippy** | 1 | Top cover: 10 m above, 10 m ahead (upper middle of the screen, clear of the crosshair) | Upward | D-pad up / 2 |
  | **Krystal** | 2 | Right | Right | D-pad right / 3 |

  Each node sets its place in the wing (`wing_index`, `break_side`, `slot_offset`) and its `speaker`, a `Pilot` file in `comms/speakers/` that holds the character: name (`call_sign`), `accent_color` (fin panel and HUD colour) and lines.
- **Order vs. state:** `order` is what the player told a wingman to do (`FORM_UP`, `ATTACK`, `COVER_ME`). `state` is what it's physically doing (`FOLLOW` the slot, or `ATTACK` something).
  - **Standing order:** `standing_order` is Form Up, Cover Me or Weapons Free. An Attack order returns to it once the target is gone (`Wingman.target_gone()`: freed, or `is_destroyed` for destroyer parts).
  - **Two kinds of method:** the `assign_*()` methods change the order. `command_attack()` / `command_follow()` only move the wingman, and Cover Me uses them to engage threats without changing the order.
- **FOLLOW:** hold `slot_offset` beside the leader. They only fire with the leader when `is_in_formation()` (within 10 m of the slot and within 20° of the leader's heading).
  - **Near the camera** (*Camera fade* exports): when the chase camera comes within `camera_fade_distance` of a wingman's hull box, its meshes fade (`GeometryInstance3D.transparency`, up to `camera_fade_max`). Mostly seen when a wingman rejoins or roams past the camera.
  - **Formation flight** (*Formation flight* exports in `wingman.gd`, `#region Formation flight`) takes over near the slot. It's fully on within `assist_full_range` (25 m) and fades out by `assist_fade_range` (70 m).
  - **Arriving from behind:** catch-up speed is capped so the wingman can brake to your speed by the slot at `arrival_deceleration` (30 m/s²). It approaches beside its slot (`join_approach_offset` 12 m out, above for Slippy) and slides in over the last 40 m, never past your ship. Formation flight's pull is capped the same way and builds up at most at `slot_pull_rate` (45 m/s²). Final braking is about 45 m/s², down from 114–175 (the old "snap").
  - **Too fast to stop gently** (closing over `overshoot_margin` 5 m/s faster than that, more than 25 m out): sails past the slot slowing at 30 m/s², then drifts back into it. 40 m behind at 120 m/s: 58 m past, back in 4.8 s, braking 34 m/s².
  - **Far ahead of the slot** (Form Up after an order left them in front of you): more than `rejoin_turn_distance` (70 m) from the slot and over 20 m ahead, a wingman somersaults back (*Somersault* exports, `_stunt` stages `PULL_UP` → `BACK` → `PULL_THROUGH`). It loops up and over at `somersault_speed` (40 m/s) and `somersault_pitch_rate` (3 rad/s, a cheat: normally 1.8), flies back upside down in a lane above the formation (at least `somersault_pass_clearance` 20 m off your line), then pulls through to come out `somersault_exit_behind` (20 m) behind its slot, beside it, and arrives as above. One already facing away turns round flat and half-rolls onto its back first. 3.9–5.9 s from 80–300 m ahead, at any leader speed, facing either way, closest pass 11.6 m. Within 70 m it slows and lets you catch up.
  - **Behind the slot but facing away** (e.g. after an attack run): turns round towards `rejoin_turn_out` (60 m) out on its side, never across your path.
  - **Formation flight only engages** while the wingman faces within about 37–73° of your heading (`ASSIST_MIN_ALIGNMENT` / `ASSIST_FULL_ALIGNMENT`), tilted by the slot's climb or dive.
  - **How it works:** the wingman turns and rolls with the leader, anticipating the leader's current turn rate (`_update_rotation` override). It also moves with the slot's real velocity plus a spring onto it. This uses `Fighter._velocity_offset()`, the one way a ship can move other than straight ahead, capped at `max_slot_correction`.
  - **Why:** the leader can bank-and-yank or roll hard without sweeping through a wingman, and formation fire stays on target.
  - **Banking:** formation flight turns the ship without the stick, so wingmen bank the model from their measured turn rate (`_turn_rates`, via the `Fighter._visual_turn_rates()` hook), rescaled to the leader's `pitch_rate` / `yaw_rate` in formation: same turn, same bank angle as the player.
  - **When it lets go:**
    - immediately on any order;
    - quickly while dodging an obstacle, pulling up from the ground or a building, or after scraping something;
    - whenever the leader is dead.
  - **Sideways slide:** `velocity_heading_blend` points the nose partly along the direction of travel, hiding most of the slide. `vertical_heading_blend` 1.0 does the same for pitch: the nose climbs and dives with the slot (vertical slide 7.6° → 2.3° on city passes).
- **ATTACK:** peel off and go after `target` until it's destroyed, then go back to the standing order.
  - **Aiming at turning targets:** wingmen have `lead_turns` on (set in `wingman.tscn`). This adds a turn that matches how fast the target crosses their view (`AIPilot._tracking_stick()`). Without it, the plain steering trails a turning fighter by about 10°, which is outside the fire window, so they chase without shooting. Elite fighters (`enemy_fighter.tscn`) have it on too; light fighters override it off. Turning it on makes any pilot a much better shot.
  - **Sharing a target:** wingmen on one target would otherwise settle into the same spot behind it.
    - Each one gives way to those with a lower `wing_index` and hangs back `pursuit_stagger` (30 m) per senior on the target (`_pursuit_offset()`).
    - If it still bunches up with a senior within `crowd_distance` for `crowd_time`, it peels off for a fresh run (`_check_crowding()`).
- **Selection** (`WingCommand.selected`):
  - **Selecting:** D-pad left / up / right (or 1 / 2 / 3) toggle Falco / Slippy / Krystal. D-pad down (or 4) selects everyone, or deselects everyone if all are already selected.
  - **Clearing:** the selection clears after each order.
  - **While paused or in cutscenes:** input is ignored.
- **Routing** (`WingCommand.recipients()`):
  - **With a selection:** orders go to the selected wingmen.
  - **With no selection:** they go to everyone whose standing order isn't Cover Me.
  - **If that's nobody:** nothing happens, silently.
  - **Reissuing:** Wingmen already following an order ignore reissues (no update, no acknowledgement), except Attack on a new target.
- **Orders** are always assigned, never toggled:
  - **Attack (F / Y):** targets what's under the crosshair, or failing that the target nearest it. Enemy fighters get twice the aiming slack. Only things whose `attack_target` is on count: never asteroids, so with a rock under the crosshair it picks the enemy nearest it. With nothing in reach, no one is ordered and the selection is kept (no message: the empty crosshair says it).
  - **Cover Me (C / X):** a standing order. Each frame, enemies in `CHASE` are threats, assigned one per covering wingman where possible. A wingman stays on its enemy until that enemy goes back to `PATROL` or dies. Between threats it waits in a trailing slot `cover_trail_distance` (35 m) behind its normal one, and doesn't fire with you. It goes straight for a threat, skipping the fan-out split that Attack orders use (`command_attack(target, false)`).
  - **Form Up (R / B):** a standing order; back into formation. The action is still called `command_cancel` so saved bindings carry over.
  - **Weapons Free (V / A):** a standing order (`_free_goal()`, `#region Weapons free`). See *Weapons Free* below.
- **Weapons Free:** with no target, the wingman roams around the leader. It picks points within `free_roam_radius` (208 m, mostly ahead), in the leader's local space so they move with it.
  - **Staying close:** outside `free_leash` (325 m) it heads back at `boost_speed` (150 m/s; its `max_speed` 80 is slower than your full throttle). With you weaving at full throttle: 150–330 m away on average, 1–33% of the time past the leash (an engagement in progress is never broken off). Roam routes steer around the leader, which isn't an AI obstacle (`_steer_clear_of_leader()`).
  - **Picking targets:** it engages enemy fighters within `free_detect_range` of itself and `free_engage_radius` of the leader. Fighters no other wingman is on come first (`_pick_free_target()`); it only doubles up when every nearby enemy is taken.
  - **Cooldown:** after shooting down an enemy fighter itself, the wingman waits `free_kill_cooldown` (2–3.5 s) before picking a new target, roaming meanwhile (`_free_cooldown`, set in `notify_kill()`). Losing a target any other way (someone else's kill, the enemy leaving) starts no cooldown.
  - **Never disengages:** once engaged, it stays on the target until it dies, however far the chase goes, then returns to roaming.

### AI Pilots and Accuracy
- `ai_pilot.gd` (base class for enemies and wingmen) uses `aim_scatter` (export) to add random noise to the true aim point. Wingmen default to 4.0, Elite fighters to 2.0.
- `lead_turns = true` allows an AI to steer its nose ahead of moving targets. Elite fighters and wingmen have this on; light fighters have it off.
  - **Off on this order:** formation flight and formation fire.
- **Signals:** `selection_changed`, `order_feedback(message)` (emitted for orders that went out; nothing shows it) and `Wingman.order_changed`.
- **Comms lines** (`acknowledgements`, `celebrations`, `praise`, `celebration_chance` in each character's `Pilot` file, `comms/speakers/*.tres`; spoken via `WingCommand` and `Wingman.notify_kill`):
  - **Acknowledgements:** after each order, one recipient picked at random says one of its own lines (never the same as its previous one): Falco "You got it!" / "On it!", Slippy "Right away!" / "Understood!", Krystal "Yessir!" / "Yes, captain!". Low priority, so it's dropped if someone's already talking. An order that reaches nobody gets no line.
  - **Destroyers** are called out by Peppy, not the wingmen (see *Peppy* under Comms).
  - **Kill celebrations:** when a wingman's shot destroys an enemy fighter (not rocks or destroyer parts), there's a `celebration_chance` (25%) it says a random line from its pilot's `celebrations`, never on Form Up. Low priority. The laser reports kills to its shooter with `notify_kill(victim)`.
  - **Praise for your kills:** when your shot destroys an enemy fighter, a random wingman has its `celebration_chance` (25%) to say one of its pilot's `praise` lines (never the same twice in a row), on any order. Low priority. `Ship.notify_kill()` → `WingCommand.praise_player_kill()`.
- **Wingmen are invulnerable:** they have no `take_hit`.

### Enemies (`EnemyFighter`)
A state machine. The HUD doesn't show the state (every enemy marker is the same red); the player reads it from how the fighter flies.

| State | Behaviour | Leaves when… |
|---|---|---|
| `PATROL` | Wanders within 250 m of `patrol_center` | Spots the player: within a 45° half-angle cone, within 400 m, and with clear line of sight → `CHASE` |
| `CHASE` | `_attack_goal(player)` | No line of sight for 3 s → `SEEK`. Player dead → `PATROL` |
| `EVADE` | Jinks away from the shooter at full speed for 2.5 s, then ignores hits for 4 s | Done → `CHASE` if the player is visible, else `SEEK` |
| `SEEK` | Searches near where the player was heading (60° cone, 450 m) | Spots the player → `CHASE`. After 12 s → `PATROL` |

Any hit triggers `EVADE` (outside the cooldown), through `notify_shot`. **Asteroids block line of sight.**

**Model (the Venomian "Mantis"):** one `.glb` (`models/enemy_fighter/`, built by `source/build_enemy_fighter.py`) for both types, about 6.2 × 5.7 m. `FighterModel` on `Model/Mantis` paints `Fighter_Accent` and `Fighter_Lights` (eye, pincer tips, wing leading edges, tip-plate fronts): elite purple + red lights (energy 10), light fighter tan + orange (energy 8, overridden in `light_fighter.tscn`). Engine glow: `Model/Glow`, one oval over the twin nozzles. Muzzles at the gun tips (±0.95, −0.42, −2.15). Damage smoke from `Model/SmokePoint` at the engine (0, 0.3, 2.2). Hurtbox 6.6 × 3.8 × 5.2 m, centred 0.5 m forward (about the old 5.5 m cube's hit rate, slightly higher); collision box 6.2 × 2 × 5.6, same centre; `radius` 3.5.

**Waves (`EnemySpawner`):** `enemy_scene` sets the level's fighter type for both waves and destroyer hangars. The base level (`levels/level_base.tscn`, so every mission) uses `light_fighter.tscn`; the script default is the elite `enemy_fighter.tscn`. 3 fighters, then one more per wave up to 8. Each wave spawns 600 m out, roughly ahead of the player and facing random directions, pushed `spawn_station_margin` (100 m) clear of a space station if there is one. Every 5th wave also brings a destroyer (`destroyer_every`, 0 = never). The next wave comes 6 s after every enemy is gone, destroyer included. At most `max_fighters` (12) enemy fighters can be alive at once, counting hangar launches. Anything that should hold up the next wave must be registered with `spawner.track(node)`. Waves don't start until `start()` is called.

### Destroyer (`Destroyer`)
- **Which ship:** every mission spawns the **Juggernaut** (`enemies/juggernaut.tscn`, set as `destroyer_scene` on the `EnemySpawner` in `level_base.tscn`); the previous ship, `destroyer.tscn`, is kept (set `destroyer_scene` back to switch). The values in the bullets below are `destroyer.tscn`'s unless marked; the Juggernaut's are in the table.

  | Juggernaut | Value |
  |---|---|
  | Size | about 1,050 × 306 × 329 m |
  | Bridge | (0, 204, 195), `radius` 50, health 70, score 3 |
  | Thrusters | keel (0, 30, 502.5) `radius` 40; sides (±93, 54, 502.5) `radius` 34; health 46, score 2 |
  | Hangar doors | (±132, 36, 15), 114 × 51 m, `open_height` 54; health 29, score 2 |
  | Turrets | 8, `juggernaut_turret.tscn` (same values as the old turret): bow glacis (±22.5, 112.7, −360), sponson plates (±112.5, 121, −165), main deck (±78, 115, −82.5), castle bastions (±63, 188.5, 195); positions from `MOUNT_PADS` in `juggernaut_c2.py` |
  | Hull collision | trimesh from the model (`hull_collision_from_model`) |
  | AI avoidance | 15 `ObstacleBox` nodes under `AvoidanceBoxes`, fitted to the hull and bridge (no face more than ~25 m off the hull), `margin` 10 each; edit them in the editor (drawn as cyan boxes; `size` or scale); spheres only on the thrusters (`proxy_radius` 0, no `extra_proxies`) |
  | Warp | `portal_radius` 190, `portal_height` 95; through at 12 s, active at 17 s |
  | Parking | `stop_distance` 375 (bow 560–600 m from the station's centre, parked at 130 s) |
  | Death | `death_blast_height` 150, `death_blast_size` 60–125, `final_blast_size` 290 |
- **Arrival (warp in, `warp_in` on by default):** placed on `zone_radius` (3000 m on the Space Station mission, inside its 4000 m boundary; elsewhere usually the boundary itself) in a random direction, then moved out to a `WarpPortal` (`effects/warp_portal.gd`) `portal_margin` 50 m beyond that (`portal_radius` 230 m, centre `portal_height` 30 m up). The portal opens over 1.5 s (crimson flash, deep rumble); after `warp_charge_time` 1 s the ship comes through at `warp_speed` 100 m/s, hidden behind the portal plane by a clip plane (`toon_clip.gdshader`, `clip_plane` instance uniform) and with collision off; once the stern is out (8.9 s) the portal shuts and the parts can be shot (`is_damageable()`); it brakes to cruise over `warp_brake_time` 5 s, then turns solid and goes active (13.9 s: turrets, hangars). With `warp_in` off: fades in over `fade_in_time` 4 s where it was placed. Then it crawls inward at `cruise_speed` (10 m/s on `destroyer.tscn`; script default 8) and stops `stop_distance` (200 m) from the centre (in a level without a space station). **On the Space Station mission** the centre holds the space station, so `EnemySpawner` sends it to a point `destroyer_station_clearance` (300 m) outside the station's bounding sphere (427 m) on the side it came from: it parks about 158 s after spawning with its centre about 930 m from the station (closest approach between its avoidance spheres and the station's over 30 arrivals: 135 m). It smashes asteroids in its path with `Asteroid.shatter()`, which awards no score. Fewer working thrusters make it slower.
- **Model:** our own, about 737 × 350 m, 278 m tall (`SCALE` 2.0 in the script; was 552 × 263 at 1.5, and 368 × 175 before that): forked prow with an open gap, bridge tower, three thrusters, side hangars; gunmetal, crimson, amber, red-orange engines. Surface detail from `add_detail()`: armour plates with panel lines, lit window rows, red running lights, conduits and machinery; underneath (`add_underside()`), a stepped two-tier keel (the lower tier is solid, with collision), large plates, a crimson spine with floodlights, a glowing ventral bay, keel windows and radiator fins (decoration only: no collision, clear of turrets, seeded, batched per material; hull about 42,500 triangles). Built in Blender by `models/destroyer/source/build_destroyer.py` (game coordinates; colours are the sRGB values the game shows), exported as four `.glb` files and cel-shaded at load (`ToonMaterial`).
- **Hull and parts:** the hull is the `AnimatableBody3D` root, on the World layer. All damage goes through `DestroyerPart` children on the Enemy layer, and the parts ignore hits until `is_damageable()` (out of the portal, or faded in, and not dying), and the Attack order can't pick them before that. Turrets and hangars wait for `is_vulnerable()` (active and not dying).
- **Kill rule:** destroying the bridge **and** all three thrusters starts a chain of explosions, then a fade-out, then `destroyed`.
- **Turrets (`DestroyerTurret`):** a destroyed turret is disabled, charred and stays on the hull.
  - **Targeting:** the player if within `aggro_range` (450 m); otherwise the nearest wingman in range.
  - **Firing limits:** pitch is limited to −5°…80°, so there are blind spots. Each turret needs a clear line of fire past the hull and asteroids.
  - **Lock-on** (*Lock-on* exports): below `lock_speed` 50 m/s a turret locks on to its target, fully in `lock_time` 3 s at or below `crawl_speed` 25 m/s (slower in between); above 50 m/s the lock breaks in `unlock_time` 1 s. Locked, it fires every `locked_fire_interval` 0.15 s (from 1.4), with `locked_spread_deg` 0.2° (from 1.5°), turns at `locked_turn_rate` 3 rad/s (from 1.2) and leads along the target's curving path (`accel_tracking` 4). Circling behind the engines (4 runs each): about 2.2 hits/s at 20 m/s (1.6–2.7; full shields gone in about 6 s once locked), 0.75 at 35 m/s, none at 50 m/s or above (before lock-on: under 0.1 at any speed).
- **Hangars (`DestroyerHangar`):** every `launch_interval` (40 s, first launch 15 s after going active), the next intact hangar opens its door and launches 3 fighters, within the fighter cap.
  - **Launched fighters:** they fly straight out for 2 s via `EnemyFighter.begin_launch()`, with collisions off so they can leave through the hull, then patrol in front of the bay.
  - **Destroying a door** blows it off and stops launches from that side.
- **Health and score:**

  | Part | Health | Score | `radius` |
  |---|---|---|---|
  | Bridge | 70 | 3 | 40.5 |
  | Each thruster | 46 | 2 | 22.5 |
  | Each hangar door | 29 | 2 | 22.5 |
  | Each turret | 12 | 1 | 6 |
  | Killing the destroyer | | +10 | |

- **AI steering:** `_build_obstacle_proxies()` fills `hull_outline` (top-down (x, z) outline, set in `destroyer.tscn`) with 24 m `ObstacleProxy` spheres every 30 × 37.5 m, plus `extra_proxies` from the model script's `proxies.txt` (tower, superstructure, hangar housings, and layers filling the deck and keel) and one per thruster: 141 in all. The gap between the prongs is open for the player; the AI avoids it. If you change the model, re-export, paste the new `collision.txt` pieces and `proxies.txt` line, and update `hull_outline`, part positions, radii and shape sizes (all ×`SCALE`).
- **Wingmen vs. parts** (Attack order, 4 runs): turret 3.6–4.1 s, bridge 5.9–6.4 s, centre thruster 18–33 s (it still makes them scrape the hull in most runs). The old ship: 4.1–5.2 s, 13.6–38.8 s, 38 s to never.

### Intro (`IntroCutscene`)
1. Places the formation at the `IntroStart` marker on autopilot. The HUD is hidden and the camera's physics is turned off.
2. The camera sits still at `IntroCameraSpot` and turns to follow the fighters.
3. Once the player is `handover_distance` past it, the camera flies to `ChaseCamera.chase_transform()`.
4. Snaps the camera into place, enables controls, fades the HUD in and emits `finished`.

`main.gd` keeps asteroids out of the fly-in lane (`_blocks_intro`), because ships on autopilot don't dodge. **Move the markers (`IntroStart`, `IntroCameraSpot`, in `levels/level_base.tscn`, overridden per mission) to reframe the shot.** The lane follows them automatically. On the Space Station mission they are overridden in `main.tscn` to fly in towards the space station.

### Comms (`Comms`)
The dialogue box, bottom left: a portrait square with the speaker's name under it, and the line typing out in a box to its right.
- **Opening (0.3 s):** the square expands from a 2 px line (`expand_time` 0.09 s), shows static (`noise_time` 0.09 s), then the portrait and name appear as the text box unfolds to the right (`unfold_time` 0.12 s). Typing (and a recorded voice) starts after that. **Closing** is the same in reverse, except that the portrait and name give way to static as soon as the text box starts folding. All driven by `_open_t` / `_apply_open()`.
- **Talking:** `Comms.find(get_tree()).say(speaker, text, priority, voice)`. `speaker` is a `CommsSpeaker` resource from `comms/speakers/`; each `Fighter` has a `speaker` export (Fox on `ship.tscn`, each wingman overridden in `levels/level_base.tscn`).
- **Priorities:**
  - **LOW** never interrupts. One arriving while a line is on screen is dropped (`say()` returns false).
  - **HIGH** interrupts LOW at once: same speaker, it just types; different speaker, a `noise_time` burst of static over the portrait first (`SWITCHING`). A HIGH arriving during another HIGH queues behind it.
  - A queued line (or a LOW one arriving while the box closes, with nothing queued) turns the closing box around at the static instead of letting it collapse.
- **Typing:** `chars_per_second` (40), with short pauses after punctuation. The label wraps the whole line up front (`VC_CHARS_AFTER_SHAPING`), so words don't jump lines mid-type. A line stays up `hold_time` plus `hold_per_char` per character, then the box closes.
- **Audio:**
  - **Voice:** a line with a `voice` stream plays it instead of beeping, and stays up until the recording's length has passed. This is timed rather than read from the player, so a dead audio device can't stick a line on screen.
  - **Beeps:** otherwise every `beep_every`-th letter (2) beeps at the speaker's `beep_pitch`. The beep is generated in code (`_make_beep()`).
- **Portraits:** set `portrait` on a speaker resource (all five have one: `comms/portraits/*.png`, 256×256, mipmaps on). The square crops to fill, over a backdrop of the speaker's colour darkened by `portrait_backdrop_darken` (0.72), so transparent backgrounds work; turn mipmaps on in the image's import settings (the square samples them). Without a portrait it shows faint static (`empty_portrait_static` 0.3).
- **Peppy** (`comms/speakers/peppy.tres`, an `Advisor`; red, beep pitch 0.85) doesn't fly: `MissionControl` (in `level_base.tscn`, group `mission_control`) has him speak, all at HIGH priority. Destroyer arrival: a `destroyer_warnings` line, then `destroyer_hints` for the mission's first destroyer or `destroyer_reminders` after. Progress: `bridge_down` (thrusters remain), `last_thruster` (one left), `thrusters_down` (bridge remains), `destroyer_killed` (when the hull finally blows, about 5 s after the last part). Lists never repeat their last line.
- **Layering:** it's its own `CanvasLayer` (layer 5, above the HUD, below the pause menu), so it shows during cutscenes while the HUD is hidden. It pauses with the game.

### UI
- **HUD:** drawn in code in `ui/hud.gd` (`_draw()`, redrawn every frame). There are no Control nodes per element. To add an element, write a `_draw_*` helper and call it from `_draw()`.
- **Gauges** (`_draw_gauges()`, top right): two bars (`BAR_WIDTH` 220 × `BAR_HEIGHT` 12 px, `BAR_GAP` 10 apart), no labels or numbers; an icon left of each in the bar's current colour (`_draw_gauge_icon()`, `GAUGE_ICON_SIZE` 7 px half-size, `GAUGE_ICON_GAP` 7): a filled shield (`SHIELD_ICON`; filled so it isn't the outlined Cover Me icon) and a flame with a see-through core (`FLAME_ICON` minus `FLAME_HOLE`, filled as two halves from `_split_ring()`). Each is baked once, white, into a cached texture (`_gauge_icon_texture()`, like the wingman markers) and tinted when drawn, so the blinking flame fades evenly. Shields on top: green; while the shields are down, it turns red and fills as they reboot. Thrusters underneath: blue (`COLOR_THRUSTERS`), full when cool, emptied by throttling (`1 - thruster_heat`); empty = overheated. During the lockout it refills in red, blinking slowly (`OVERHEAT_BLINK_PERIOD` 1 s fade cycle down to `OVERHEAT_BLINK_MIN_ALPHA` 0.2); full again = throttle back. Score is still counted in `hud.score` but not shown.
- **Enemy brackets** (`_draw_enemies()`): only within `enemy_marker_radius` 320 px (set in `hud.tscn`) of the crosshair (popping in and out, no fade), and never while something on the World layer (terrain, asteroid, destroyer) hides the enemy from the camera (`hide_hidden_enemies`, one ray per enemy per physics tick). Clouds don't block (no collision). HUD exports, *Enemy markers* group.
- **Radar** (`_draw_radar()`, top left): shows enemy fighters, wingmen and the destroyer within `radar_range` (500 m). The destroyer is a red silhouette of its hull outline, 20 px long at any range (`RADAR_DESTROYER_LENGTH`), turned to its heading, with a short above / below line (`RADAR_DESTROYER_TICK` 6 px); out of range it sits on the rim, smaller and dimmer (`_draw_radar_destroyer()`). Its on-screen size is `radar_radius` (80 px in the base layout); both are exports on the HUD node in `levels/level_base.tscn`. Enemies further away sit on the rim in their direction as smaller, dimmer ▲ / ▼ / ■ icons (above / below / level; `RADAR_FAR_SCALE` 0.65, `RADAR_FAR_ALPHA` 0.6). It's the main way to find off-screen enemies: they get an edge arrow only within `sense_range` 150 m ("pilot senses": full `sense_opacity` 0.85 inside `sense_full_range` 50 m, fading out by 150 m; *Pilot senses* exports). The destroyer and Attack targets always get one.
  - **Orientation:** positions are in the ship's local space, so ahead is up and the radar turns and rolls with you.
  - **Enemy symbols:** ▲ above you, ▼ below, ■ level (`_radar_height()`: within `RADAR_LEVEL_DEG` or `RADAR_LEVEL_METRES`).
  - **Wingmen:** dots in their colours, with a height tick. They're kept at least `RADAR_WINGMAN_MIN` px from the centre so the formation stays readable.
- **Hit direction** (`_draw_hit_direction()`): a red arc around the screen centre on the side an enemy shot came from, fading over `Ship.shot_flash_time` (0.8 s). Set by `Ship.notify_shot(origin)`, which lasers call before `take_hit()`.
- **Wing panel** (`_draw_wing_panel()`, bottom right): laid out like the D-pad, with Falco left, Slippy top, Krystal right and ALL below.
  - **Each card** (base layout 56 × 56 squares, 5 px apart, ALL 56 × 20, names 13 px, all scaled by `WING_PANEL_SCALE` 1.15 to about 64 × 64; translucent backgrounds with `CARD_CORNER_RADIUS` 6 px (scaled) rounded corners and no outline, one reused `StyleBoxFlat`): an icon for the current order on top, in the order's colour (`_draw_order_icon()`), with the call sign centred under it: Form Up three dots in a V (green), Attack a crosshair (orange), Cover Me a shield (blue), Weapons Free a burst (red). There's deliberately no live status (attacking, roaming...): the player can see that. The one exception: on Form Up, the icon fades slowly out and in while the wingman is still joining and not yet firing with you (`Wingman.joins_leader_fire()` false for over `JOIN_BLINK_DELAY` 0.4 s, so brief drops in hard turns don't flicker it; a `JOIN_BLINK_PERIOD` 1.2 s cycle down to `JOIN_BLINK_MIN_ALPHA` 0 (invisible), timed by `_joining_for`). Selected cards are tinted in the wingman's colour, and on keyboard the select key shows in the corner.
  - **The middle:** who the next order would go to.
- **Wingman markers:**
  - **Triangles:** a solid downward triangle over each wingman in its own colour, with its initial in bold white (`WINGMAN_MARKER_SIZE` 36 × 29 px, letter size `WINGMAN_INITIAL_SIZE` 15; cached as textures, see `_wingman_marker()`; bold through a `FontVariation` with `variation_embolden`). They look the same whether or not the wingman is selected (selection shows on the wing panel only).
  - **Targets:** only targets of an **Attack** order get an orange diamond listing who's on it (initials and distance). Targets picked by Cover Me or Weapons Free aren't marked.
- **Pause menu:** runs with `process_mode = ALWAYS`. It sets `get_tree().paused` and also pauses automatically when the window loses focus.
- **`SceneFader` autoload:** `SceneFader.change_scene(path)` fades out, swaps scenes and fades in. It's currently only used by the title screen when a mission is picked.
- **`Music` autoload:** `Music.play(level_music)` (same track = keeps playing; different = 1 s fade-out of the old one; `null` / `stop()` = fade to silence). `Level.music` and the title screen's `music` call it in `_ready()`. Plays on the **Music** bus (`default_bus_layout.tres`). −8 dB while paused. Lead → loop is gapless (`AudioStreamInteractive`).
- **Mission selector** (`ui/mission_select.gd`, node `MissionSelect` in `title_screen.tscn`): Start opens it. One button per `Mission` in its `missions` array, the highlighted one's description underneath, Back (Esc / B) returns to the title menu.

### Missions and levels
- **Missions:** `Mission` resources in `missions/` (`title`, `description`, `scene_path`). Space Station mission → `res://main.tscn`; Corneria → `res://levels/corneria.tscn`.
- **Shared base:** every mission scene inherits `levels/level_base.tscn` (root script `Level`). It keeps flat node names (`Ship`, `Falco`...). Changes to the base reach every mission unless overridden.
- **Space Station mission (`main.tscn`):** `PlayBoundary` radius 4000 m (turn back at 4200 m; at full throttle the ship gets about 4,345 m out; just past the 3800 m field). `asteroid_count` 640, `field_radius` 3800, `field_flatten` 0.25 (the same 640 rocks as at 1800 m, so about 9× sparser and twice as thick; history: 160 / 900 / 0.5, then 640 / 1800 / 0.25), `EnemySpawner.zone_radius` 3000 (destroyers warp in inside the area), `ChaseCamera.far` 10000 (base 5000). `GreatFox` at (0, 30, 5000), yaw -25°, behind `IntroStart`; the turn-back keeps you 384–394 m from its hull. Waves and patrols stay inside the boundary. `SpaceStation` at the origin, yaw 215° (bow and hangar towards the intro); the intro markers are overridden here (`IntroStart` (60, 30, 3700), 300 m inside the edge and about 1.3 km in front of the Great Fox; `IntroCameraSpot` (90, 34, 3400)) so the formation flies in from near the edge towards it and has it dead ahead (about 3.2 km away) at handover. `main.gd` `station_clearance` 40 m (asteroids from the station). `WorldEnvironment` uses `asteroid_field_environment.tres`: Corneria in the sky, `planet_direction` (-0.62, -0.42, -0.66), `planet_angular_radius` 22°, `night_brightness` 0.004 (near-black night side; city lights unaffected), `day_brightness` 2.5 and `day_saturation` 0.6 (sunlit side only).
  - **Station detail** (`build_space_station.py`): wheel frames at the 16 arc joints without a collar or module (`FRAME_ANGLES`, 0.5° wide), side-face conduits at r 376, outer plates per lathe segment (75% of them) between conduits at z ±9.5, 8 radiator fin clusters (`FIN_ANGLES`, 4 fins 9 × 16 m, 1.2° apart), an inner rail lit every other segment; spoke frames every 28 m (`SPOKE_RIBS`); 16 ribs per hub cone; cargo containers (9 × 12 × 20 m) in two rows at z -124 / -102, 6 tanks (r 7) over z 86–144 (`FITTINGS` widen the AI spheres there); hangar underplates and roof machinery. Each detail pass has its own seed.
- **`Level` exports:** `restart_delay` (3 s), `spawn_enemies` (off = no waves), `music` (a `LevelMusic`; empty = silence), `intro_line`, `intro_line_delay`, `intro_advisor_line` (said by MissionControl's advisor, Peppy, `intro_advisor_delay` 2 s after the player gets control, so not during the intro; empty = nothing; the Space Station mission sets "Stay sharp, team. I'm reading multiple enemy squadrons approaching our position."). The intro line is HIGH priority so that, if the intro was skipped and it is still on screen, the advisor's line queues behind it instead of cutting it off. Override `_build_world()` to generate a world (`main.gd` scatters asteroids there).

### Planet terrain (Corneria)
- **The Corneria map** (`models/corneria/`, built by `source/build_corneria.py` in Blender): 8 × 8 km, north = −Z. Sea and sea stacks south; a bay with six stone arches (openings ~80 × 120 m); a suspension bridge (30 m deck) over the river mouth; Corneria City (~170 blocks, towers to 340 m with the spire, red warning lights over 100 m); a 130 m plateau with a lake (surface 120 m) and a waterfall; hills, ridges, mesas, a canyon and coastal cliffs in the west; the military base (west) reached by a road through a graded valley; a harbour town with a lighthouse (east coast); irregular mountains on three sides; ~6,000 trees.
  - **Exports:** `corneria_map.tres` (a `TerrainMap`: 321 × 321 heights, per-cell paint 0 auto / 1 paved / 2 high water, `high_water_level` 120, per-cell structure heights) and `corneria_props.glb` (no sea: Terrain makes it). Re-export after editing the script; never hand-edit them.
  - **`Props`** (`MapProps` on the glb instance): toon materials (`unlined_materials` Corneria_Tree / TreeLight / Trunk without ink outlines, plus a shadow-only child per mesh so they still cast shadows), `water_material` on `Corneria_Water`, trimesh collision (World layer) for `solid_nodes` (all but streets, road, trees).
  - **Kit:** buildings, bridges, arches, stacks and trees are pieces from `source/corneria_kit.blend` (spec: `ASSETS.md`), copied in by `load_kit()` / `Batch.kit()`: scaled, turned, merged into the same group objects. Towers stack a base, 20 m shafts (`SHAFT`) and a crown; low blocks stretch a 10 m unit block; streets are 30 m pieces (`STREET_TILE`) between crossing pieces. Materials map by name to `PALETTE`; kit faces keep their facing and smooth shading.
  - **Falls:** the `Waterfall` node (not a prop) sits at `LIP` (the upper river's last point, the cliff's edge), transform from `waterfall.txt`. The script shapes the ground for it: river channel bed 108 m with banks rising through the water ~40 m out (`smoothstep(55, 22)`), raised to ≥126 m near the lip; lake bed 100 m out to e 0.55, banks by e 0.85; a plunge pool cut in front of the lip (`PLUNGE_HALF_WIDTH` 60 m, sheer face, pool from ~20 m out); the river's water stops `RIVER_SHORT_OF_LIP` 6 m before the lip; high-water paint stops 12 m behind it.
  - **Cost:** level loads in ~0.9 s headless; ~650 FPS uncapped at 1280 × 720 with 12 enemies over the city (same as the old 4 km test map). With the kit: 1.2–2.3 M triangles a frame, GPU 2.0–2.8 ms at 1280 × 720 (within ~0.2 ms of the old boxes); `corneria_props.glb` 22.6 MB.
- **`Terrain`** (`world/terrain.gd`): with `map` set (Corneria), its heights and size; otherwise noise: 4 × 4 km, seed 1984. 25 m cells in 8 × 8 chunks (204,800 triangles on Corneria, 51,200 for the noise map), one shared vertex per grid point with smooth normals (central differences, `_grid_normals()`).
  - **Noise height:** `base_height` 8 + hills ±70 (900 m wide) + ridged mountains up to 320 (none within 450 m of the centre) + boundary ring up to 520 (from 72% to 90% of the half-width), sinking below sea level at the very edge.
  - **Colour per pixel** (`effects/terrain.gdshader`, values handed over by `_feed_ground()`): sand (< 6 m above water), rock (normal.y < 0.78), snow (> 260 m), light/dark grass patches (`patch_scale` 350 m, `patch_threshold` 0.55) with a ±4% `mottle` (60 m); map cells painted paved get `paved_color` (paint map as an R8 texture, linear filtered). Every boundary is a hard edge wiggled by one noise (`edge_scale` 40 m; `sand_wobble` 2.5 m, `snow_wobble` 30 m, `slope_wobble` 0.06, `paint_wobble` 0.15). `rock_facets` 0 (flat per-triangle light on rock; ≥ 0.2 saw-tooths). Optional greyscale `grass_texture` (top-down, 20 m) / `rock_texture` (triplanar, 30 m), white by default. Colours and heights are Terrain exports; the rest are uniforms on the ground material (`Mat_ground` in `corneria.tscn`). Cost: within run-to-run noise of the old vertex colours (GPU 2.2–2.5 ms at 1280 × 720 from four views, both).
  - **Collision:** a `ConcavePolygonShape3D` per chunk from the same triangles (World layer); water and the 30 km far-ground plane have thin solid slabs. Crashes are the normal 30 damage + bounce.
  - **Backdrop** (`backdrop`, on in `corneria.tscn`; *Backdrop* export group): scenery past the map's edge, no collision or shadows. Rings round the map from its grid line `backdrop_inset` 150 m inside the edge (shared vertices; covers the sunk border) out to `backdrop_reach` 5.5 km past it, steps 50 m ×1.2. Edge heights carried out (smoothed over `backdrop_smoothing` 400 m), blending over `backdrop_blend` 1.5 km into ridged mountains: `backdrop_base` 40 + up to `backdrop_height` 600 m where noise crests pass `backdrop_crest` 0.5, `backdrop_scale` 2.2 km. Sea where the edge is below `backdrop_land_height` 20 m; coast from the land share along the edge over `backdrop_coast_smoothing` 3 km, wobbled ±`backdrop_coast_wobble` 0.35. One mesh per side, underwater triangles dropped. Corneria: 30k triangles, +70 ms load.
  - **API:** `height_at(x, z)` (exact, `-INF` off the map), `surface_height(x, z)` (ground or water, incl. a map's high water), `clearance_height(x, z)` (also the map's structure height on that cell). AI, spawner and turn-back use `clearance_height`; the camera uses `surface_height`; wingman slots use `surface_height`, plus a gradual lift over `clearance_height` (see below).
- **Water:** one opaque plane at `sea_level` 0 (`water.gdshader`); `water_to_horizon` (Corneria) extends it to the horizon. The plateau lake is part of the props. Shader: depth (from a heights texture Terrain sets, `_feed_water()`; the floor fades to `open_sea_depth` 100 m between 150 and 600 m from land, `water_depth_fade`, so no straight bands along the map edge) picks shallow / mid (3 m) / deep (12 m) bands; shore foam to 0.6 m plus lines rolling in from 4 m (bent by noise, `foam_wobble` 1.0 of the spacing over 10 m, uneven thickness, 30% left out as gaps: they followed the depth dead straight); wave crests (fade out by 1.8 km); sun sparkles on 7 m ripples; sky tint at grazing angles. No ink outlines: drawn in the transparent pass (`ALPHA *= 1.0`, `depth_draw_always`), material `render_priority` -50 (`Terrain.water_render_priority`) so it draws before bolts and other see-through things. Ripples never touch `NORMAL` (flat cel light). **Splashes and wake:** bolts hitting water (`Terrain.is_water_surface()`, within 0.5 m of `water_level_at()`) spawn `WaterSplash` (`Laser.water_splash`, `splash_size` 1) instead of the surface hit: `water_splash.gdshader` bends a cylinder into a jet (11 m, 6 spikes) and a crown (4.5 m, 11 spikes) over 1.1 s; a foam ring on the water (`WaterMarks.add_ring()`, 0.6→6 m over 1.2 s); prewarmed by `Level.prewarm_splash`. `WaterWake` on `ship.tscn` (wingmen too): strength = (1 − smoothstep(3, 12 m over water)) × speed / 90 m/s (0.67 at cruise); reports its trail to `WaterMarks` (point every 10 m, ≤24 per trail, ≤8 trails), which the water shader draws as a V of ragged, wandering, patchy foam bands (start 1.5 m out, spreading 12 m/s, 3.5 s) plus broken churn (1.6 s); two spray sheets (`water_spray.gdshader`, foot wobbling 0.9 m and frayed) beside the wingtips, 3 m ahead to 8 m back, 4.5 m tall × strength. Cost (1280 × 720): four wakes + 22 splashes/s ≈ +0.5 ms GPU.
- **`Clouds`** (`world/clouds.gd`): defaults 60 clusters of 5–9 blobs at 220 / 430 m (±30) within 1700 m, none within 350 m of the centre; Corneria: 170 at 650 / 950 m within 3600 m. Each cluster scaled 0.5–1.5 (`cluster_scale`), or with `big_chance` 6% a giant at 4–6.5 (`big_scale`) in the top layer + `big_lift` 100 m (Corneria: 7 giants, 370–920 m across). Fade up to 85% when the camera is inside or within 40 m. Corneria's use `effects/cloud.gdshader`: drifting noise lumps (16 m apart, 12 m high), bottoms squashed to 0.3 below 8 m under the centre, soft crevice shading on downward faces, three bands (white, pale blue, blue-grey underside), rim and silver lining; no ink outlines (transparent pass via `ALPHA *= 1.0`, which keeps the camera fade, plus `depth_draw_always`); blobs 20 × 12.
- **Environment:** `planet_environment.tres` (procedural day sky, sky ground colour = horizon, depth fog in the horizon colour: clear to 1.5 km, full at 5 km (the far plane), curve 1.6, `fog_sky_affect` 0; was exponential 0.00035, which washed out the near ground). Sun pitched higher, shadows to 600 m.
- **Camera:** `ChaseCamera.ground_clearance` 3 m above `surface_height()`.
- **Start:** 120 m over the sea at (−450, 120, 3400), heading north; intro start 300 m further south.
- **Enemies on Corneria:** the base level's waves, no destroyers (`destroyer_every = 0` on its `EnemySpawner`).
- **AI ground avoidance** (`AIPilot`, *Ground* group; only with a `Terrain`): goals raised to `ground_clearance` 25 m above `clearance_height()` (not an engaged target's lead point); flight path checked at 7 points over `ground_lookahead_time` 2 s, steep climb if any is below the clearance (`_ground_danger`). The AI flies over the city, not down its streets. Measured on Corneria (3 × 3 min around the city): 0 wingman and 1 enemy ground scrapes, no building hits; wingmen hop over buildings when you fly a street (72–88% in formation).
- **Wingmen near the ground:** `slot_position()` raises the slot to `formation_ground_clearance` 6 m over the ground under it and `formation_ground_lookahead` 1 s ahead. Near the slot, wingmen use 6 m / 1 s for their own check; if it fires (`_ground_danger`), formation flight lets go. In formation that check looks along the slot's path, ignoring its descent (`_ground_probe_direction()`). With the leader 15 m up: about 98% in formation, about 0.1 scrapes a minute.
- **Wingmen and buildings:** on top of that, `_structure_lift` aims the slot 6 m over the `clearance_height()` of its path for the next `structure_lookahead` 4 s (and `structure_side_margin` 8 m to either side), less `structure_climb_rate` 10 m/s × the time beyond `structure_ready_time` 2 s (so the ramp is done 2 s before the building). Only structures count, not a hill ahead (`_structure_excess()`). It moves like a climbing ship: `structure_lift_gain` 3 m/s per metre left, `structure_lift_accel` 25 m/s², at most `structure_lift_rise_speed` 40 m/s up and `structure_lift_fall_speed` 10 m/s down (`structure_lift_clear_fall_speed` 30 m/s with nothing ahead; braking to land softly), holding `structure_lift_hold` 1.5 s before descending. Wingmen hop over the rooftops beside you in smooth curves, never through a street canyon or under an arch. Scripted low city passes: vertical acceleration 193–242 → 13–15 m/s², formation flight dropped 198–261 → 1–4 times per 20 passes, no scrapes. Where the slot would need lifting more than `tuck_lift_threshold` 25 m (towers of 100–240 m beside a street), wingmen **tuck in** on your recorded flight path (`_trail`) instead, `tuck_spacing` 20 m × (`wing_index` + 1) behind you, sliding over `tuck_slide_time` 1.5 s and staying `tuck_hold` 2 s after the last tall building; tucked in, they skip the cell-based ground check, keep formation through grazes and hold their fire. Low street passes: time 30+ m above the slot 48–58% → 0.1–0.9%, average distance 57–81 → 25–28 m.
- **Enemy patrols:** roam points at least `patrol_min_altitude` 60 m up and `patrol_boundary_margin` 150 m inside the boundary, and moved out of obstacles (`_clear_of_obstacles()`: never inside the space station or a big rock).
- **Spawner (planet):** wave centre at least `spawn_altitude` 80 m up (each fighter at least 40 m over its own ground) and `spawn_boundary_margin` 250 m inside the boundary.
- **`PlayBoundary`** (`world/play_boundary.gd`): Corneria `radius` 3300 m (horizontal) around (0, 0, 500), `turn_back_margin` 200 m (negative = warning only). HUD: "RETURN TO THE COMBAT AREA" past the radius, "TURNING BACK" during the automatic turn.
- **Turn back (`Ship`, *Boundary* group):** past radius + margin the ship steers itself home (`turning_back`; roll ignored), pulling up hard if the ground is within `turn_back_clearance` 60 m; control returns within `turn_back_done_deg` 25° of the way home. About 3 s. A level, low run straight at a steep ridge can still clip it.
- **`GreatFox`** (`world/great_fox.tscn`): on Corneria, scenery at (500, 700, 4500) over the sea, yaw 70°, about 730 m outside the boundary, behind the intro approach. No collision or groups; `bob_height` 3 m, `bob_period` 14 s. At full throttle straight at it, the turn-back stops you about 160 m short (farthest 3,644 m from the boundary centre; with the old 2.5 s boost it was 257 m short at 3,549 m). Keep it beyond the boundary + turn-back margin. Also on the Space Station mission (see Missions and levels).

---

## 6. Common tasks

**Add a mission.** New inherited scene from `levels/level_base.tscn` under `levels/`; override start positions, environment, `spawn_enemies`, `intro_line`; add the world as child nodes, or a root script extending `Level` with `_build_world()`, plus a `PlayBoundary` for an edge; add a `Mission` .tres in `missions/` and put it in the `missions` array of `MissionSelect` in `ui/title_screen.tscn`. Details: GUIDE section 10.

**Add level music.** Audio files in `audio/music/`; *New Resource → LevelMusic* (set `loop`, optional `lead`, `volume_db`); drag it onto `Music` on the mission scene's root (or the title screen root). The loop file needs no loop import setting; a loop offset on import is respected. Details: GUIDE section 10.

**Tune difficulty.** Change `damage` in `weapons/enemy_laser.tscn`. On the root of `enemies/enemy_fighter.tscn`, change `spread_deg`, `fire_interval` and `max_health`. For wave sizes, select the `EnemySpawner` node in `levels/level_base.tscn` (or override it in one mission's scene). Detection settings are in the enemy's *Senses* group.

**Add a new shootable object.** Put it on the World or Enemy layer, implement `take_hit` (with the double-hit guard), and add `radius` and `signal destroyed`. Add it to `targets` if wingmen should be able to be ordered onto it, and to `obstacles` if AI should steer around it.

**Add a new enemy type.**
1. Duplicate `enemy_fighter.tscn`.
2. Keep `Model/MuzzleL` and `Model/MuzzleR`: `Fighter` fires from these.
3. Keep collision layer 4.
4. Adjust the exports, or `extends EnemyFighter` and override `_decide()` / `_update_state()` for different behaviour.
5. Point `EnemySpawner.enemy_scene` at it, or extend the spawner to mix types.

**Add a new AI ship (friendly or not).** `extends AIPilot` and implement `_decide()`. `EnemyFighter._decide()` is a compact example: it picks a goal per state from `_attack_goal()`, `_roam_goal()` or `_evade_goal()`.

**Add an input action.**
1. Add an entry to `Settings.ACTIONS`; the controls screen picks it up automatically.
2. Add its default slots in `Settings._default_bindings()`.
3. Read it with `Input` / `event.is_action_pressed()` as usual.
4. The controls screen lists it automatically; there are no on-screen hints to update.

Players with an older `settings.cfg` get the new action's defaults.

**Add a HUD element.** Add a `_draw_*` function in `hud.gd`. Use `cam.unproject_position()` for world-space markers (check `cam.is_position_behind()` first), and `_draw_edge_arrow()` for markers off screen.

**Change the ship model.** The art is the imported Arwing (`models/arwing_assault/`, CC-BY 4.0: credit the author) instanced as `Model/Arwing` in `player/ship.tscn` (the wingmen inherit it through `wing/wingman.tscn`): scale 0.0055, rotated -90° around Y so the nose points along -Z. Its `ShipModel` script turns flat-colour materials into toon ones and, with `show_band` on (currently off, for a test of HUD markers alone), paints a band in each ship's colour across the fins (`band_materials` `Material.002` + `Material.004`, `player/arwing_band.gdshader`: a shell `band_radius` 2.3 m around `band_hub` (1.0, 0.3, -0.1), mirrored; `band_width` 0.4 m, white `pinstripe_width` 0.06 m edges). Muzzles sit at the forward roots of the blue fins, (±0.87, 0.44, -0.42). To swap models, keep `Model`, `Model/MuzzleL`, `Model/MuzzleR` and `Model/Shield`, keep -Z as forward, and put `ship_model.gd` on the new instance. Step by step: GUIDE section 10.

**Add a model or material (cel-shaded look).**
- **Lit surfaces:** use a `ShaderMaterial` with `effects/toon.gdshader` and set its `albedo`. The other uniforms tune the bands, glint and rim per material. Textured models: set `albedo_texture` (and `emission`, `emission_texture`, `emission_energy` for glow), or convert an imported model with `ToonMaterial.convert_tree(node)`.
- **Glowing parts** (engines, eyes, windows, bolts): use a `StandardMaterial3D` with emission. Glow reads fine without toon bands.
- **Outlines:** opaque geometry gets ink lines automatically. Anything transparent (including `GeometryInstance3D.transparency` fades) doesn't, because it doesn't write depth. To keep tiny or effect-like meshes from turning into black specks, make them transparent, as `space_dust.gd` does.
- **New cameras:** give them an `InkOutline` child.
- **Tuning:** line colour, width, edge thresholds and the distance fade are uniforms in `effects/ink_outline.gdshader`.

---

## 7. Testing and debugging

There's no automated test suite in the repo. Features have been checked with throwaway headless scenario scripts. That approach is worth reusing:

```sh
# Refresh the class cache after adding new class_name scripts outside the editor
godot --headless --path . --import

# Run a scripted scenario against the real scenes, at a fixed 60 fps
godot --headless --path . --fixed-fps 60 -s path/to/scenario.gd
```

A scenario script `extends SceneTree`:
1. In `_initialize()`, instantiates `res://main.tscn`, adds it to `root` and sets `current_scene`.
2. Drives the game from `_physics_process()`: moves nodes, calls `wing.order_attack(...)`, sends `Input.parse_input_event(...)`, and so on.
3. Prints PASS/FAIL lines, and returns `true` to quit.

Two tips:
- Free `EnemySpawner` first if you want a controlled setup.
- `EnemyFighter._enter_state(...)` forces a state.

**In-game:** while the game runs, the editor's *Remote* scene tree lets you inspect any ship's `state`, `_phase` or `_engage`.

---

## 8. Gotchas

- **"Could not find type X" in the editor or VS Code** after creating a `class_name` script outside the editor means the global class cache is stale. Focus the Godot editor so it rescans, or run `--import`.
- **Editing `project.godot` by hand while the editor is open:** use *Project → Reload Current Project* before saving settings in the editor, or the editor may overwrite your change. The `SceneFader`, `Settings` and `Music` autoloads live in that file.
- **Freed nodes:** targets disappear mid-frame (`queue_free`). Check `is_instance_valid()` before using any stored node reference, and before casting one with `as`.
- **Laser speed inherits ship speed** (`laser_speed + speed`), and `_lead_point()` assumes the same. Keep them consistent if you change how bolts move.
- **Twin lasers** (`Fighter.parallel_fire`, on in `ship.tscn`, so the player and wingmen; off on enemies).
  - **Path:** each bolt flies from its muzzle parallel to the line from the point between the muzzles through the aim point, so the pair stays 0.87 m either side of the crosshair line at every range (under an enemy's 1.1 m hit sphere). No bends. Off = each bolt flies straight to the aim point.
  - **Muzzle flash:** `Fighter.muzzle_flash_size` (0.6 on `ship.tscn`, 0 = none) spawns `MuzzleFlash` (`effects/muzzle_flash.gd`) on the muzzle: 70 ms, bolt's `impact_color`, drawn over the ship's own fins (no depth test).
  - **Streak:** `Laser.trail_length` (16 m on `laser.tscn`, 0 on enemy and turret bolts) stretches the bolt mesh behind its head, growing from the muzzle, so a bolt moving ~25 m per frame reads as one streak.
- **Engine glow follows speed** (`Fighter._update_engine_glow()`, *Engine glow* exports): strength 1.0 at cruise, `engine_glow_per_speed` 0.015 per m/s, clamped to `engine_glow_range` (0.5–2.3); the player's `ship.tscn` uses 0.0075 and 0.7–1.5 (0.7 at minimum speed, 1.5 at full throttle; was 0.5 and 2.05), and `wingman.tscn` restores the defaults; scales `Model/Glow`'s size and emission and `Model/EngineLight`'s energy. Each ship duplicates the shared glow material. Ships without those nodes (enemies) are skipped.
- **Physics interpolation is off.** Ships and the camera update at 60 Hz, so there may be slight judder on high-refresh monitors.
- **Wingmen and enemies only see the player.** Enemies never target wingmen, and nothing damages wingmen. (Destroyer turrets shoot at wingmen only when the player is out of range, purely for show.)
- **The destroyer moves itself** with `sync_to_physics` off. Leave it off, or transforms set outside the physics step get overwritten.
- **AI and big obstacles:** obstacle avoidance knows spheres and boxes, so large non-spherical things need covering with `ObstacleProxy` spheres or `ObstacleBox` boxes (see `Destroyer._build_obstacle_proxies()`; the AI keeps radius × 1.3 + `avoid_margin` 6 from a sphere's centre and `margin` + `avoid_margin` from a box's faces). While attacking, the AI ignores obstacles at or beyond its target, and a box (hull) where its path meets it within `mount_ignore_distance` (60 m) + the target's radius of a structure it attacks, and after scraping a surface it steers off along the normal for `recover_duration` (the sum of every surface hit, mixed with the previous direction while still recovering, so it can't flip between a wall and a ledge in a corner).
- **Toon shadow floor is sun-only.** `toon.gdshader` gives shadowed sides a minimum brightness, but only for directional lights. If a non-directional light got it too, it would light whole lighting clusters, showing up as blocky squares.
- **Outlines vanish against space.** Ink lines are near-black, so silhouettes against the sky blend in. Lines show where objects overlap and on creases. Lines fade out between 220 and 520 m so distant ships stay readable.
- **Asteroid layout is seeded** (`main.gd → field_seed`), so the field is the same every run apart from the intro lane.

---

## 9. Ideas and known gaps

- Fades are only used for Start. Quit to Title and the restart after death cut straight to the next scene.
- Wingmen can't be damaged or lost. There's no shield or health system for them.
- Audio: comms beeps, laser shots, explosions, engine loops and level music (see docs/GUIDE.md, Sound). There is a Music bus but no volume settings yet; no tracks are assigned yet.
- A destroyer's off-screen arrow can sit under the comms box when it points bottom left.
- One level, endless waves. There's no win condition.
