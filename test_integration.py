from profiling.player_profiler import PlayerProfiler
from profiling.archetype_engine import ArchetypeEngine
from tactical.tactical_fit_engine import TacticalFitEngine
from market.market_intelligence import MarketIntelligence


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
    "dribbles_per90": 3.5,

    "age": 24,
    "market_value": 35,
    "contract_years_left": 1,
    "salary": 7,
    "injury_risk": "low"
}


profiler = PlayerProfiler()
archetype_engine = ArchetypeEngine()
tactical_engine = TacticalFitEngine()
market_engine = MarketIntelligence()


player = profiler.process(player)

player = archetype_engine.process(player)

player = tactical_engine.process(player)

player = market_engine.process(player)


print("\nFINAL PLAYER")

print(
    "Archetype:",
    player["primary_archetype"]
)

print(
    "Tactical fit:",
    player["fit_score"]
)

print(
    "Market score:",
    player["market_score"]
)

print(
    "Market level:",
    player["market_level"]
)