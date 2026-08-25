from football_data.loader import FootballDataLoader
from football_data.performance_loader import PerformanceLoader

football_loader = FootballDataLoader(
    leagues=["ESP-La Liga"],
    seasons=["2425"]
)

performance_loader = PerformanceLoader(
    football_loader=football_loader,
    offline=False
)

df = performance_loader.load()