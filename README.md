# Decision Intelligence System — Probabilistic Football Recruitment Analytics

> **Project status:** Evolving R&D project. This README distinguishes implemented capabilities from features in development and objectives that still require validation.

## 1. PROJECT OVERVIEW

### Problem
Football recruitment involves costly decisions under uncertainty. Recruitment teams must identify players who match a coach's tactical requirements, squad needs, and financial constraints. Decisions based on isolated statistics or reputation can lead to poor role fit, inefficient spending, and an unbalanced squad.

### Approach
This project develops a **Football Recruitment Decision Support framework** combining player-performance analysis, profiling, probabilistic estimation, tactical compatibility, and recruitment constraints.

- **Current implementation:** The repository contains football-data ingestion and player-analysis components, player profiling and comparison logic, tactical-fit components, and a Bayesian use case focused on estimating scoring ability from observed performance. The Bayesian approach represents an estimate as a probability distribution rather than only a point value.
- **Development direction:** Extend the framework towards a broader, role-aware view of player ability. Rather than treating goalscoring as a universal measure of talent, the intended design will represent abilities relevant to a player's role and tactical responsibilities, then connect those profiles to squad needs and recruitment constraints.
- **Validation objective:** Document a capability as implemented only when it is demonstrable in the code. New ability dimensions and decision outputs must be tested on suitable data and compared with appropriate baselines before being treated as reliable recruitment evidence.

The aim is to support better-informed decisions, not to replace scouting expertise or claim that a model can directly observe a player's “true talent”.

## 2. FOOTBALL RECRUITMENT PROBLEM

### Problem
Recruitment decisions can be distorted when clubs focus on headline statistics or well-known names rather than the specific role a candidate is expected to perform. A player may produce strong numbers in one team or tactical system and struggle in another. Decisions must also account for squad balance, budget, age profile, contractual situation, and alternative candidates.

### Approach
The framework organizes candidate evaluation around performance indicators, role requirements, tactical fit, and available recruitment information.

- **Current implementation:** Player-analysis and comparison components are present; workflow coverage depends on available input data and the current integration state.
- **Development direction:** Make the links between squad needs, role-specific profiles, tactical compatibility, and recruitment constraints more explicit in an end-to-end workflow.
- **Validation objective:** Test whether the framework produces useful and consistent shortlists under defined recruitment scenarios, comparing recommendations with transparent baselines or expert-defined criteria.

## 3. WHY TRADITIONAL PLAYER EVALUATION CAN BE MISLEADING

### Problem
Raw totals such as goals and assists can hide context. Playing time, team strength, tactical role, and opportunity volume affect observed output. A single statistic may reflect several factors rather than individual contribution. Defensive actions, progression, creation, and other role-relevant behaviours can also be overlooked when evaluation relies on headline metrics.

### Approach
The project aims to interpret observed performance in context rather than treat one statistic as a complete measure of player quality.

- **Current implementation:** Player-analysis components use match-performance indicators where available, including minutes, shots, expected goals (xG), goals, assists, dribbles, key passes, progressive passes, pressures, tackles, and interceptions. Actual coverage depends on the data source and pipeline.
- **Development direction:** Improve comparability through playing-time normalization, contextual adjustment, and role-aware feature selection. Additional physical or injury-related information may be incorporated if suitable data can be obtained and integrated.
- **Validation objective:** Verify metric definitions, missing-data handling, and normalization choices. Test whether adjustments improve comparability across players, teams, competitions, and roles.

GPS running distances, comprehensive injury histories, and other specialized data are not treated as current capabilities unless a working source and pipeline have been implemented and verified.

## 4. METHODOLOGY

### Problem
Football performance varies over time and is affected by limited samples, opportunity, team context, and random variation. A single observed statistic or deterministic score can give a misleading impression of certainty, especially when a player has limited playing time.

### Approach
The project uses Bayesian modelling to estimate an underlying performance ability while explicitly representing uncertainty.

- **Current implementation:** The current football Bayesian use case focuses on scoring ability. It combines prior assumptions with observed scoring-related information, such as xG and goals, to estimate a posterior distribution for the parameter defined by the model.
- **Development direction:** Generalize this approach into a reusable, role-aware **Bayesian Talent Engine**. The longer-term design will represent distinct abilities relevant to different roles—for example, chance creation and progression for some midfield roles, defensive actions for defenders, or shot-stopping for goalkeepers—rather than applying a goalscoring model to every player.
- **Validation objective:** For each new dimension, define the target quantity, statistical assumptions, required data, and uncertainty interpretation. Evaluate model fit and convergence, compare estimates with suitable baselines, and document where the model is and is not reliable.

“Underlying ability” refers to a latent quantity inferred from observed data; it is not a direct measurement of innate or permanent talent.

## 5. BAYESIAN PLAYER EVALUATION

### Problem
Football data can be noisy, and observed output may be based on limited minutes or few relevant events. A strong short-term result does not necessarily imply stable underlying ability. Point estimates also make it difficult to distinguish a precise estimate from one based on weak evidence.

### Approach
Bayesian inference combines prior assumptions with observed data to obtain a posterior distribution for a defined model parameter.

- **Current implementation:** The football Bayesian use case focuses on estimating scoring ability from scoring-related observations. It is not yet a comprehensive estimate of every dimension of player talent or of future transfer success.
- **Development direction:** Preserve the scoring model as an initial ability-specific model while designing a reusable structure for additional role-relevant dimensions. Model dimensions separately where their data-generating processes differ, then bring them together in a multidimensional player profile.
- **Validation objective:** Check sampling convergence and effective sample size, inspect trace plots and posterior distributions, and report credible intervals where appropriate. Test sensitivity to modelling assumptions and limited samples before using estimates to rank or compare recruitment targets.

## 6. UNCERTAINTY QUANTIFICATION

### Problem
A single rating can conceal how much evidence supports it. Two players with similar point estimates may have different uncertainty because of differences in minutes, event counts, or data quality. Without that distinction, decision-makers may place too much confidence in a fragile estimate.

### Approach
Bayesian modelling can express uncertainty through posterior distributions and, where appropriate, credible intervals.

- **Current implementation:** The scoring-ability model can represent uncertainty around its modelled parameter through its posterior distribution. Interpretation depends on model specification, data, and sampling diagnostics.
- **Development direction:** Extend uncertainty reporting to additional ability-specific models as they are implemented, showing uncertainty alongside profiles and comparisons rather than hiding it inside a single score.
- **Validation objective:** Verify convergence and sampling quality, examine sensitivity to priors and sample size, and assess calibration or predictive performance where a meaningful observed outcome is available. A credible interval describes uncertainty under the model; it is not a guarantee of future performance or transfer success.

## 7. RECRUITMENT DECISION SUPPORT

### Problem
Statistical outputs are not automatically useful to scouts or sporting decision-makers. Recruitment decisions also depend on the role to fill, tactical requirements, budget, contract situation, age profile, and alternative candidates. A performance estimate alone cannot determine whether a player should be signed.

### Approach
The decision-support layer is intended to connect player evidence to a defined recruitment context.

- **Current implementation:** The repository contains components for player comparison, profiling, tactical-fit analysis, and decision-oriented recommendations. Their outputs depend on the data and logic currently connected; this does not establish that the complete recruitment process has been validated.
- **Development direction:** Connect role-aware ability profiles and their uncertainty to explicit squad needs and recruitment constraints. The intended output is a transparent comparison of candidates and trade-offs, not an unexplained universal rating.
- **Validation objective:** Test recommendations against defined scenarios, inspect each criterion's contribution, and assess stability when budgets, role requirements, or assumptions change. Financial feasibility and tactical compatibility remain distinct decision dimensions.

## 8. PLAYER PROFILING & COMPARISON

### Problem
Players listed in the same position can perform different tactical roles. Comparing them using positional labels or raw totals alone may hide differences in style, responsibility, opportunity, and strengths. Useful comparison must reflect the role the club is trying to recruit for.

### Approach
The framework is moving towards role-aware profiles that preserve multiple performance dimensions rather than compress all player quality into one universal score.

- **Current implementation:** Existing analysis and profiling components use match-performance indicators where available and support player-comparison workflows. The Bayesian scoring-ability estimate is one specific modelled dimension, not a complete multidimensional talent assessment.
- **Development direction:** Define role-relevant dimensions and build separate estimates where justified by the data. Comparisons can combine observed metrics with probabilistic estimates where available, retaining each dimension's uncertainty and context.
- **Validation objective:** Confirm that dimensions are defined consistently, compare like with like where appropriate, and test whether profiles distinguish meaningful role differences. Do not claim comparisons of posterior distributions for dimensions that have not yet been modelled or validated.

## 9. TECHNICAL ARCHITECTURE

### Problem
A recruitment decision-support workflow requires data ingestion, consistent feature definitions, analysis, modelling, and decision-oriented outputs. Disconnected components or inconsistent assumptions can make comparisons difficult to reproduce or interpret.

### Approach
The repository is organized around data handling, player analysis, probabilistic modelling, and downstream decision-support components.

- **Current implementation:** The codebase includes data-loader components, player-analysis and profiling modules, comparison and tactical-fit components, and a Bayesian football use case. Integration and operational readiness can differ by module; the repository is not presented as a fully validated end-to-end product.
- **Development direction:** Refactor the Bayesian component into a reusable engine for ability-specific models, then connect its outputs to player profiles, comparisons, tactical-fit analysis, and recruitment decisions through clear interfaces.
- **Validation objective:** Test components individually and as an integrated pipeline; document inputs, outputs, assumptions, failure cases, and data provenance. Ensure downstream decisions use only outputs that are actually produced and checked.

## 10. DATA SOURCES

### Problem
Player evaluation can be limited by incomplete coverage, inconsistent definitions, and differences between providers or competitions. Contract and market information can help frame recruitment decisions, but should not be assumed to be available or equally reliable for every player.

### Approach
The framework is designed to work with football performance data and relevant player or recruitment context, depending on source availability.

- **Current implementation:** The repository includes loader components intended to retrieve and combine player-performance and market/contract-related information. Metrics and coverage in a particular run depend on source, competition, and successful pipeline execution. Simulated or test data supports development and method testing; it should not be presented as real-world validation.
- **Development direction:** Improve data provenance, coverage, consistency, and missing-value handling. Add specialized physical, tracking, or injury-related sources only when access, definitions, and integration are established.
- **Validation objective:** Record the source and date of each dataset, verify key fields and joins, inspect missingness and duplicates, and distinguish simulated demonstrations from analyses based on real observations.

## 11. CURRENT LIMITATIONS

### Problem
A useful recruitment framework must do more than run a model. It needs suitable data, reliable estimates, reproducible processing, interpretable outputs, and evidence that recommendations are meaningful. Gaps in any of these areas limit how confidently results can be used.

### Approach
The project is being developed incrementally, with implementation status and validation status treated as separate questions.

- **Current implementation:** The Bayesian football use case is narrower than the overall recruitment ambition, with scoring ability as its principal modelled dimension. Data breadth and the degree of integration across modules also constrain the claims that can be made.
- **Development direction:** Extend the model to role-specific ability dimensions, strengthen data pipelines and integration, and improve decision-facing visualizations and reporting.
- **Validation objective:** Establish repeatable tests and documented evidence for each new capability. A feature is not operational merely because it appears in the architecture or roadmap; a model is not recruitment-ready until its assumptions, diagnostics, and performance have been evaluated.

## 12. ROADMAP

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
