class_name TerrainMap
extends Resource
## A hand-made landscape for Terrain, used instead of its noise one. Written by
## a Blender build script (models/corneria/source/build_corneria.py exports
## models/corneria/corneria_map.tres): ground heights on a square grid, plus
## what each grid cell is and how tall the structures on it are.

## Map cell is coloured by Terrain's height and slope rules.
const PAINT_AUTO := 0
## Map cell is paved (towns, the base apron): Terrain.paved_color.
const PAINT_PAVED := 1
## Map cell lies under water above sea level (a plateau lake, at high_water_level).
const PAINT_HIGH_WATER := 2

## Width and depth of the map in metres (square, centred on the origin).
@export var size := 8000.0
## Grid points per side: cells per side + 1. The cells per side must divide
## evenly into Terrain.chunks.
@export var points := 2
## Ground height at each grid point, row by row (x along a row, rows along +Z).
@export var heights := PackedFloat32Array()
## One PAINT_* value per cell, row by row like heights.
@export var paint := PackedByteArray()
## Surface height of the water over PAINT_HIGH_WATER cells.
@export var high_water_level := 0.0
## Top of the tallest structure on each cell (0 where there's none), row by
## row: buildings, arches, bridges, rock spires. What the AI flies over.
@export var structures := PackedFloat32Array()
