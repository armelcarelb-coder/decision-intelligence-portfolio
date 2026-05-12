STRATEGIES = {
    "rentable": lambda p: p["profit"] > 0,
    "offensif": lambda p: p["shots"] >= 5,
    "efficace": lambda p: (
        p["efficiency"] == "clinical_finisher"
    ),
    "low_risk": lambda p: p["probability"] > 0.6,
    "polyvalent": lambda p: (
    p["style"] == "balanced_player"
)
}