"""The fitness plugin: strength & conditioning (gym) videos -> sets, per-rep measurements, muscle map, coaching.

One session of lifts filmed on a phone: the agent splits it into sets and names each exercise from the library
(library/exercises.json), a pose pass measures every rep of the side-view sets (depth, trunk lean, tempo, bar path,
slowing across the set), and the report explains each exercise, what the muscles do and how to adjust it for the
athlete's sport. See docs/fitness.md.
"""
NAME = "fitness"
SPORT = "strength training"
