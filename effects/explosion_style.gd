class_name ExplosionStyle
extends Resource
## How an Explosion looks: one of these per kind of blast (presets in
## effects/explosions/). Distances and speeds are in units of the explosion's
## `size` (the fireball's radius in metres, passed to Explosion.spawn()), so one
## style serves small and big blasts alike. Times are in seconds and don't scale.

@export_group("Flash")
## A white-hot burst at the very start, so the moment reads. 0 = none.
@export var flash_size := 1.5
@export var flash_time := 0.12
@export var flash_color := Color(1.0, 0.95, 0.8)

@export_group("Fireball")
## Puffs of fire that swell, drift out, cool into smoke and break up.
@export var puff_count := 10
## Puff diameter, and how fast puffs fly out (slowing down as they go).
@export var puff_size := 1.1
@export var puff_speed := 2.4
@export var puff_lifetime := 1.6
## Fraction of a puff's life after which it's all smoke (it cools from the edge in).
@export_range(0.05, 1.0) var cool_at := 0.55
## Fraction of a puff's life after which it starts breaking up.
@export_range(0.0, 1.0) var dissolve_from := 0.55
@export var hot_color := Color(1.0, 0.96, 0.7)
@export var fire_color := Color(1.0, 0.62, 0.15)
@export var ember_color := Color(0.85, 0.22, 0.06)
## How brightly the fire glows (above 1 it blooms).
@export var glow := 3.0
@export var smoke_color := Color(0.17, 0.16, 0.16)

@export_group("Smoke")
## Bigger, slower smoke puffs left behind after the fire.
@export var smoke_count := 5
@export var smoke_size := 1.5
@export var smoke_speed := 0.6
@export var smoke_lifetime := 2.4
## Seconds before the smoke appears: it would hide the fire if it came at once.
@export var smoke_delay := 0.45

@export_group("Sparks")
## Hot streaks flying out, stretched along their flight.
@export var spark_count := 24
@export var spark_speed := 9.0
@export var spark_length := 0.5
@export var spark_lifetime := 0.6
@export var spark_color := Color(1.0, 0.75, 0.35)

@export_group("Debris")
## Tumbling dark chunks.
@export var debris_count := 6
@export var debris_size := 0.12
@export var debris_speed := 5.0
@export var debris_lifetime := 1.6
@export var debris_color := Color(0.16, 0.15, 0.16)
## Faceted rock lumps instead of hull plates.
@export var debris_rocks := false

@export_group("Shockwave")
## A thin ring racing out in a (tilted) plane. 0 = none.
@export var shockwave_size := 0.0
@export var shockwave_time := 0.55
@export var shockwave_color := Color(1.0, 0.85, 0.6)
## Random tilt of the ring's plane away from level, degrees.
@export var shockwave_tilt := 25.0

@export_group("Light")
## A burst of light on what's around it (range in units of size).
@export var light_energy := 6.0
@export var light_range := 5.0
@export var light_time := 0.45
@export var light_color := Color(1.0, 0.6, 0.25)

@export_group("Motion")
## How much of the exploding object's velocity the explosion keeps...
@export_range(0.0, 1.0) var inherit_velocity := 0.35
## ...and how quickly it loses it (per second).
@export var drag := 1.5


## The longest any part of it lasts.
func duration() -> float:
	return maxf(maxf(flash_time, puff_lifetime), maxf(maxf(smoke_delay + smoke_lifetime, spark_lifetime),
		maxf(maxf(debris_lifetime, light_time), shockwave_time if shockwave_size > 0.0 else 0.0)))
