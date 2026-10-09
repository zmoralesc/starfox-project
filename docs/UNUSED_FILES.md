# Unused files

Files kept in the repository that the game doesn't use, and why each is still here. Checked in October 2026 by searching every scene, resource, script, shader and import file for each file's `res://` path and `uid`, then checking the hits by hand. Nothing here is loaded by a mission. Delete an entry's files together, and update this list when you retire or revive something.

## Retired models and scenes

**The first space station** (replaced by "the Drum", October 2026; GUIDE §8.11b)
- `models/space_station/space_station.glb` (+ `.import`): the first, half-size wheel station.
- `models/space_station/source/build_space_station.py`: its Blender build script.
- `models/space_station/source/proxies.txt`: its 158 AI avoidance spheres.
- To compare the two, `git show` an older `world/space_station.tscn` (before the Drum), which points at these files.

**The previous destroyer** (replaced by the Juggernaut; GUIDE §8.10)
- `enemies/destroyer.tscn`, `enemies/destroyer_turret.tscn`
- `models/destroyer/destroyer_bridge.glb`, `destroyer_hangar_door.glb`, `destroyer_hull.glb`, `destroyer_thruster.glb` (+ `.import`)
- `models/destroyer/source/build_destroyer.py`, `collision.txt`, `proxies.txt`

`EnemySpawner.destroyer_scene` still defaults to `destroyer.tscn` (`preload` in `enemies/enemy_spawner.gd`). `levels/level_base.tscn` overrides it with `juggernaut.tscn`, so it loads but never spawns. Before deleting these files, change that default to the Juggernaut. Its scripts (`destroyer.gd`, `destroyer_part.gd`, `destroyer_hangar.gd`, `destroyer_turret.gd`) are shared with the Juggernaut and are **in use**.

## Unused game resources

- `world/planet_environment.tres`: the first planet-mission sky and fog. Corneria uses `planet_environment_wide.tres` and the Space Station mission `asteroid_field_environment.tres`. GUIDE and ONBOARDING still describe it.
- `models/destroyer/juggernaut_collision.glb` (+ `.import`): the Juggernaut's `Col_` meshes. The game builds its hull collision from the model instead (`hull_collision_from_model`).
- `models/destroyer/juggernaut_markers.glb` (+ `.import`): the Juggernaut's part pivots, launch points and turret mounts. Never loaded: their positions are copied into `enemies/juggernaut.tscn` by hand, so keep it as the source for those numbers.

## Design history (source folders, ignored by Godot)

- `models/destroyer/source/juggernaut_c1.py`, `juggernaut_c1_approved.py`, `juggernaut_c1_stern_attempt.py`: earlier passes of the Juggernaut. `juggernaut_c2.py` is the current one and imports none of them.
- `models/destroyer/source/concepts/`: the destroyer concept round (`destroyer_concepts.blend`, `PROPOSALS.md`, screenshots A–H). See `models/SPACE_ASSETS.md`.
- `models/destroyer/source/juggernaut_preview/`: only `C3_*` and `juggernaut_plating.png` come from the current script. `C1_*`, `C2_*`, `fix_*`, `live_*`, `ingame_*` and the other files are renders from earlier passes and reviews.
- `models/asteroid/source/`: empty except for its `.gdignore`.
- `GEMINI_CHANGES.md` (repository root): a change log from an earlier Gemini session. It is out of date (for example, it renames a wingman "Saber" who is no longer in the game), and nothing links to it.

## Not unused, though a search makes them look it

- `*_Juggernaut_Plating.png` and `space_station_v2_tex_*.png`: Godot's import extracts these textures from inside the `.glb` files and the imported scenes use them. Commit them with their `.glb`.
- `models/destroyer/juggernaut_turret.glb`: its meshes are saved out to `juggernaut_turret_*.res` (through `_subresources` in its `.import`), and `juggernaut_turret.tscn` uses those.
- `models/arwing_assault/scene.bin` and `textures/`, `models/great_fox/Great_Fox_III.bin` and `images/`: referenced from inside the `.gltf` files.
- `default_bus_layout.tres`: Godot loads it by its default name.
- `class_name` scripts (`AIPilot`, `SoundFX`, `ToonMaterial`, ...): used by class name, not by path.
