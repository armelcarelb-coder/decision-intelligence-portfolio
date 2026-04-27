STRATEGIES = {
    "rentable": lambda p: p["profit"] > 0,
    "offensif": lambda p: p["style"] == "high_volume_player",
    "efficace": lambda p: p["efficiency"] == "clinical_finisher",
    "low_risk": lambda p: p["probability"] > 0.6
}