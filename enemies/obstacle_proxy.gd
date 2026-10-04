class_name ObstacleProxy
extends Node3D
## An invisible sphere the AI steers around. Large, non-spherical things (like
## the destroyer's hull) are covered with a set of these, because AI obstacle
## avoidance treats every obstacle as a sphere of `radius`.

@export var radius := 10.0


func _ready() -> void:
	add_to_group("obstacles")
