from fpdf import FPDF

class ReportGenerator:

    def generate(self, best_player):

        pdf = FPDF()

        pdf.add_page()

        pdf.set_font("Arial", size=12)

        pdf.cell(
            200,
            10,
            txt="SCOUT REPORT",
            ln=True
        )

        pdf.cell(
            200,
            10,
            txt=f"Player: {best_player['player']}",
            ln=True
        )

        pdf.cell(
            200,
            10,
            txt=f"Profit: {best_player['profit']:.2f}",
            ln=True
        )

        pdf.output("SCOUT_REPORT.pdf")