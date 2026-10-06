# Gemini Changes

## Agent System Updates
- Installed and activated the `i-have-adhd` agent skill plugin to strictly format responses.

## Wingman AI & Commands
- Decoupled the hardcoded wingman roster to support variable squad sizes (1 to 3 wingmen). Bound selection inputs to generic `select_wingman_1/2/3`.
- Renamed the "Dancer" callsign to "Saber" globally, including updating node names, resource files, comms arrays, HUD comments, and documentation.
- Idempotent Orders: Wingmen now ignore commands they are already executing (no feedback, no acknowledgment), with the exception of assigning an Attack order to a *new* target.
- "Weapons Free" Nerf: Implemented a 2.0 to 3.5 second cooldown (`_free_cooldown`) after a wingman scores a kill in Weapons Free mode, causing them to break off and roam near the player before acquiring a new target.
- Kill Celebrations: Wingmen now have a 25% chance to play a random celebration voice line after securing a kill (via a new `shooter_node` tracking in lasers). Disabled celebrations when the wingman is in `FORM_UP` formation.

## Combat Mechanics
- Physical Crash Damage: The player ship now takes 30 shield damage upon colliding with terrain or enemies. The collision applies a violent deflection (`global_basis` reflection) and triggers intense camera shake on the `ChaseCamera`.
- Tunable Aim Inaccuracy: Added an `aim_scatter` export variable to `AIPilot` which adds random spatial noise to their laser convergence points. Set to 4.0 for Wingmen and 2.0 for Elite fighters.
- Elite Fighter Lead Aiming: Enabled `lead_turns = true` in the unused `enemy_fighter.tscn` (elite fighter), allowing it to track moving targets with its nose for much higher accuracy.

## UI / UX
- Crosshair Overhaul: Removed the small, secondary depth bracket (`near_point`) crosshair to declutter the screen. 
- Crosshair Smoothing: Added a fast `lerp()` (25.0 speed) to the main crosshair's 2D screen projection in `ui/hud.gd`, preventing it from visually jumping or snapping when sweeping across objects at different depths.

## Controls & Input
- Default Gamepad Layout: Updated `settings/settings.gd`'s `_default_bindings()` to match user-configured controls (throttle on triggers L2/R2, roll on Right Stick X, fire on Right Bumper R1).

## Visual Effects & Wrecks
- Wreck Flight Alignment: In `effects/wreck.gd`, added `_align_with_velocity()` so a dying enemy fighter's nose (-Z basis) continuously aligns with its curved velocity vector under gravity (e.g. on Corneria) while maintaining its axial roll rotation.

## Documentation
- Updated `ONBOARDING.md` to document player crash damage in the collision layers table, note the flexible wingman squad size, document the new command reissue logic, outline the new kill celebrations, explain the Weapons Free cooldown and aim scatter, and record wreck flight alignment.
- Updated `docs/GUIDE.md` to remove the Kill Chatter tutorial suggestion (since it's now built-in) and replaced it with a custom weapon task. Removed hardcoded references to exactly three wingmen. Documented smoothed single crosshair and wreck flight alignment under gravity.


