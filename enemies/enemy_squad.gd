class_name EnemySquad
extends RefCounted
## Enemy fighters that arrived together (a wave, a hangar launch, a
## destroyer's escorts) and look out for each other: see the "Squad" exports
## on EnemyFighter. Members leave when destroyed.

var members: Array[EnemyFighter] = []


## Puts `fighter` in this squad (call before or after it enters the tree).
func add(fighter: EnemyFighter) -> void:
	members.append(fighter)
	fighter.squad = self
	fighter.destroyed.connect(_on_member_destroyed.bind(fighter))


## Everyone else in the squad still flying, nearest to `fighter` first.
func mates_of(fighter: EnemyFighter) -> Array[EnemyFighter]:
	var mates: Array[EnemyFighter] = []
	for member in members:
		if is_instance_valid(member) and member != fighter and not member.is_queued_for_deletion():
			mates.append(member)
	var from := fighter.global_position
	mates.sort_custom(func(a: EnemyFighter, b: EnemyFighter) -> bool:
		return a.global_position.distance_squared_to(from) < b.global_position.distance_squared_to(from))
	return mates


func _on_member_destroyed(fighter: EnemyFighter) -> void:
	members.erase(fighter)
