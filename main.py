from data.football_loader import FootballDataLoader
from agent.scout_agent import ScoutAgent

loader = FootballDataLoader()

matches = loader.get_matches(11, 42)
match_ids = matches.head(5)['match_id']

players = loader.get_players_in_match(match_ids.iloc[0])
players = players[:5]

agent = ScoutAgent(loader)

while True:
    request = input("\n💬 Que veux-tu analyser ? (exit pour quitter) : ")

    if request.lower() == "exit":
        break

    response = agent.run(request, players, match_ids)
    print(response)
    
print(agent.memory.get_history())