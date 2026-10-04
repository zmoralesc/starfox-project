class_name Clouds
extends Node3D
## Puffy cartoon clouds for planet missions: clusters of soft toon-shaded blobs
## scattered at a few altitudes. No collision, so you fly straight through
## them; a cluster fades out while the camera is inside or near it (like the
## wingmen do), so it never fills the screen with white.
##
## Each cluster is merged into one mesh (one draw call). Seeded, so the sky
## looks the same every run.

@export var cloud_seed := 7
## How many clusters.
@export var count := 60
## Clusters are scattered within this distance of the centre.
@export var spread := 1700.0
## No clusters within this horizontal distance of the centre, so the mission's
## intro shot stays clear.
@export var clear_radius := 350.0
## Altitudes of the cloud layers; each cluster picks one, give or take 30 m.
@export var layers: PackedFloat32Array = [220.0, 430.0]
## Blobs per cluster (min, max).
@export var puffs := Vector2i(5, 9)
## Blob radius (min, max).
@export var puff_radius := Vector2(18.0, 40.0)
## Blobs are squashed to this fraction of their height.
@export var flatten := 0.6
@export var material: Material

@export_group("Camera fade")
## Start fading when the camera is this close to a cluster's outer edge.
@export var fade_distance := 40.0
## Transparency once the camera is inside a cluster (1 = invisible).
@export_range(0.0, 1.0) var fade_max := 0.85

## Each cluster's mesh, centre and radius.
var _clusters: Array[MeshInstance3D] = []
var _centres := PackedVector3Array()
var _radii := PackedFloat32Array()


func _ready() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = cloud_seed
	var blob := SphereMesh.new()
	blob.radius = 1.0
	blob.height = 2.0
	blob.radial_segments = 10
	blob.rings = 6
	for k in count:
		var centre := Vector3.ZERO
		for attempt in 20:
			var angle := rng.randf() * TAU
			var distance := sqrt(rng.randf()) * spread
			centre = Vector3(cos(angle) * distance, 0.0, sin(angle) * distance)
			if distance > clear_radius:
				break
		centre.y = layers[rng.randi() % layers.size()] + rng.randf_range(-30.0, 30.0)
		_add_cluster(rng, blob, centre)


func _add_cluster(rng: RandomNumberGenerator, blob: SphereMesh, centre: Vector3) -> void:
	var st := SurfaceTool.new()
	var radius := 0.0
	var n := rng.randi_range(puffs.x, puffs.y)
	# Blobs strung out along one direction, biggest in the middle.
	var along := Vector3(cos(rng.randf() * TAU), 0.0, sin(rng.randf() * TAU)).normalized()
	for b in n:
		var middle := 1.0 - absf((b + 0.5) / n * 2.0 - 1.0)
		var r := lerpf(puff_radius.x, puff_radius.y, middle * rng.randf_range(0.7, 1.0))
		var offset := along * (b - n * 0.5) * r * 0.9 \
			+ Vector3(rng.randf_range(-0.4, 0.4), rng.randf_range(-0.15, 0.25), rng.randf_range(-0.4, 0.4)) * r
		var xf := Transform3D(Basis.from_scale(Vector3(r, r * flatten, r)), offset)
		st.append_from(blob, 0, xf)
		radius = maxf(radius, offset.length() + r)
	var cluster := MeshInstance3D.new()
	cluster.mesh = st.commit()
	cluster.material_override = material
	cluster.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	cluster.position = centre
	add_child(cluster)
	_clusters.append(cluster)
	_centres.append(centre)
	_radii.append(radius)


func _process(_delta: float) -> void:
	var camera := get_viewport().get_camera_3d()
	if camera == null:
		return
	var eye := camera.global_position
	for k in _clusters.size():
		var gap := eye.distance_to(_centres[k]) - _radii[k]
		var fade := (1.0 - smoothstep(0.0, fade_distance, gap)) * fade_max
		if not is_equal_approx(_clusters[k].transparency, fade):
			_clusters[k].transparency = fade
