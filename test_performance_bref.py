import soccerdata as sd


print("=" * 70)
print("TEST EXTRACTION FBREF RÉELLE")
print("=" * 70)

print("\n[1] Initialisation FBref...")

fbref = sd.FBref(
    leagues=["ESP-La Liga"],
    seasons=["2425"],
)

print("✓ FBref initialisé")

print("\n[2] Extraction des statistiques joueurs...")

try:

    df = fbref.read_player_season_stats(
        stat_type="standard"
    )

    print("✓ Extraction réussie")

    print("\nDATASET")
    print("-" * 70)

    print(f"Shape : {df.shape}")

    print("\nCOLONNES")
    print("-" * 70)

    print(df.columns.tolist())

    print("\nAPERÇU")
    print("-" * 70)

    print(df.head())

except Exception as e:

    print("\n✗ EXTRACTION FBREF ÉCHOUÉE")
    print(f"Erreur : {type(e).__name__}: {e}")

print("\n" + "=" * 70)
print("FIN DU TEST")
print("=" * 70)