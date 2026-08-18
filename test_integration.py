from profiling.player_profiler import PlayerProfiler
from profiling.archetype_engine import ArchetypeEngine
from tactical.tactical_fit_engine import TacticalFitEngine


player = {

    "player": "Test Player",

    "position": "ST",

    "shots_per90": 3.0,

    "xg_per90": 0.50,

    "goals_per90": 0.60,

    "assists_per90": 0.20,

    "key_passes_per90": 1.6,

    "progressive_passes_per90": 4.5,

    "pressures_per90": 7.0,

    "tackles_per90": 1.0,

    "interceptions_per90": 0.5,

    "dribbles_per90": 3.5
}


profiler = PlayerProfiler()

archetype_engine = ArchetypeEngine()

tactical_engine = TacticalFitEngine()


player = profiler.process(player)

player = archetype_engine.process(player)

player = tactical_engine.process(player)


print("\nFINAL PLAYER")

for key, value in player.items():

    print(
        f"{key}: {value}"
    )