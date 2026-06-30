class TransferWindowOptimizer:

    def optimize_window(
        self,
        ranking,
        needs,
        budget
    ):
        """
        Main entry point.

        Parameters
        ----------
        ranking : list
            Output of RecruitmentPrioritizationEngine

        needs : dict
            Output of RecruitmentNeedsEngine

        budget : float
            Transfer budget (M€)
        """

        signings, monitor, reject, budget_used = self._select_signings(
            ranking,
            needs,
            budget
        )

        budget_report = self._allocate_budget(
            budget,
            budget_used
        )

        window_rating = self._evaluate_window(
            signings,
            budget_report,
            needs
        )

        summary = self._generate_summary(
            signings,
            monitor,
            reject,
            budget_report,
            window_rating,
            needs
        )

        return {

            "recommended_signings": signings,

            "monitor": monitor,

            "reject": reject,

            **budget_report,

            "window_rating": window_rating,

            "summary": summary
        }

    # =====================================================
    # SIGNING SELECTION
    # =====================================================

    def _select_signings(
        self,
        ranking,
        needs,
        budget
    ):

        signings = []

        monitor = []

        reject = []

        budget_used = 0

        covered_positions = set()

        needed_positions = self._extract_needed_positions(
            needs
        )

        ranking = sorted(
            ranking,
            key=lambda x: x.get(
                "recruitment_score",
                0
            ),
            reverse=True
        )

        for player in ranking:

            position = player.get(
                "position",
                ""
            )

            value = player.get(
                "market_value",
                0
            )

            decision = player.get(
                "transfer_decision",
                "MONITOR"
            )

            # Already covered

            if position in covered_positions:
                continue

            # No tactical need

            if (
                needed_positions
                and position not in needed_positions
            ):

                reject.append({

                    **player,

                    "reject_reason":
                        "position not required"
                })

                continue

            # Wrong transfer decision

            if decision != "SIGN":

                monitor.append(player)

                continue

            # Budget exceeded

            if budget_used + value > budget:

                monitor.append({

                    **player,

                    "monitor_reason":
                        "budget limitation"
                })

                continue

            signings.append(player)

            budget_used += value

            covered_positions.add(position)

        return (
            signings,
            monitor,
            reject,
            budget_used
        )

    # =====================================================
    # BUDGET
    # =====================================================

    def _allocate_budget(
        self,
        budget,
        budget_used
    ):

        remaining = budget - budget_used

        usage = 0

        if budget > 0:

            usage = round(
                budget_used / budget,
                2
            )

        return {

            "budget_total": budget,

            "budget_used": budget_used,

            "budget_remaining": remaining,

            "budget_usage": usage
        }

    # =====================================================
    # WINDOW EVALUATION
    # =====================================================

    def _evaluate_window(
        self,
        signings,
        budget_report,
        needs
    ):

        needed_positions = self._extract_needed_positions(
            needs
        )

        covered = 0

        for player in signings:

            if player.get("position") in needed_positions:

                covered += 1

        if needed_positions:

            coverage = covered / len(
                needed_positions
            )

        else:

            coverage = 1

        avg_probability = 0

        if signings:

            avg_probability = sum(

                p.get(
                    "success_probability",
                    0
                )

                for p in signings

            ) / len(signings)

        budget_usage = budget_report[
            "budget_usage"
        ]

        score = (

            coverage * 40

            + avg_probability * 40

            + budget_usage * 20

        )

        if score >= 85:

            return "EXCELLENT"

        if score >= 70:

            return "GOOD"

        if score >= 50:

            return "AVERAGE"

        return "POOR"

    # =====================================================
    # SUMMARY
    # =====================================================

    def _generate_summary(
        self,
        signings,
        monitor,
        reject,
        budget_report,
        window_rating,
        needs
    ):

        summary = []

        summary.append(

            f"Budget : {budget_report['budget_total']} M€"
        )

        summary.append(

            f"Used : {budget_report['budget_used']} M€"
        )

        summary.append(

            f"Remaining : {budget_report['budget_remaining']} M€"
        )

        summary.append(

            f"Recommended signings : {len(signings)}"
        )

        summary.append(

            f"Monitor list : {len(monitor)}"
        )

        summary.append(

            f"Rejected : {len(reject)}"
        )

        needed_positions = self._extract_needed_positions(
            needs
        )

        covered = len({

            p.get("position")

            for p in signings

        })

        summary.append(

            f"Needs covered : {covered}/{len(needed_positions)}"
        )

        summary.append(

            f"Window rating : {window_rating}"
        )

        return summary

    # =====================================================
    # UTILITIES
    # =====================================================

    def _extract_needed_positions(
        self,
        needs
    ):

        positions = set()

        for category in needs.values():

            for item in category:

                position = item.get(
                    "position"
                )

                if position:

                    positions.add(position)

        return positions