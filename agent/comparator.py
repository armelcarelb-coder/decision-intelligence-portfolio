class PlayerComparator:

    def compare_players(self, player_a, player_b):

        comparison = []

        # profit
        if player_a["profit"] > player_b["profit"]:
            comparison.append(
                f"{player_a['player']} est plus rentable"
            )
        else:
            comparison.append(
                f"{player_b['player']} est plus rentable"
            )

        # risque
        if player_a["probability"] > player_b["probability"]:
            comparison.append(
                f"{player_a['player']} est moins risqué"
            )
        else:
            comparison.append(
                f"{player_b['player']} est moins risqué"
            )

        # style
        comparison.append(
            f"{player_a['player']} : {player_a['style']}"
        )

        comparison.append(
            f"{player_b['player']} : {player_b['style']}"
        )

        return comparison