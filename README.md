# Decision Intelligence System — Probabilistic Football Recruitment Analytics

> **Project status:** Evolving R&D project. This README distinguishes implemented capabilities from features in development and objectives that still require validation.Controlled datasets support method testing and calculation audits, while FBref and Transfermarkt loaders provide an integration path for real football and market data.

## 1. PROJECT OVERVIEW

### Problem

Football recruitment involves costly decisions under uncertainty. Clubs do not simply need talented players; they need players who solve a specific squad problem within a coach’s tactical system and the club’s financial constraints.

A player may be talented in isolation but poorly suited to the required role, playing style, squad balance, or wage structure. Conversely, a less famous player may be the better recruitment solution because his abilities, tactical profile, projected contribution, and financial profile match the club’s need.

Decisions based on isolated statistics, reputation, or generic ratings can therefore lead to poor role fit, inefficient spending, and an unbalanced squad.

### Approach

This project develops an **Ideal-Profile Recruitment Matching System**.

The system first translates a club’s tactical identity, squad needs, and financial constraints into an **ideal player profile**. This profile describes the characteristics required to solve a specific recruitment problem.

The system then compares real players with that ideal profile across role-relevant ability dimensions, tactical requirements, and financial criteria. The output is a ranked shortlist of real players with the highest compatibility with the target profile.

```text
Coach needs + tactical system + squad need + financial constraints
                              ↓
                   Ideal Player Profile
                              ↓
                Comparison with real-player database
                              ↓
          Compatibility scores by ability dimension
                              ↓
             Financial compatibility and overall fit
                              ↓
              Ranked real-player recommendations
```

### Current implementation

The repository contains football-data ingestion and player-analysis components, player profiling and comparison logic, tactical-fit components, and an initial Bayesian use case focused on estimating scoring ability from observed performance.

The Bayesian approach represents an estimate as a probability distribution rather than only a point value.

### Development direction

Extend the framework from a single goalscoring-ability model to a role-aware Bayesian Talent Engine.

Rather than treating goalscoring as a universal measure of talent, the intended design will estimate separate ability dimensions relevant to different roles —
for example finishing, chance creation, progression, dribbling, passing security, pressing, defensive impact, duels, and goalkeeper-specific abilities.

These ability profiles will then be connected to an ideal player profile, a tactical-compatibility layer, and a financial-compatibility layer.

### Validation objective

Document a capability as implemented only when it is demonstrable in the code.

New ability dimensions, compatibility scores, financial estimates, and decision outputs must be tested on suitable data and compared with appropriate baselines before being treated as reliable recruitment evidence.

The aim is to support better-informed recruitment decisions, not to replace scouting expertise or claim that a model can directly observe a player’s “true talent”.

### Ideal-Profile Recruitment Matching

This project is built around a two-stage recruitment logic.

First, it translates a club’s coaching requirements, tactical identity, squad needs, and financial constraints into an **ideal player profile**. This profile describes the player characteristics required to solve a specific recruitment problem.

Second, it compares real players with that ideal profile across role-relevant ability dimensions and financial criteria. The output is a ranked shortlist of real players with the highest compatibility with the target profile.

### Central Question

**Given a club’s tactical identity, squad need, and financial constraints, what is the ideal player profile for the identified recruitment problem — and which real players are most compatible with that profile?**

The system does not start from a player and ask whether he fits the club.It starts from the club’s recruitment problem and asks which real players best match the profile required to solve it.

### How the System Works

```text
Coach needs + tactical system + squad need + financial constraints
                              ↓
                   Ideal Player Profile
                              ↓
                Comparison with real-player database
                              ↓
          Compatibility scores by ability dimension
                              ↓
             Financial compatibility and overall fit
                              ↓
              Ranked real-player recommendations
```

The ideal profile is a recruitment specification, not a claim that a perfect player exists. It defines the ability, tactical, squad-building, and financial characteristics required for a specific role.

### Expected Output

The central output is a **Recruitment Decision Brief** for each recommended
player.

### 1. Ideal Player Profile

The system first presents the profile it is searching for.

Example:

```text
🎯 Ideal Player Profile — Left Winger

Recruitment problem:
The squad needs a left-sided winger able to progress the ball, create chances, and support a high-pressing system.

Tactical target:
- High pressing intensity
- Progressive ball carrying
- Chance creation from wide areas
- Defensive contribution in transition

Squad target:
- Immediate rotation option with starter potential
- Age profile: 21–26
- Contract horizon: at least three years

Financial target:
- Transfer budget: €25m
- Maximum salary: €4m per year
- Preferred contract length: 4–5 years
```

### 2. Real-Player Compatibility Ranking

The system then ranks real players by overall compatibility with the ideal profile.

```text
🔍 Best matches with ideal profile

1. Player A — Overall compatibility: 86%
2. Player B — Overall compatibility: 81%
3. Player C — Overall compatibility: 77%
```

The overall score is always accompanied by a dimension-level breakdown, so the user can see where a player matches the target and where he deviates.

### 3. Dimension-Level Compatibility

For each recommended player, the system compares the real player with the ideal
profile across relevant dimensions.

```text
Dimension              Ideal target     Player A      Compatibility
Finishing              High             High          78%
Chance creation        High             Very high     91%
Ball progression       High             High          94%
Dribbling              High             High          88%
Pressing impact        High             High          90%
Defensive impact       Moderate         Low           71%
Transfer cost          ≤ €25m           €23m          82%
Salary                 ≤ €4m            €3.2m         88%
```

This makes the recommendation interpretable: a player may be an excellent match for creation and progression while remaining below target on defensive impact.

### 4. Financial Compatibility

Financial fit is treated as a distinct recruitment dimension.

```text
💰 Financial compatibility — Player A

Estimated transfer cost: €23m
Budget limit: €25m
Transfer-cost compatibility: 82%

Estimated salary: €3.2m per year
Salary limit: €4m per year
Salary compatibility: 88%

Contract situation:
Current contract expires: 2028
Recommended contract length: four years
Contract compatibility: 90%

Financial risk: Low to moderate
```

The system should also expose trade-offs, for example when a player fits the
wage structure but consumes most of the available transfer budget.

### 5. Recruitment Recommendation

The final output is a transparent decision-support recommendation.

```text
✅ Recruitment recommendation — Player A

Recommendation: TARGET
Overall compatibility: 86%
Confidence: Moderate

Why:
- Strong match with the ideal winger profile.
- High compatibility on creation, progression, dribbling, and pressing.
- Financially feasible within the defined budget and salary structure.

Conditions:
- Defensive impact is below the ideal target.
- Transfer cost leaves limited budget flexibility.
- Compare with at least two lower-cost alternatives.

This recommendation supports recruitment decision-making; it does not replace
scouting expertise or final club decision-making.
```

### What the System Does Not Claim

The ideal profile is not a perfect player.  
A high compatibility score does not guarantee transfer success, future performance, or financial return.

The system produces a transparent comparison between a player’s evidence and the specific system, role, and financial context in which the club intends to use them.

## 2. Visual Decision Interface

The central interface is not a generic analytics dashboard. It is a
**Recruitment Decision Brief**: a guided visual workflow that translates a
club’s recruitment problem into an ideal player profile, identifies real
players compatible with that profile, and explains the recommendation.

The interface is organised into four connected screens:

1. Recruitment Brief
2. Target-vs-Player Compatibility
3. Player Pitch Card
4. Financial Decision Panel

Each screen answers one decision question. Together, they allow a sporting
director or scout to understand the recruitment problem, the ideal solution,
the best real-player matches, and the conditions of the recommendation.

### Design Principle

The interface follows a decision-first structure:

```text
Club need → Ideal profile → Real-player matches → Dimension-level fit → Financial fit → Recommendation
```

The user should be able to understand the main answer in less than ten
seconds:

- What player profile does the club need?
- Which real players are closest to that profile?
- Where do they match or deviate?
- Are they financially feasible?
- What is the recommended action?

Visual complexity is deliberately limited. Colour, shape, and layout are used
to support decision-making, not decoration.

### Screen 1 — Recruitment Brief

### 1. Purpose

The Recruitment Brief defines the recruitment problem and presents the ideal
player profile generated from coach, tactical, squad-building, and financial
requirements.

### 2. User question

> “What player profile does the club need, and which real players best match it?”

### 3. Layout

```text
┌────────────────────────────────────────────────────────────────────┐
│ RECRUITMENT BRIEF — LEFT WINGER                                    │
│                                                                    │
│ Recruitment problem                                                │
│ Progressive, high-pressing left winger able to create chances      │
│ and support transitions.                                           │
│                                                                    │
│ Financial constraints                                              │
│ Transfer budget: €25m                                              │
│ Salary cap: €4m per year                                           │
│ Preferred contract: 4–5 years                                      │
│                                                                    │
│ IDEAL PLAYER PROFILE                                               │
│                                                                    │
│ Chance creation       ████████████████  High                       │
│ Ball progression      ████████████████  High                       │
│ Dribbling             ████████████████  High                       │
│ Pressing impact       ████████████████  High                       │
│ Finishing             ██████████          Moderate–High            │
│ Defensive impact      ██████              Moderate                 │
│                                                                    │
│ TOP REAL-PLAYER MATCHES                                            │
│                                                                    │
│ 1. Player A   Overall compatibility: 86%   [TARGET]               │
│ 2. Player B   Overall compatibility: 81%   [MONITOR]              │
│ 3. Player C   Overall compatibility: 77%   [MONITOR]              │
│                                                                    │
│ [Open detailed comparison]                                         │
└────────────────────────────────────────────────────────────────────┘
```

### 4. Required data

```python
{
    "recruitment_brief": {
        "target_position": "LEFT_WINGER",
        "recruitment_problem": "Progressive, high-pressing left winger",
        "tactical_context": {
            "playing_style": "high_press",
            "build_up_preference": "progressive",
            "defensive_structure": "high_block"
        },
        "squad_need": {
            "role": "rotation_with_starter_potential",
            "age_range":,[21][26]
            "contract_horizon_years":[3][5]
        },
        "financial_constraints": {
            "transfer_budget": 25_000_000,
            "salary_cap": 4_000_000,
            "preferred_contract_years":[4][5]
        }
    },
    "ideal_profile": {
        "finishing": {
            "target_level": "moderate_high",
            "weight": 0.15
        },
        "chance_creation": {
            "target_level": "high",
            "weight": 0.25
        },
        "ball_progression": {
            "target_level": "high",
            "weight": 0.25
        },
        "dribbling": {
            "target_level": "high",
            "weight": 0.15
        },
        "pressing_impact": {
            "target_level": "high",
            "weight": 0.15
        },
        "defensive_impact": {
            "target_level": "moderate",
            "weight": 0.05
        }
    },
    "recommended_players": [
        {
            "player": "Player A",
            "overall_compatibility": 0.86,
            "recommendation": "TARGET"
        },
        {
            "player": "Player B",
            "overall_compatibility": 0.81,
            "recommendation": "MONITOR"
        },
        {
            "player": "Player C",
            "overall_compatibility": 0.77,
            "recommendation": "MONITOR"
        }
    ]
}
```

### 5. Visual components

- A prominent title identifying the target role.
- A short recruitment-problem statement.
- Financial constraints displayed as compact badges.
- Horizontal bars for ideal-profile target levels.
- A ranked list of the top three real-player matches.
- A clear call-to-action to open the detailed comparison.

### 6. Colour rules

| Element | Colour | Meaning |
|---|---|---|
| Page background | `#F7F8FA` | Neutral, high-readability background |
| Primary text | `#1F2937` | Titles, player names, key figures |
| Secondary text | `#6B7280` | Context, labels, explanations |
| Ideal-profile bars | `#111827` | Neutral reference target |
| Player bars | `#1D4ED8` | Real-player evidence |
| Strong compatibility | `#15803D` | Clear match with target |
| Moderate compatibility | `#D97706` | Acceptable but requires attention |
| Weak compatibility or risk | `#B91C1C` | Significant deviation or financial risk |
| Pitch background | `#E8F3EC` | Subtle football context |

### Screen 2 — Target-vs-Player Compatibility

### 1. Purpose

This is the analytical core of the interface. It compares one real player with
the ideal profile across every relevant evaluation dimension.

### 2. User question

> “Where does this real player match the ideal profile, and where does he deviate?”

### 3. Layout

```text
┌────────────────────────────────────────────────────────────────────┐
│ TARGET vs PLAYER — Player A                                        │
│                                                                    │
│ Overall compatibility: 86%                                         │
│ Recommendation: TARGET                                             │
│ Confidence: Moderate                                               │
│                                                                    │
│ ABILITY COMPATIBILITY                                              │
│                                                                    │
│ Chance creation                                                    │
│ Player A   ████████████████████░░  91%                             │
│ Target     ────────────────  High                                  │
│                                                                    │
│ Ball progression                                                   │
│ Player A   █████████████████████  94%                              │
│ Target     ────────────────  High                                  │
│                                                                    │
│ Dribbling                                                          │
│ Player A   ████████████████████░░  88%                             │
│ Target     ────────────────  High                                  │
│                                                                    │
│ Pressing impact                                                    │
│ Player A   ████████████████████░░  90%                             │
│ Target     ────────────────  High                                  │
│                                                                    │
│ Finishing                                                          │
│ Player A   ████████████████░░░░░░  78%                             │
│ Target     ────────────────  Moderate–High                         │
│                                                                    │
│ Defensive impact                                                   │
│ Player A   ██████████████░░░░░░░░  71%                             │
│ Target     ──────────────────  Moderate                            │
│                                                                    │
│ MATCHES TARGET                                                     │
│ - Chance creation                                                  │
│ - Ball progression                                                 │
│ - Pressing impact                                                  │
│                                                                    │
│ DEVIATES FROM TARGET                                               │
│ - Defensive impact                                                 │
│ - Finishing is close to, but below, target                         │
└────────────────────────────────────────────────────────────────────┘
```

### 4. Required data

```python
{
    "player": "Player A",
    "overall_compatibility": 0.86,
    "recommendation": "TARGET",
    "confidence": "moderate",
    "dimension_compatibility": {
        "finishing": 0.78,
        "chance_creation": 0.91,
        "ball_progression": 0.94,
        "dribbling": 0.88,
        "pressing_impact": 0.90,
        "defensive_impact": 0.71
    },
    "ideal_profile": {
        "finishing": "moderate_high",
        "chance_creation": "high",
        "ball_progression": "high",
        "dribbling": "high",
        "pressing_impact": "high",
        "defensive_impact": "moderate"
    },
    "matches_target": [
        "chance_creation",
        "ball_progression",
        "pressing_impact"
    ],
    "deviates_from_target": [
        "defensive_impact"
    ],
    "uncertainty": {
        "finishing": {
            "hdi_low": 0.68,
            "hdi_high": 0.86
        },
        "chance_creation": {
            "hdi_low": 0.85,
            "hdi_high": 0.95
        }
    }
}
```

### 5. Visual components

- One horizontal bar per ability dimension.
- A vertical target marker showing the ideal-profile requirement.
- A compatibility percentage at the end of each bar.
- Two summary lists: `Matches target` and `Deviates from target`.
- Optional uncertainty bands or HDI annotations for Bayesian estimates.

### 6. Visual rule

Do not use a radar chart as the primary comparison. Radar charts can distort
magnitude perception and make cross-axis comparison slower. Use them only as a
secondary identity view, never as the main evidence.

### Screen 3 — Player Pitch Card

### 1. Purpose

The Player Pitch Card translates statistical compatibility into football
context. It shows the player’s intended role, main strengths, and fit with the
coach’s system.

### 2. User question

> “What role would this player occupy in our system, and what would he bring?”

### 3. Layout

```text
┌────────────────────────────────────────────────────────────────────┐
│ PLAYER A — LEFT WINGER                                             │
│                                                                    │
│ ┌──────────────────────────────────────────────────────────────┐   │
│ │                    PITCH CONTEXT                             │   │
│ │                                                              │   │
│ │                 Left flank / attacking third                 │   │
│ │                                                              │   │
│ │   Primary role: Progressive wide creator                     │   │
│ │   Secondary role: High-pressing forward                      │   │
│ └──────────────────────────────────────────────────────────────┘   │
│                                                                    │
│ SYSTEM FIT                                                         │
│                                                                    │
│ High pressing          ████████████████████  Strong                │
│ Progressive build-up   ████████████████████  Strong                │
│ Wide chance creation   ███████████████████░  Strong                │
│ Transition defence     ██████████████░░░░░░  Moderate              │
│                                                                    │
│ KEY STRENGTHS                                                      │
│ - Progressive carrying                                             │
│ - Chance creation from the left flank                              │
│ - Pressing intensity                                               │
│                                                                    │
│ WATCH-OUTS                                                         │
│ - Limited defensive-duel evidence                                  │
│ - Requires complementary defensive cover from left-back            │
└────────────────────────────────────────────────────────────────────┘
```

### 4. Required data

```python
{
    "player": "Player A",
    "primary_role": "Progressive wide creator",
    "secondary_role": "High-pressing forward",
    "pitch_context": {
        "primary_zone": "left_flank",
        "secondary_zone": "attacking_third"
    },
    "system_fit": {
        "high_pressing": {
            "score": 0.90,
            "level": "strong"
        },
        "progressive_build_up": {
            "score": 0.94,
            "level": "strong"
        },
        "wide_chance_creation": {
            "score": 0.91,
            "level": "strong"
        },
        "transition_defence": {
            "score": 0.71,
            "level": "moderate"
        }
    },
    "key_strengths": [
        "Progressive carrying",
        "Chance creation from the left flank",
        "Pressing intensity"
    ],
    "watch_outs": [
        "Limited defensive-duel evidence",
        "Requires complementary defensive cover from left-back"
    ]
}
```

### 5. Visual components

- A simplified vertical or horizontal pitch.
- A highlighted zone showing the player’s primary area of influence.
- Role labels: primary and secondary.
- System-fit bars linked to the coach’s tactical principles.
- Strengths and watch-outs in two separate lists.

### 6. Visual rule

The pitch is a contextual frame, not a detailed match map. It should show
**where the player fits**, not pretend to display tracking data that the system
does not currently have.

### Screen 4 — Financial Decision Panel

### 1. Purpose

The Financial Decision Panel separates sporting compatibility from financial
feasibility. It shows whether the player can realistically be signed within
the club’s constraints.

### 2. User question

> “Can the club afford this player, and what is the financial risk?”

### 3. Layout

```text
┌────────────────────────────────────────────────────────────────────┐
│ 💰 FINANCIAL DECISION PANEL — Player A                             │
│                                                                    │
│ TRANSFER COST                                                      │
│                                                                    │
│ €23m      [████████████████████░░░░]  €25m limit                   │
│ Compatibility: 82%                                                 │
│                                                                    │
│ SALARY                                                             │
│                                                                    │
│ €3.2m     [██████████████████████░░]  €4m limit                    │
│ Compatibility: 88%                                                 │
│                                                                    │
│ CONTRACT                                                           │
│                                                                    │
│ Current contract expires: 2028                                     │
│ Recommended contract length: 4 years                               │
│ Contract compatibility: 90%                                        │
│                                                                    │
│ FINANCIAL RISK                                                     │
│                                                                    │
│ Low–Moderate                                                       │
│                                                                    │
│ TRADE-OFF                                                          │
│ The player fits the wage structure, but the estimated transfer fee │
│ would consume 92% of the remaining transfer budget.                │
│                                                                    │
│ FINANCIAL RECOMMENDATION                                           │
│ Feasible, but budget flexibility is limited.                       │
└────────────────────────────────────────────────────────────────────┘
```

### 4. Required data

```python
{
    "player": "Player A",
    "financial_profile": {
        "estimated_transfer_cost": 23_000_000,
        "transfer_budget": 25_000_000,
        "transfer_cost_compatibility": 0.82,
        "estimated_salary": 3_200_000,
        "salary_cap": 4_000_000,
        "salary_compatibility": 0.88,
        "current_contract_expiry": "2028",
        "recommended_contract_years": 4,
        "contract_compatibility": 0.90,
        "financial_risk": "low_moderate",
        "budget_utilisation": 0.92
    },
    "financial_recommendation": {
        "status": "feasible_limited_flexibility",
        "message": "The player fits the wage structure, but the estimated transfer fee would consume 92% of the remaining transfer budget."
    }
}
```

### 5. Visual components

- Horizontal financial gauges for transfer cost and salary.
- Clear budget and salary-cap reference lines.
- A contract compatibility indicator.
- A financial-risk badge.
- A trade-off message explaining budget flexibility.

### 6. Colour rules

| Financial status | Colour | Meaning |
|---|---|---|
| Within comfortable limits | `#15803D` | Feasible |
| Close to limit | `#D97706` | Feasible but constrained |
| Above limit | `#B91C1C` | Not feasible under current constraints |

### LLM Recruitment Interpreter

The LLM acts as the **natural-language entry point** of the system. It does not
replace the Bayesian engine, similarity model, tactical-fit engine, or financial
engine. It translates a user request into a structured recruitment brief.

### 1. User input example

```text
Je veux un ailier créatif avec un fort pourcentage de dribbles réussis
et une finition au-dessus de la moyenne.
```

### 2. Expected system behaviour

```text
User request
     ↓
LLM Recruitment Interpreter
     ↓
Structured recruitment brief
     ↓
Ideal-profile generator
     ↓
Real-player compatibility engine
     ↓
Financial compatibility engine
     ↓
Visual Recruitment Decision Brief
```

### 3. LLM output schema

The LLM must return a validated JSON object, not free text.

```python
{
    "target_position": "LEFT_WINGER",
    "recruitment_problem": "Creative left winger with strong dribbling and above-average finishing",
    "tactical_context": {
        "playing_style": "possession_with_width",
        "build_up_preference": "progressive",
        "defensive_structure": "unspecified"
    },
    "squad_need": {
        "role": "wide_creator",
        "age_range":,[18][30]
        "contract_horizon_years":[3][5]
    },
    "financial_constraints": {
        "transfer_budget": None,
        "salary_cap": None,
        "preferred_contract_years":[3][5]
    },
    "ideal_profile": {
        "finishing": {
            "target_level": "above_average",
            "weight": 0.25
        },
        "chance_creation": {
            "target_level": "high",
            "weight": 0.30
        },
        "dribbling": {
            "target_level": "high",
            "weight": 0.30
        },
        "ball_progression": {
            "target_level": "moderate_high",
            "weight": 0.10
        },
        "pressing_impact": {
            "target_level": "moderate",
            "weight": 0.05
        }
    },
    "missing_information": [
        "transfer_budget",
        "salary_cap",
        "preferred_foot",
        "league_coverage"
    ],
    "assumptions": [
        "No financial constraint was specified, so financial compatibility will be reported as informational rather than decisive.",
        "Dribbling compatibility requires successful and attempted dribble data."
    ]
}
```

### 4. LLM responsibilities

The LLM should:

- Identify the target position or role.
- Extract tactical requirements.
- Convert qualitative requests into target levels.
- Assign initial dimension weights.
- Identify missing financial or squad-building information.
- Generate a structured recruitment brief.
- Explain the final recommendation in clear football language.

The LLM should not:

- Invent player statistics.
- Directly calculate final compatibility scores.
- Override Bayesian estimates.
- Produce a recruitment decision without the structured engines.
- Present missing data as known information.

### 5. Implementation Architecture

```text
User request
     ↓
LLM Recruitment Interpreter
     ↓
Structured Recruitment Brief
     ↓
IdealProfileBuilder
     ↓
PlayerCompatibilityEngine
     ↓
FinancialCompatibilityEngine
     ↓
DecisionAggregator
     ↓
Visual Brief Generator
```

### 6. Recommended modules

```text
interfaces/
└── recruitment_request.py

llm/
└── recruitment_interpreter.py

profile/
└── ideal_profile_builder.py

engines/
├── role_aware_talent_engine.py
├── player_compatibility_engine.py
└── financial_compatibility_engine.py

decision/
└── decision_aggregator.py

visualisation/
├── recruitment_brief.py
├── target_player_comparison.py
├── player_pitch_card.py
└── financial_decision_panel.py
```

### 7. Data contract

The visual layer should consume a single, stable object:

```python
RecruitmentDecisionBrief
```

This object should contain:

- The original user request.
- The structured recruitment brief.
- The ideal player profile.
- The ranked real-player matches.
- Dimension-level compatibility scores.
- Bayesian uncertainty where available.
- Financial compatibility.
- The final recommendation and confidence level.
- Missing information and assumptions.

This separation allows the same backend to generate an HTML report, a Streamlit
interface, a PDF, or a future web application.

## Visual Language

### 1. Typography

Use a single modern sans-serif family.

- Titles: bold, large, dark grey.
- Player names: semibold.
- Metric labels: regular, medium grey.
- Key figures: large and high-contrast.
- Explanatory text: small, secondary grey.

### 2. Shape language

- Use rounded rectangles for cards and panels.
- Use horizontal bars for ability and financial comparisons.
- Use a vertical line or marker for the ideal-profile target.
- Use badges for recommendation status.
- Use a simplified pitch only to provide football context.
- Avoid pie charts, 3D charts, decorative gauges, and dense multi-radar layouts.

### 3. Recommendation badges

| Recommendation | Colour | Meaning |
|---|---|---|
| `TARGET` | `#15803D` | Strong overall compatibility and feasible profile |
| `MONITOR` | `#D97706` | Interesting profile, but uncertainty or financial constraint exists |
| `AVOID` | `#B91C1C` | Major incompatibility or unacceptable financial/risk profile |
| `INSUFFICIENT DATA` | `#6B7280` | Evidence is too limited for a reliable recommendation |

## Implementation Priority

1. Build the structured `RecruitmentDecisionBrief` object.
2. Implement the four visual screens with static example data.
3. Connect the ideal-profile generator.
4. Connect the player-compatibility engine.
5. Connect the financial-compatibility engine.
6. Add the LLM interpreter as the natural-language entry point.
7. Add uncertainty, missing-data handling, and recommendation explanations.


## 3. FOOTBALL RECRUITMENT PROBLEM

### Problem
Recruitment decisions can be distorted when clubs focus on headline statistics or well-known names rather than the specific role a candidate is expected to perform. A player may produce strong numbers in one team or tactical system and struggle in another. Decisions must also account for squad balance, budget, age profile, contractual situation, and alternative candidates.

### Approach
The framework organizes candidate evaluation around performance indicators, role requirements, tactical fit, and available recruitment information.

- **Current implementation:** Player-analysis and comparison components are present; workflow coverage depends on available input data and the current integration state.
- **Development direction:** Make the links between squad needs, role-specific profiles, tactical compatibility, and recruitment constraints more explicit in an end-to-end workflow.
- **Validation objective:** Test whether the framework produces useful and consistent shortlists under defined recruitment scenarios, comparing recommendations with transparent baselines or expert-defined criteria.

## 4. WHY TRADITIONAL PLAYER EVALUATION CAN BE MISLEADING

### Problem
Raw totals such as goals and assists can hide context. Playing time, team strength, tactical role, and opportunity volume affect observed output. A single statistic may reflect several factors rather than individual contribution. Defensive actions, progression, creation, and other role-relevant behaviours can also be overlooked when evaluation relies on headline metrics.

### Approach
The project aims to interpret observed performance in context rather than treat one statistic as a complete measure of player quality.

- **Current implementation:** Player-analysis components use match-performance indicators where available, including minutes, shots, expected goals (xG), goals, assists, dribbles, key passes, progressive passes, pressures, tackles, and interceptions. Actual coverage depends on the data source and pipeline.
- **Development direction:** Improve comparability through playing-time normalization, contextual adjustment, and role-aware feature selection. Additional physical or injury-related information may be incorporated if suitable data can be obtained and integrated.
- **Validation objective:** Verify metric definitions, missing-data handling, and normalization choices. Test whether adjustments improve comparability across players, teams, competitions, and roles.

GPS running distances, comprehensive injury histories, and other specialized data are not treated as current capabilities unless a working source and pipeline have been implemented and verified.

## 5. METHODOLOGY

### Problem
Football performance varies over time and is affected by limited samples, opportunity, team context, and random variation. A single observed statistic or deterministic score can give a misleading impression of certainty, especially when a player has limited playing time.

### Approach
The project uses Bayesian modelling to estimate an underlying performance ability while explicitly representing uncertainty.

- **Current implementation:** The current football Bayesian use case focuses on scoring ability. It combines prior assumptions with observed scoring-related information, such as xG and goals, to estimate a posterior distribution for the parameter defined by the model.
- **Development direction:** Generalize this approach into a reusable, role-aware **Bayesian Talent Engine**. The longer-term design will represent distinct abilities relevant to different roles—for example, chance creation and progression for some midfield roles, defensive actions for defenders, or shot-stopping for goalkeepers—rather than applying a goalscoring model to every player.
- **Validation objective:** For each new dimension, define the target quantity, statistical assumptions, required data, and uncertainty interpretation. Evaluate model fit and convergence, compare estimates with suitable baselines, and document where the model is and is not reliable.

“Underlying ability” refers to a latent quantity inferred from observed data; it is not a direct measurement of innate or permanent talent.

## 6. BAYESIAN PLAYER EVALUATION

### Problem
Football data can be noisy, and observed output may be based on limited minutes or few relevant events. A strong short-term result does not necessarily imply stable underlying ability. Point estimates also make it difficult to distinguish a precise estimate from one based on weak evidence.

### Approach
Bayesian inference combines prior assumptions with observed data to obtain a posterior distribution for a defined model parameter.

- **Current implementation:** The football Bayesian use case focuses on estimating scoring ability from scoring-related observations. It is not yet a comprehensive estimate of every dimension of player talent or of future transfer success.
- **Development direction:** Preserve the scoring model as an initial ability-specific model while designing a reusable structure for additional role-relevant dimensions. Model dimensions separately where their data-generating processes differ, then bring them together in a multidimensional player profile.
- **Validation objective:** Check sampling convergence and effective sample size, inspect trace plots and posterior distributions, and report credible intervals where appropriate. Test sensitivity to modelling assumptions and limited samples before using estimates to rank or compare recruitment targets.

## 7. UNCERTAINTY QUANTIFICATION

### Problem
A single rating can conceal how much evidence supports it. Two players with similar point estimates may have different uncertainty because of differences in minutes, event counts, or data quality. Without that distinction, decision-makers may place too much confidence in a fragile estimate.

### Approach
Bayesian modelling can express uncertainty through posterior distributions and, where appropriate, credible intervals.

- **Current implementation:** The scoring-ability model can represent uncertainty around its modelled parameter through its posterior distribution. Interpretation depends on model specification, data, and sampling diagnostics.
- **Development direction:** Extend uncertainty reporting to additional ability-specific models as they are implemented, showing uncertainty alongside profiles and comparisons rather than hiding it inside a single score.
- **Validation objective:** Verify convergence and sampling quality, examine sensitivity to priors and sample size, and assess calibration or predictive performance where a meaningful observed outcome is available. A credible interval describes uncertainty under the model; it is not a guarantee of future performance or transfer success.

### Model Diagnostics

The Bayesian player-ability model is assessed through standard MCMC
diagnostics before posterior estimates are interpreted.

#### Role-Aware Ability Model

The Bayesian player-ability model estimates separate, role-relevant ability
dimensions rather than reducing player quality to a single goalscoring score.

Initial modelled dimensions include:

- Finishing: goals relative to expected goals (xG).
- Chance creation: assists relative to expected assisted goals (xAG).
- Dribbling: successful take-ons relative to attempted take-ons.
- Ball progression: progressive passes and carries per 90 minutes.
- Passing security: completed passes relative to attempted passes.
- Crossing: crosses per 90 minutes.
- Defensive impact: tackles and interceptions per 90 minutes.
- Pressing impact: pressures per 90 minutes.
- Aerial and ground duel ability: duels won relative to duels attempted.
- Goalkeeper shot stopping, penalty stopping, and distribution.

Ability dimensions are activated according to the player’s position group.
For example, dribbling and crossing are relevant for wingers and full-backs,
while shot stopping and penalty stopping are relevant for goalkeepers.

Physical-output dimensions such as distance covered, sprint volume, and
acceleration require a tracking or GPS source. They are not treated as current
capabilities unless such a source is integrated and validated.

#### Transfer Simulator Evolution

The Bayesian Transfer Simulator is evolving from a feature-independent Naive
Bayes structure to a hierarchical Bayesian logistic-regression model.

The logistic model estimates the joint effect of tactical fit, market context,
age, injury risk, and salary on transfer success. It produces posterior
predictive probabilities and credible intervals, rather than relying on an
approximate normal interval.

With limited historical transfer data, the model remains a simulation and
research tool. It does not produce recruitment decisions, and its calibration
and predictive performance must be evaluated on a sufficiently large and
representative historical dataset.


Diagnostics include:

- **R-hat:** checked to assess between-chain convergence.
- **Effective Sample Size:** `ess_bulk` and `ess_tail` are checked to assess
  sampling quality.
- **Trace plots:** generated for visual inspection of chain mixing and
  posterior stability.
- **Posterior distributions:** inspected for each modelled ability dimension.
- **Credible intervals:** 94% Highest Density Intervals (HDIs) are reported
  for each ability estimate.

A player profile therefore reports ability-specific estimates and uncertainty,
rather than a single universal talent score. A strong finishing estimate does
not imply strong chance creation, progression, or defensive impact.

The Bayesian Transfer Simulator uses conjugate Beta updates rather than MCMC
sampling. It reports an approximate uncertainty interval, not an MCMC-based
HDI.


## 8. RECRUITMENT DECISION SUPPORT

### Problem
Statistical outputs are not automatically useful to scouts or sporting decision-makers. Recruitment decisions also depend on the role to fill, tactical requirements, budget, contract situation, age profile, and alternative candidates. A performance estimate alone cannot determine whether a player should be signed.

### Approach
The decision-support layer is intended to connect player evidence to a defined recruitment context.

- **Current implementation:** The repository contains components for player comparison, profiling, tactical-fit analysis, and decision-oriented recommendations. Their outputs depend on the data and logic currently connected; this does not establish that the complete recruitment process has been validated.
- **Development direction:** Connect role-aware ability profiles and their uncertainty to explicit squad needs and recruitment constraints. The intended output is a transparent comparison of candidates and trade-offs, not an unexplained universal rating.
- **Validation objective:** Test recommendations against defined scenarios, inspect each criterion's contribution, and assess stability when budgets, role requirements, or assumptions change. Financial feasibility and tactical compatibility remain distinct decision dimensions.

## 9. PLAYER PROFILING & COMPARISON

### Problem
Players listed in the same position can perform different tactical roles. Comparing them using positional labels or raw totals alone may hide differences in style, responsibility, opportunity, and strengths. Useful comparison must reflect the role the club is trying to recruit for.

### Approach
The framework is moving towards role-aware profiles that preserve multiple performance dimensions rather than compress all player quality into one universal score.

- **Current implementation:** Existing analysis and profiling components use match-performance indicators where available and support player-comparison workflows. The Bayesian scoring-ability estimate is one specific modelled dimension, not a complete multidimensional talent assessment.
- **Development direction:** Define role-relevant dimensions and build separate estimates where justified by the data. Comparisons can combine observed metrics with probabilistic estimates where available, retaining each dimension's uncertainty and context.
- **Validation objective:** Confirm that dimensions are defined consistently, compare like with like where appropriate, and test whether profiles distinguish meaningful role differences. Do not claim comparisons of posterior distributions for dimensions that have not yet been modelled or validated.

## 10. TECHNICAL ARCHITECTURE

### Problem
A recruitment decision-support workflow requires data ingestion, consistent feature definitions, analysis, modelling, and decision-oriented outputs. Disconnected components or inconsistent assumptions can make comparisons difficult to reproduce or interpret.

### Approach
The repository is organized around data handling, player analysis, probabilistic modelling, and downstream decision-support components.

- **Current implementation:** The codebase includes data-loader components, player-analysis and profiling modules, comparison and tactical-fit components, and a Bayesian football use case. Integration and operational readiness can differ by module; the repository is not presented as a fully validated end-to-end product.
- **Development direction:** Refactor the Bayesian component into a reusable engine for ability-specific models, then connect its outputs to player profiles, comparisons, tactical-fit analysis, and recruitment decisions through clear interfaces.
- **Validation objective:** Test components individually and as an integrated pipeline; document inputs, outputs, assumptions, failure cases, and data provenance. Ensure downstream decisions use only outputs that are actually produced and checked.

The role-aware Bayesian Talent Engine is implemented as a dedicated engine
module. It receives structured player-performance features, estimates
role-relevant ability dimensions, and returns posterior ability profiles with
uncertainty.

The intended workflow is:

1. `FootballDataLoader` retrieves and combines FBref and Transfermarkt data.
2. The ability-feature layer prepares role-relevant metrics and per-90
   normalised inputs.
3. `RoleAwareBayesianTalentEngine` estimates ability-specific posterior
   distributions.
4. Player profiles, comparisons, tactical-fit analysis, and recruitment
   decision-support components consume these outputs.

## 11. DATA SOURCES

### Problem
Player evaluation can be limited by incomplete coverage, inconsistent definitions, and differences between providers or competitions. Contract and market information can help frame recruitment decisions, but should not be assumed to be available or equally reliable for every player.

### Approach
The framework is designed to work with football performance data and relevant player or recruitment context, depending on source availability.

- **Current implementation:** The repository includes loader components intended to retrieve and combine player-performance and market/contract-related information. Metrics and coverage in a particular run depend on source, competition, and successful pipeline execution. Simulated or test data supports development and method testing; it should not be presented as real-world validation.
- **Development direction:** Improve data provenance, coverage, consistency, and missing-value handling. Add specialized physical, tracking, or injury-related sources only when access, definitions, and integration are established.
- **Validation objective:** Record the source and date of each dataset, verify key fields and joins, inspect missingness and duplicates, and distinguish simulated demonstrations from analyses based on real observations.

### Data Strategy

Simulated and controlled datasets are used to test the methodology, while the
repository includes real football-data loaders and historical transfer data.

The project separates controlled demonstrations, source-derived observations,
and calculated outputs. A successful test on synthetic inputs is not treated
as evidence of real-world recruitment validity.

### 1. Prototype & Validation — Simulated and Controlled Data

Controlled player profiles are used to test analytical methods under explicit,
reproducible assumptions.

Profiles such as `FW Low`, `FW Medium`, `FW High`, and their midfield
equivalents provide structured inputs for checking:

- Per-90 metric calculations.
- Performance-score calculations and ordering.
- Percentile outputs within defined comparison groups.
- Consistency across positions and seasons.

Synthetic inputs can also be used to test probabilistic models under known
assumptions. However, the presence of a scored test dataset does not establish
that it has been used by the Bayesian model.

These datasets support calculation checks, method development, and controlled
demonstrations. They do not establish predictive accuracy, transfer success,
or real-world recruitment effectiveness.

Dataset classification depends on provenance and generation logic, not on the
filename alone.

### 2. Real-Data Integration — Source Loaders

`FootballDataLoader` provides an integration workflow for real football data
through dedicated source loaders.

| Component | Implemented role |
|---|---|
| `FBrefLoader` | Uses the `soccerdata` FBref interface to retrieve player season statistics through `read_player_season_stats(stat_type="standard")`. |
| `TransfermarktLoader` | Uses the `soccerdata` Transfermarkt interface to retrieve squad information through `read_squads()`. |
| `FootballDataLoader.build_global_scouting_dataset()` | Loads FBref and Transfermarkt data, joins the tables on `player`, derives contract years remaining when contract expiry is available, removes duplicate player names, and returns the combined scouting dataset. |
| `StatsBombLoader` | Instantiated by `FootballDataLoader`, but not called by the current global dataset-building method. StatsBomb integration is therefore not demonstrated by this workflow. |

This means the project is not limited to simulated inputs: it includes a
concrete path from external football sources to a combined player and market
dataset.

The actual fields, coverage, and successful retrieval depend on the selected
leagues and seasons, source availability, and execution of the loaders.

### 3. Historical Transfer Context

The repository includes `data/historical/historical_transfers.parquet`, a
historical transfer dataset intended to provide player and transfer context
for recruitment-oriented analysis.

Historical data can support retrospective analysis, but it does not
automatically validate current recruitment recommendations. Its use requires
documenting the covered seasons, competitions, transfer types, and any
restrictions introduced by data availability.

### 4. Provenance, Coverage & Current Boundaries

The project distinguishes:

- **Source-derived observations**: data retrieved through the FBref and
  Transfermarkt loaders.
- **Synthetic or controlled inputs**: constructed records used for testing and
  demonstration.
- **Derived outputs**: calculated metrics, scores, percentiles, or model
  estimates. Their interpretation depends on their inputs and calculation
  method.

Real-data runs should document the source, retrieval date, leagues, seasons,
and missing fields.

The current dataset-building workflow joins and deduplicates on player name.
Identity matching and preservation of team, competition, and season context
are therefore important validation points.

Contract years remaining are calculated relative to the execution year.
Historical analyses require an explicit reference date to avoid interpreting
past contract information against the current year.

Real-data integration and recruitment validation are separate milestones:
retrieving and combining observations does not by itself validate downstream
scores, Bayesian estimates, or recruitment recommendations.

## 12. CURRENT LIMITATIONS

### Problem
A useful recruitment framework must do more than run a model. It needs suitable data, reliable estimates, reproducible processing, interpretable outputs, and evidence that recommendations are meaningful. Gaps in any of these areas limit how confidently results can be used.

### Approach
The project is being developed incrementally, with implementation status and validation status treated as separate questions.

- **Current implementation:** The Bayesian football use case is narrower than the overall recruitment ambition, with scoring ability as its principal modelled dimension. Data breadth and the degree of integration across modules also constrain the claims that can be made.
- **Development direction:** Extend the model to role-specific ability dimensions, strengthen data pipelines and integration, and improve decision-facing visualizations and reporting.
- **Validation objective:** Establish repeatable tests and documented evidence for each new capability. A feature is not operational merely because it appears in the architecture or roadmap; a model is not recruitment-ready until its assumptions, diagnostics, and performance have been evaluated.

## 13. ROADMAP

### Problem
A probabilistic model becomes useful to non-technical stakeholders only when its outputs can be interpreted in context and connected to a clear decision. A complete recruitment workflow therefore requires progress in modelling, data quality, integration, and presentation—not just additional features.

### Approach
The roadmap is organized into three connected workstreams:

1. **Role-aware probabilistic modelling**
   - **Current implementation:** Bayesian estimation focused on scoring ability.
   - **Development direction:** Build a reusable engine for additional role-specific performance dimensions and integrate them into multidimensional player profiles.
   - **Validation objective:** Define each target and its data requirements, check diagnostics, compare against baselines, and document uncertainty and limitations before using the dimension in recruitment recommendations.

2. **Data pipeline and decision layer**
   - **Current implementation:** Data-loader and player-analysis components, with player comparison and tactical-fit logic present in the repository.
   - **Development direction:** Improve data coverage and consistency, and connect model outputs to squad needs, role requirements, and financial constraints.
   - **Validation objective:** Verify data quality and pipeline reproducibility; test the stability and usefulness of comparisons and recommendations under defined scenarios.

3. **Decision-facing interface and reporting**
   - **Current implementation:** Analytical and decision-support components exist in the codebase, with integration varying by module.
   - **Development direction:** Develop interactive visualizations for player profiles, posterior distributions, uncertainty, and recruitment trade-offs; explore natural-language scouting reports as a presentation layer.
   - **Validation objective:** Check that visualizations accurately represent the underlying data and model outputs, and ensure generated reports distinguish observed facts, model estimates, and unresolved uncertainty.

The roadmap will be updated as capabilities move from development to implementation and then through validation. This README is intended to reflect that progression without presenting planned work as completed functionality.
