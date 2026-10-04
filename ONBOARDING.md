# Onboarding guide

> This is the quick reference. For a full explanation of how the code works, with walkthroughs and step-by-step recipes, read [docs/GUIDE.md](docs/GUIDE.md).

***Star Fox: Ascent***, a Star Fox fangame: a 3D arcade space shooter with *Star Wars: Rogue Squadron*-style squad orders. You fly an Arwing through an asteroid field with three AI wingmen (Falco, Slippy and Krystal), fight waves of enemy fighters, and give your wingmen orders.

This guide assumes you know Godot 4 basics: scenes, nodes, signals and GDScript. It covers what's specific to this project. Read sections 1–4 before touching code; use the rest as reference.

---

## 1. Get it running (5 minutes)

1. Install **Godot 4.7** (standard build, not .NET). The project uses Jolt Physics and Forward+, both built in.
2. Open the folder in the Godot project manager and press **F5**.
3. Almost every asset (meshes, sky, effects) is generated in code or built from primitives. The exceptions are the sound effects in `audio/sfx/`, the player/wingman ship model in `models/arwing_assault/`, the Great Fox in `models/great_fox/`, the destroyer and enemy fighter in `models/destroyer/` and `models/enemy_fighter/` (built by Blender scripts there) and the UI font in `ui/fonts/`; all are in the repo, and Godot imports them the first time the project opens.

**Controls**

| Action | Keyboard / mouse | Gamepad |
|---|---|---|
| Steer | Mouse (moves a virtual stick), arrow keys | Left stick |
| Throttle | W / S | Right stick up/down |
| Roll | Q / E or A / D | LB / RB |
| Boost | Shift | A |
| Fire | Left mouse button / Space | Right trigger |
| Wingmen: attack target | F | Y |
| Wingmen: cover me (toggle) | C | X |
| Wingmen: regroup / cancel orders | R | B |
| Pause | Esc | Start |
| Skip intro | Fire / Enter | A |

---

## 2. Project map

```
main.tscn / main.gd        Asteroid Field mission: inherits levels/level_base.tscn, main.gd (extends Level) scatters the asteroids
levels/
  level.gd                 Level: shared mission logic (build world, intro + line, spawner start, death/restart, mouse)
  level_base.tscn          Every shared node (ship, camera, wingmen, spawner, HUD, comms, pause, intro); missions inherit it
  corneria_test.tscn       Corneria test: terrain, lakes, clouds, day sky, enemy waves (no destroyer), play boundary
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
  destroyer.gd / .tscn     Destroyer: capital ship (movement, fade, launches, kill rule)
  destroyer_part.gd        DestroyerPart: a destructible subsystem (bridge / thruster / turret / hangar)
  destroyer_turret.*       DestroyerTurret: hull turret (extends DestroyerPart)
  destroyer_hangar.gd      DestroyerHangar: hangar door that launches squadrons (extends DestroyerPart)
  obstacle_proxy.gd        ObstacleProxy: invisible sphere the AI steers around (covers the destroyer hull)
weapons/
  laser.gd                 Laser: bolt movement + hit detection (shared by both sides)
  laser.tscn               Player-side bolt (green, 500 m/s on ship.tscn, 8 m streak)
  enemy_laser.tscn         Enemy fighter bolt (red)
  turret_laser.tscn        Destroyer turret bolt (bigger, slower, 8 damage)
world/
  asteroid.gd              Asteroid: procedural, destructible rocks
  intro_cutscene.gd        IntroCutscene: level intro fly-by
  space_dust.gd            Speed streaks around the camera
  space_sky.gdshader       Procedural starfield sky
  space_environment.tres   Shared Environment (sky, glow, tonemap) used by title + Asteroid Field
  terrain.gd               Terrain: procedural low-poly ground, lakes, far ground, collision; height_at() / surface_height()
  clouds.gd                Clouds: flyable cartoon cloud clusters that fade near the camera
  planet_environment.tres  Day sky + horizon fog for planet missions
  play_boundary.gd         PlayBoundary: edge of a mission area; HUD warning, then the ship turns itself back
  great_fox.gd / .tscn     GreatFox: the team mothership as scenery outside a mission area (no collision; slow bob)
effects/
  impact.gd                Impact.spawn(...): flash for hits and explosions
  muzzle_flash.gd          MuzzleFlash.spawn(...): brief flash on a gun muzzle when a fighter fires
  shield_effect.gd         ShieldEffect: the blue shield bubble on the player ship (+ shield.gdshader)
  toon.gdshader            Cel shading used by every lit surface (light model in toon_light.gdshaderinc); optional colour texture + glow map
  toon_material.gd         ToonMaterial.convert_tree(): cel-shaded copies of an imported model's PBR materials (keeps texture + glow; used by GreatFox)
  toon_vertex.gdshader     Same, coloured by vertex colours (the terrain)
  water.gdshader           Lake surface: flat toon blue with drifting shimmer
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
  pilot.gd                 Pilot: a CommsSpeaker that flies; adds accent colour + battle lines (acks, celebrations, praise for your kills, destroyer callout)
  speakers/*.tres          One file per character: Fox (CommsSpeaker), Falco, Slippy, Krystal (Pilot)
models/
  arwing_assault/          Imported Arwing (glTF, CC-BY 4.0, credit in license.txt): the player and wingman model
  great_fox/               Imported Great Fox III (glTF, textures cut to 1024 px; no licence came with it, see README.txt)
  destroyer/               The destroyer (our own model): hull, bridge, thruster and hangar-door .glb files
    source/                build_destroyer.py (builds and exports them in Blender) + collision.txt (hull collision pieces)
  enemy_fighter/           The Venomian "Mantis" enemy fighter (our own model), one .glb for every fighter type
    source/                build_enemy_fighter.py (builds and exports it in Blender)
```

Every script with a `class_name` (`Fighter`, `Ship`, `Wingman`, `EnemyFighter`, `WingCommand`, `Laser`, and so on) can be used as a type anywhere.

---

## 3. The mental model

### Scene flow

```
title_screen.tscn --Start--> MissionSelect --pick--> SceneFader.change_scene(mission.scene_path) --> main.tscn / levels/corneria_test.tscn
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
3. Change speed towards `_get_target_speed()`, with boost from `_wants_boost()`.
4. `move_and_slide()`, then collision response.
5. `_aim(delta)`: set `aim_point`, where the guns aim (twin lasers fly parallel to the line through it).
6. Fire if `_wants_fire()` and the cooldown allows.

**The pilot interface:**

| Override | Meaning |
|---|---|
| `_get_stick() -> Vector2` | x = yaw right, y = pitch down (screen-style), -1..1 |
| `_get_roll() -> float` | Positive rolls left. 0 means auto-level. |
| `_get_target_speed()` | Clamped to `[min_speed, boost_speed]` |
| `_wants_boost()`, `_wants_fire()` | |
| `_get_level_up()` | "Up" to auto-level towards (wingmen use the leader's up) |
| `_get_pitch_rate()` | Pitch rate at full stick (default `pitch_rate`; wingmen raise it to somersault) |
| `_get_acceleration(fast)` | Speed change rate (default `acceleration`, or `boost_acceleration` when `fast`) |

For AI ships, `AIPilot._think()` calls **`_decide(delta) -> Vector3`**, which returns the world point to fly towards. It then handles steering and obstacle avoidance itself. A subclass's `_decide()` also sets `_target_speed`, `_engage` (what to shoot, if anything) and `_level_up`.

Useful `AIPilot` helpers:
- `_attack_goal(target, side)`: chases fighters from behind, and makes strafing runs (approach, then break off) on anything that doesn't move.
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
| `obstacles` | Asteroids, enemies, destroyer `ObstacleProxy` spheres | AI obstacle avoidance |
| `hud` | HUD overlay | `call_group("hud", "add_score", n)` |
| `comms` | `Comms` | `Comms.find(get_tree())` from anything that talks |
| `wing_command` | `WingCommand` | HUD; `EnemySpawner` calls `announce_destroyer` on it |
| `wing_command`, `enemy_spawner`, `destroyer` | singletons in the level | HUD |
| `terrain` | `Terrain` (planet missions only; joined in `_enter_tree`) | `ChaseCamera` ground clearance, AI ground avoidance, wingman slots, `EnemySpawner` |
| `boundary` | `PlayBoundary` (missions with an edge; joined in `_enter_tree`) | `Ship` turn back, HUD warning, enemy patrols, `EnemySpawner` |

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
  - **Formation flight only engages** while the wingman faces within about 37–73° of your heading (`ASSIST_MIN_ALIGNMENT` / `ASSIST_FULL_ALIGNMENT`).
  - **How it works:** the wingman turns and rolls with the leader, anticipating the leader's current turn rate (`_update_rotation` override). It also moves with the slot's real velocity plus a spring onto it. This uses `Fighter._velocity_offset()`, the one way a ship can move other than straight ahead, capped at `max_slot_correction`.
  - **Why:** the leader can bank-and-yank or roll hard without sweeping through a wingman, and formation fire stays on target.
  - **Banking:** formation flight turns the ship without the stick, so wingmen bank the model from their measured turn rate (`_turn_rates`, via the `Fighter._visual_turn_rates()` hook), rescaled to the leader's `pitch_rate` / `yaw_rate` in formation: same turn, same bank angle as the player.
  - **When it lets go:**
    - immediately on any order;
    - quickly while dodging an obstacle or after scraping something;
    - whenever the leader is dead.
  - **Sideways slide:** `velocity_heading_blend` points the nose partly along the direction of travel, hiding most of the slide.
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
  - **Weapons Free (V / Back):** a standing order (`_free_goal()`, `#region Weapons free`). See *Weapons Free* below.
- **Weapons Free:** with no target, the wingman roams around the leader. It picks points within `free_roam_radius` (208 m, mostly ahead), in the leader's local space so they move with it.
  - **Staying close:** outside `free_leash` (325 m) it heads back. Roam routes steer around the leader, which isn't an AI obstacle (`_steer_clear_of_leader()`).
  - **Picking targets:** it engages enemy fighters within `free_detect_range` of itself and `free_engage_radius` of the leader. Fighters no other wingman is on come first (`_pick_free_target()`); it only doubles up when every nearby enemy is taken.
  - **Cooldown:** after shooting down an enemy fighter itself, the wingman waits `free_kill_cooldown` (2–3.5 s) before picking a new target, roaming meanwhile (`_free_cooldown`, set in `notify_kill()`). Losing a target any other way (someone else's kill, the enemy leaving) starts no cooldown.
  - **Never disengages:** once engaged, it stays on the target until it dies, however far the chase goes, then returns to roaming.

### AI Pilots and Accuracy
- `ai_pilot.gd` (base class for enemies and wingmen) uses `aim_scatter` (export) to add random noise to the true aim point. Wingmen default to 4.0, Elite fighters to 2.0.
- `lead_turns = true` allows an AI to steer its nose ahead of moving targets. Elite fighters and wingmen have this on; light fighters have it off.
  - **Off on this order:** formation flight and formation fire.
- **Signals:** `selection_changed`, `order_feedback(message)` (emitted for orders that went out; nothing shows it) and `Wingman.order_changed`.
- **Comms lines** (`acknowledgements`, `destroyer_callout`, `celebrations`, `praise`, `celebration_chance` in each character's `Pilot` file, `comms/speakers/*.tres`; spoken via `WingCommand` and `Wingman.notify_kill`):
  - **Acknowledgements:** after each order, one recipient picked at random says one of its own lines (never the same as its previous one): Falco "You got it!" / "On it!", Slippy "Right away!" / "Understood!", Krystal "Yessir!" / "Yes, captain!". Low priority, so it's dropped if someone's already talking. An order that reaches nobody gets no line.
  - **Destroyer callout:** when a destroyer spawns, a random wingman calls it out with a hint (bridge and thrusters). One line per wingman. High priority.
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

**Model (the Venomian "Mantis"):** one `.glb` (`models/enemy_fighter/`, built by `source/build_enemy_fighter.py`) for both types, about 6.2 × 5.7 m. `FighterModel` on `Model/Mantis` paints `Fighter_Accent` and `Fighter_Lights` (eye, pincer tips, wing leading edges, tip-plate fronts): elite purple + red lights (energy 10), light fighter tan + orange (energy 8, overridden in `light_fighter.tscn`). Engine glow: `Model/Glow`, one oval over the twin nozzles. Muzzles at the gun tips (±0.95, −0.42, −2.15). Hurtbox 6.6 × 3.8 × 5.2 m, centred 0.5 m forward (about the old 5.5 m cube's hit rate, slightly higher); collision box 6.2 × 2 × 5.6, same centre; `radius` 3.5.

**Waves (`EnemySpawner`):** `enemy_scene` sets the level's fighter type for both waves and destroyer hangars. The base level (`levels/level_base.tscn`, so every mission) uses `light_fighter.tscn`; the script default is the elite `enemy_fighter.tscn`. 3 fighters, then one more per wave up to 8. Each wave spawns 600 m out, roughly ahead of the player and facing random directions. Every 5th wave also brings a destroyer (`destroyer_every`, 0 = never). The next wave comes 6 s after every enemy is gone, destroyer included. At most `max_fighters` (12) enemy fighters can be alive at once, counting hangar launches. Anything that should hold up the next wave must be registered with `spawner.track(node)`. Waves don't start until `start()` is called.

### Destroyer (`Destroyer`)
- **Arrival:** appears at `zone_radius` (1000 m) from the centre, fades in over 4 s (`GeometryInstance3D.transparency` on every mesh), then crawls inward at 8 m/s and stops `stop_distance` (300 m, set in `destroyer.tscn`) from the centre. It smashes asteroids in its path with `Asteroid.shatter()`, which awards no score. Fewer working thrusters make it slower.
- **Model:** our own, about 368 × 175 m (1.5× the old one): forked prow with an open gap, bridge tower, three thrusters, side hangars; gunmetal, crimson, amber, red-orange engines. Built in Blender by `models/destroyer/source/build_destroyer.py` (game coordinates; colours are the sRGB values the game shows), exported as four `.glb` files and cel-shaded at load (`ToonMaterial`).
- **Hull and parts:** the hull is the `AnimatableBody3D` root, on the World layer. All damage goes through `DestroyerPart` children on the Enemy layer, and the parts ignore hits until `is_vulnerable()` (fully faded in and not dying).
- **Kill rule:** destroying the bridge **and** all three thrusters starts a chain of explosions, then a fade-out, then `destroyed`.
- **Turrets (`DestroyerTurret`):** a destroyed turret is disabled, charred and stays on the hull.
  - **Targeting:** the player if within `aggro_range` (450 m); otherwise the nearest wingman in range.
  - **Firing limits:** pitch is limited to −5°…80°, so there are blind spots. Each turret needs a clear line of fire past the hull and asteroids.
- **Hangars (`DestroyerHangar`):** every `launch_interval` (40 s, first launch 15 s after fading in), the next intact hangar opens its door and launches 3 fighters, within the fighter cap.
  - **Launched fighters:** they fly straight out for 2 s via `EnemyFighter.begin_launch()`, with collisions off so they can leave through the hull, then patrol in front of the bay.
  - **Destroying a door** blows it off and stops launches from that side.
- **Health and score:**

  | Part | Health | Score | `radius` |
  |---|---|---|---|
  | Bridge | 70 | 3 | 27 |
  | Each thruster | 46 | 2 | 15 |
  | Each hangar door | 29 | 2 | 15 |
  | Each turret | 12 | 1 | 6 |
  | Killing the destroyer | | +10 | |

- **AI steering:** `_build_obstacle_proxies()` fills `hull_outline` (top-down (x, z) outline, set in `destroyer.tscn`) with 16 m `ObstacleProxy` spheres every 20 × 25 m, plus `extra_proxies` (tower, superstructure, hangar housings) and one per thruster: 89 in all. The gap between the prongs is open for the player; the AI avoids it. If you change the model, re-export, paste the new `collision.txt` pieces and update `hull_outline`, `extra_proxies` and part positions.
- **Wingmen vs. parts** (Attack order, 4 runs): turret 3.6–4.1 s, bridge 5.9–6.4 s, centre thruster 18–33 s (it still makes them scrape the hull in most runs). The old ship: 4.1–5.2 s, 13.6–38.8 s, 38 s to never.

### Intro (`IntroCutscene`)
1. Places the formation at the `IntroStart` marker on autopilot. The HUD is hidden and the camera's physics is turned off.
2. The camera sits still at `IntroCameraSpot` and turns to follow the fighters.
3. Once the player is `handover_distance` past it, the camera flies to `ChaseCamera.chase_transform()`.
4. Snaps the camera into place, enables controls, fades the HUD in and emits `finished`.

`main.gd` keeps asteroids out of the fly-in lane (`_blocks_intro`), because ships on autopilot don't dodge. **Move the markers (`IntroStart`, `IntroCameraSpot`, in `levels/level_base.tscn`, overridden per mission) to reframe the shot.** The lane follows them automatically.

### Comms (`Comms`)
The dialogue box, bottom left: a portrait square (faint static until portraits exist) with the speaker's name under it, and the line typing out in a box to its right.
- **Opening (0.3 s):** the square expands from a 2 px line (`expand_time` 0.09 s), shows static (`noise_time` 0.09 s), then the portrait and name appear as the text box unfolds to the right (`unfold_time` 0.12 s). Typing (and a recorded voice) starts after that. **Closing** is the same in reverse. All driven by `_open_t` / `_apply_open()`.
- **Talking:** `Comms.find(get_tree()).say(speaker, text, priority, voice)`. `speaker` is a `CommsSpeaker` resource from `comms/speakers/`; each `Fighter` has a `speaker` export (Fox on `ship.tscn`, each wingman overridden in `levels/level_base.tscn`).
- **Priorities:**
  - **LOW** never interrupts. One arriving while a line is on screen is dropped (`say()` returns false).
  - **HIGH** interrupts LOW at once: same speaker, it just types; different speaker, a `noise_time` burst of static over the portrait first (`SWITCHING`). A HIGH arriving during another HIGH queues behind it.
  - A queued line (or a LOW one arriving while the box closes, with nothing queued) turns the closing box around at the static instead of letting it collapse.
- **Typing:** `chars_per_second` (40), with short pauses after punctuation. The label wraps the whole line up front (`VC_CHARS_AFTER_SHAPING`), so words don't jump lines mid-type. A line stays up `hold_time` plus `hold_per_char` per character, then the box closes.
- **Audio:**
  - **Voice:** a line with a `voice` stream plays it instead of beeping, and stays up until the recording's length has passed. This is timed rather than read from the player, so a dead audio device can't stick a line on screen.
  - **Beeps:** otherwise every `beep_every`-th letter (2) beeps at the speaker's `beep_pitch`. The beep is generated in code (`_make_beep()`).
- **Portraits:** set `portrait` on a speaker resource. The square crops to fill. Without one it shows faint static (`empty_portrait_static` 0.3).
- **Layering:** it's its own `CanvasLayer` (layer 5, above the HUD, below the pause menu), so it shows during cutscenes while the HUD is hidden. It pauses with the game.

### UI
- **HUD:** drawn in code in `ui/hud.gd` (`_draw()`, redrawn every frame). There are no Control nodes per element. To add an element, write a `_draw_*` helper and call it from `_draw()`.
- **Gauges** (`_draw_gauges()`, top right): two bars with no labels or numbers. Shields are green on top; while they're down, the bar turns red and fills as they reboot. Boost is blue underneath. Score is still counted in `hud.score` but not shown.
- **Enemy brackets** (`_draw_enemies()`): only within `enemy_marker_radius` 320 px (set in `hud.tscn`) of the crosshair (popping in and out, no fade), and never while something on the World layer (terrain, asteroid, destroyer) hides the enemy from the camera (`hide_hidden_enemies`, one ray per enemy per physics tick). Clouds don't block (no collision). HUD exports, *Enemy markers* group.
- **Radar** (`_draw_radar()`, top left): shows enemy fighters and wingmen within `radar_range` (500 m). Its on-screen size is `radar_radius` (80 px in the base layout); both are exports on the HUD node in `levels/level_base.tscn`. Enemies further away sit on the rim as small dim dots in their direction. It's the only way to find off-screen enemies: they get no edge arrows (the destroyer and Attack targets still do).
  - **Orientation:** positions are in the ship's local space, so ahead is up and the radar turns and rolls with you.
  - **Enemy symbols:** ▲ above you, ▼ below, ■ level (`_radar_height()`: within `RADAR_LEVEL_DEG` or `RADAR_LEVEL_METRES`).
  - **Wingmen:** dots in their colours, with a height tick. They're kept at least `RADAR_WINGMAN_MIN` px from the centre so the formation stays readable.
- **Hit direction** (`_draw_hit_direction()`): a red arc around the screen centre on the side an enemy shot came from, fading over `Ship.shot_flash_time` (0.8 s). Set by `Ship.notify_shot(origin)`, which lasers call before `take_hit()`.
- **Wing panel** (`_draw_wing_panel()`, bottom right): laid out like the D-pad, with Falco left, Slippy top, Krystal right and ALL below.
  - **Each card** (104 × 38): call sign, with an icon for the current order on the right in the order's colour (`_draw_order_icon()`): Form Up three dots in a V (green), Attack a crosshair (orange), Cover Me a shield (blue), Weapons Free a burst (red). There's deliberately no live status (attacking, roaming...): the player can see that. Selected cards light up in the wingman's colour, and on keyboard the select key shows in the corner.
  - **The middle:** who the next order would go to.
- **Wingman markers:**
  - **Triangles:** a solid downward triangle over each wingman in its own colour, with its initial in bold white (`WINGMAN_MARKER_SIZE` 36 × 29 px, letter size `WINGMAN_INITIAL_SIZE` 15, 21 when selected; cached as textures, see `_wingman_marker()`; bold through a `FontVariation` with `variation_embolden`); 1.4× bigger and bracketed when selected.
  - **Targets:** only targets of an **Attack** order get an orange diamond listing who's on it (initials and distance). Targets picked by Cover Me or Weapons Free aren't marked.
- **Pause menu:** runs with `process_mode = ALWAYS`. It sets `get_tree().paused` and also pauses automatically when the window loses focus.
- **`SceneFader` autoload:** `SceneFader.change_scene(path)` fades out, swaps scenes and fades in. It's currently only used by the title screen when a mission is picked.
- **`Music` autoload:** `Music.play(level_music)` (same track = keeps playing; different = 1 s fade-out of the old one; `null` / `stop()` = fade to silence). `Level.music` and the title screen's `music` call it in `_ready()`. Plays on the **Music** bus (`default_bus_layout.tres`). −8 dB while paused. Lead → loop is gapless (`AudioStreamInteractive`).
- **Mission selector** (`ui/mission_select.gd`, node `MissionSelect` in `title_screen.tscn`): Start opens it. One button per `Mission` in its `missions` array, the highlighted one's description underneath, Back (Esc / B) returns to the title menu.

### Missions and levels
- **Missions:** `Mission` resources in `missions/` (`title`, `description`, `scene_path`). Asteroid Field → `res://main.tscn`; Corneria (test) → `res://levels/corneria_test.tscn`.
- **Shared base:** every mission scene inherits `levels/level_base.tscn` (root script `Level`). It keeps flat node names (`Ship`, `Falco`...). Changes to the base reach every mission unless overridden.
- **Asteroid Field (`main.tscn`):** `PlayBoundary` radius 1000 m (turn back at 1200 m; just past the 900 m field and the 1000 m destroyer arrival). `GreatFox` at (0, 30, 1800), yaw -25°, straight behind `IntroStart`; a boosting player is turned back about 200 m short of it. Waves and patrols stay inside the boundary.
- **`Level` exports:** `restart_delay` (3 s), `spawn_enemies` (off = no waves), `music` (a `LevelMusic`; empty = silence), `intro_line`, `intro_line_delay`. Override `_build_world()` to generate a world (`main.gd` scatters asteroids there).

### Planet terrain (Corneria test)
- **`Terrain`** (`world/terrain.gd`): 4 × 4 km, seed 1984, 25 m cells → 160 × 160 cells in 8 × 8 chunks, 51,200 flat-shaded triangles, built in about 0.4 s.
  - **Height:** `base_height` 8 + hills ±70 (900 m wide) + ridged mountains up to 320 (none within 450 m of the centre) + boundary ring up to 520 (from 72% to 90% of the half-width), sinking below sea level at the very edge.
  - **Colour per face:** sand (< 6 m above water), rock (normal.y < 0.78), snow (> 260 m), light/dark grass patches; ±5% brightness jitter. Vertex colours, converted to linear, drawn with `toon_vertex.gdshader`.
  - **Collision:** a `ConcavePolygonShape3D` per chunk from the same triangles (World layer); water and the 30 km far-ground plane have thin solid slabs. Crashes are the normal 30 damage + bounce.
  - **API:** `height_at(x, z)` (exact, `-INF` off the map), `surface_height(x, z)` (ground or water, whichever is higher).
- **Lakes:** one opaque plane at `sea_level` 0; about 12% of the playable area. `water.gdshader`.
- **`Clouds`** (`world/clouds.gd`): 60 clusters of 5–9 blobs at 220 / 430 m (±30), none within 350 m of the centre; fade up to 85% when the camera is inside or within 40 m.
- **Environment:** `planet_environment.tres` (procedural day sky, sky ground colour = horizon, fog density 0.00035 in the horizon colour, `fog_sky_affect` 0). Sun pitched higher, shadows to 600 m.
- **Camera:** `ChaseCamera.ground_clearance` 3 m above `surface_height()`.
- **Start:** ships and intro markers 250 m up (ground at the centre is about 8 m).
- **Enemies on Corneria:** the base level's waves, no destroyers (`destroyer_every = 0` on its `EnemySpawner`).
- **AI ground avoidance** (`AIPilot`, *Ground* group; only with a `Terrain`): goals raised to `ground_clearance` 25 m (not an engaged target's lead point); flight path checked at 7 points over `ground_lookahead_time` 2 s, steep climb if any is below the clearance (`_ground_danger`). Measured: 1 enemy and 0 wingman ground scrapes in six 3-minute runs (before: enemies spawned and stayed underground).
- **Wingmen near the ground:** `slot_position()` raises the slot to `formation_ground_clearance` 6 m over the ground under it and `formation_ground_lookahead` 1 s ahead. Near the slot, wingmen use 6 m / 1 s for their own check, and it doesn't drop formation flight. With the leader 15 m up: 99% in formation, about 0.1 scrapes a minute.
- **Enemy patrols:** roam points at least `patrol_min_altitude` 60 m up and `patrol_boundary_margin` 150 m inside the boundary.
- **Spawner (planet):** wave centre at least `spawn_altitude` 80 m up (each fighter at least 40 m over its own ground) and `spawn_boundary_margin` 250 m inside the boundary.
- **`PlayBoundary`** (`world/play_boundary.gd`): `radius` 1450 m (horizontal), `turn_back_margin` 200 m (negative = warning only). HUD: "RETURN TO THE COMBAT AREA" past the radius, "TURNING BACK" during the automatic turn.
- **Turn back (`Ship`, *Boundary* group):** past radius + margin the ship steers itself home (`turning_back`; roll ignored), pulling up hard if the ground is within `turn_back_clearance` 60 m; control returns within `turn_back_done_deg` 25° of the way home. About 3 s. A level, low run straight at a steep ridge can still clip it.
- **`GreatFox`** (`world/great_fox.tscn`): on Corneria, scenery at (-300, 800, 2100), yaw 70°, about 2.1 km out, behind the intro approach. No collision or groups; `bob_height` 3 m, `bob_period` 14 s. Boosting straight at it, the turn-back stops you about 250 m short. Keep it beyond the boundary + turn-back margin. Also on the Asteroid Field (see Missions and levels).

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

**Change the ship model.** The art is the imported Arwing (`models/arwing_assault/`, CC-BY 4.0: credit the author) instanced as `Model/Arwing` in `player/ship.tscn` (the wingmen inherit it through `wing/wingman.tscn`): scale 0.0055, rotated -90° around Y so the nose points along -Z. Its `ShipModel` script turns flat-colour materials into toon ones and paints `accent_material` (`Material.004`, the fin panels) in each ship's colour. Muzzles sit at the forward roots of the blue fins, (±0.87, 0.44, -0.42). To swap models, keep `Model`, `Model/MuzzleL`, `Model/MuzzleR` and `Model/Shield`, keep -Z as forward, and put `ship_model.gd` on the new instance. Step by step: GUIDE section 10.

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
  - **Streak:** `Laser.trail_length` (8 m on `laser.tscn`, 0 on enemy and turret bolts) stretches the bolt mesh behind its head, growing from the muzzle, so a bolt moving ~10 m per frame reads as one streak.
- **Engine glow follows speed** (`Fighter._update_engine_glow()`, *Engine glow* exports): strength 1.0 at cruise, `engine_glow_per_speed` 0.015 per m/s, clamped to `engine_glow_range` (0.5–2.3); scales `Model/Glow`'s size and emission and `Model/EngineLight`'s energy. Each ship duplicates the shared glow material. Ships without those nodes (enemies) are skipped.
- **Physics interpolation is off.** Ships and the camera update at 60 Hz, so there may be slight judder on high-refresh monitors.
- **Wingmen and enemies only see the player.** Enemies never target wingmen, and nothing damages wingmen. (Destroyer turrets shoot at wingmen only when the player is out of range, purely for show.)
- **The destroyer moves itself** with `sync_to_physics` off. Leave it off, or transforms set outside the physics step get overwritten.
- **AI and big obstacles:** obstacle avoidance treats everything as a sphere, so large non-spherical things need covering with `ObstacleProxy` spheres (see `Destroyer._build_obstacle_proxies()`). While attacking, the AI ignores obstacles at or beyond its target, and after scraping a surface it steers off along the normal for `recover_duration`.
- **Toon shadow floor is sun-only.** `toon.gdshader` gives shadowed sides a minimum brightness, but only for directional lights. If a non-directional light got it too, it would light whole lighting clusters, showing up as blocky squares.
- **Outlines vanish against space.** Ink lines are near-black, so silhouettes against the sky blend in. Lines show where objects overlap and on creases. Lines fade out between 220 and 520 m so distant ships stay readable.
- **Asteroid layout is seeded** (`main.gd → field_seed`), so the field is the same every run apart from the intro lane.

---

## 9. Ideas and known gaps

- Fades are only used for Start. Quit to Title and the restart after death cut straight to the next scene.
- Wingmen can't be damaged or lost. There's no shield or health system for them.
- Audio: comms beeps, laser shots, explosions, engine loops and level music (see docs/GUIDE.md, Sound). There is a Music bus but no volume settings yet; no tracks are assigned yet.
- No character portraits yet; the comms portrait square is empty.
- A destroyer's off-screen arrow can sit under the comms box when it points bottom left.
- One level, endless waves. There's no win condition.
