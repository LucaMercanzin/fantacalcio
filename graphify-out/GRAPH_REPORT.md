# Graph Report - .  (2026-09-01)

## Corpus Check
- 191 files · ~367,359 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1695 nodes · 4302 edges · 123 communities (101 shown, 22 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 129 edges (avg confidence: 0.65)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Dashboard Data Access Py
- Dashboard Data Access Py
- Dashboard Data Access Py
- Pipeline Run Photos Transfermarkt
- Pipeline Run Scraping Py
- Dashboard Data Access Py
- Config Py
- Ranking Percentile Py
- Dashboard Components Py
- Db Repository Py
- Consensus Engine Py
- Ranking Ideal Squad Py
- Project Community
- Consensus Engine Py
- Dashboard Data Access Py
- Consensus Engine Py
- Dashboard Components Py
- Dashboard Common Py
- Db Repository Py
- Pipeline Run Scraping Py
- Ranking Goalkeepers Py
- Project Community
- Ranking Scorer Py
- Db Repository Py
- Db Repository Py
- Dashboard Components Py
- Dashboard Data Access Py
- Matching Player Matcher Py
- Matching Player Matcher Py
- Ranking Goalkeeper Score Py
- Db Repository Py
- Ranking Scorer Py
- Fantacalcio Audit 2026 08
- Consensus Engine Py
- Dashboard Components Py
- Scrapers Fantacalciopedia Py
- Db Connection Py
- Ranking Fantamedia Py
- Scripts Simulate Auctions Py
- Ranking Purchase Advisor Py
- Ranking Tactical Profile Py
- Scripts Diagnose Missing Prices
- Pipeline Run Fixture Difficulty
- Scrapers Fantacalcio It Py
- Scrapers Fantanalisi Py
- Scrapers Fantanalisi Giocatore Py
- Db Repository Py
- Pipeline Run Match Ratings
- Ranking Lp Optimizer Py
- Consensus Engine Py
- Dashboard Data Access Py
- Ranking Budget Py
- Ranking Correlation Py
- Ranking Scorer Py
- Fantacalcio Audit 2026 08
- Dashboard Team Info Py
- Giocatori Griglia Portieri 2026
- Dashboard Components Py
- Project Community
- Grafica Screenshot 2026 08
- Grafica Screenshot 2026 08
- Fantacalcio Impossibile Analisi Avanzata
- Ranking Price Engine Py
- Dashboard Data Access Py
- Ranking Scorer Py
- Scrapers Pianetafanta Py
- Db Repository Py
- Giocatori Movimento Md
- Grafica Screenshot 2026 08
- Grafica Screenshot 2026 08
- Scrapers Fantacalcio Online Py
- Dashboard Data Access Py
- Specs 2026 08 26
- Grafica Screenshot 2026 08
- Fantacalcio Backlog 2026 08
- Specs 2026 08 25
- Giocatori Griglia Portieri 2026
- Fantacalcio Impossibile Mlops Governance
- Tests Test Data Access
- Plans 2026 08 27
- Specs 2026 08 22
- Fixtures Fantacalciopedia Detail Sample
- Grafica Grafica Md
- Fantacalcio Agents Md
- Fantacalcio Audit 2026 08
- Plans 2026 08 27
- Plans 2026 08 27
- Plans 2026 08 27
- Fixtures Transfermarkt Search Sample
- Giocatori Griglia Portieri 2026
- Giocatori Portieri Md
- Fantacalcio Impossibile Asta Live
- Specs 2026 08 26
- Docs Task Scheduler Setup
- Fantacalcio Environment Yml
- Project Community
- Fixtures Fantacalcio It Sample
- Fixtures Fantapazz Sample Html
- Fixtures Transfermarkt Profile Sample
- Skill Observations Cross Cutting
- Tests Test Domain Invariants
- Fantacalcio Audit Md 2026
- Specs 2026 08 26
- Specs 2026 08 26
- Fixtures Fantacalciopedia Sample Html
- Giocatori Griglia Portieri 2026
- Giocatori Griglia Portieri 2026
- Giocatori Griglia Portieri 2026
- Giocatori Griglia Portieri 2026
- Giocatori Griglia Portieri 2026
- Giocatori Griglia Portieri 2026
- Giocatori Griglia Portieri 2026
- Fantacalcio Requirements Dev Txt
- Fantacalcio Runtime Txt

## God Nodes (most connected - your core abstractions)
1. `get_connection()` - 223 edges
2. `init_db()` - 217 edges
3. `upsert_player()` - 118 edges
4. `PlayerRecord` - 65 edges
5. `insert_quotation()` - 53 edges
6. `run_pipeline()` - 49 edges
7. `_merge_player_rows()` - 45 edges
8. `get_ranked_role()` - 42 edges
9. `BaseScraper` - 34 edges
10. `normalize_team()` - 31 edges

## Surprising Connections (you probably didn't know these)
- `Scraper to matching to ranking to dashboard architecture` --semantically_similar_to--> `Multi-source scraping and ranking pipeline`  [INFERRED] [semantically similar]
  docs/superpowers/plans/2026-08-22-fantacalcio-scraper-dashboard.md → README.md
- `Auction Price Estimates by League Format` --semantically_similar_to--> `Price Engine`  [INFERRED] [semantically similar]
  fixtures/fantacalcio_online_sample.html → docs/superpowers/specs/2026-08-26-price-engine-decision-center-design.md
- `Decision Center` --semantically_similar_to--> `Fantasy Football Decision Engine`  [INFERRED] [semantically similar]
  impossibile-analisi-avanzata.md → visione-progetto.md
- `test_compute_listino_to_auction_factor_falls_back_with_few_samples()` --calls--> `compute_listino_to_auction_factor()`  [INFERRED]
  tests/test_data_access.py → consensus/engine.py
- `test_merge_player_rows_importable_and_works_standalone()` --calls--> `_merge_player_rows()`  [EXTRACTED]
  tests/test_consensus_engine.py → consensus/engine.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Continuous quality checks** — github_workflows_ci_ci_pipeline, github_workflows_codeql_codeql_analysis, github_workflows_lint_ruff_check, github_workflows_python_package_conda_conda_build [INFERRED 0.95]
- **Critical data correctness cluster** — opus_project_review_incompatible_price_scales, opus_project_review_rating_scale_fallback, opus_project_review_missing_value_sentinel, opus_project_review_unscoped_statistics, opus_project_review_unstable_player_identity, opus_project_review_transfer_duplicates [EXTRACTED 1.00]
- **Fantacalcio multi-source data flow** — readme_multi_source_pipeline, docs_superpowers_plans_2026_08_22_fantacalcio_scraper_dashboard_cross_source_reconciliation, docs_superpowers_plans_2026_08_22_fantacalcio_scraper_dashboard_layered_architecture, docs_scheda_giocatore_multi_source_normalization [INFERRED 0.95]
- **Player Detail External Data Flow** — docs_superpowers_plans_2026_08_27_scheda_giocatore_dati_esterni_transfermarkt_biographical_data, docs_superpowers_plans_2026_08_27_scheda_giocatore_dati_esterni_fantanalisi_advanced_stats, docs_superpowers_plans_2026_08_27_scheda_giocatore_dati_esterni_fixture_difficulty [EXTRACTED 1.00]
- **Fantacalciopedia Detail Signal Bundle** — fixtures_fantacalciopedia_detail_sample_fcp_algorithm_score, fixtures_fantacalciopedia_detail_sample_predicted_player_output, fixtures_fantacalciopedia_detail_sample_player_skill_tags, fixtures_fantacalciopedia_detail_sample_investment_and_injury_metrics, fixtures_fantacalciopedia_detail_sample_multiseason_player_statistics [EXTRACTED 1.00]
- **Auction Decision Signal Flow** — docs_superpowers_specs_2026_08_26_price_engine_decision_center_design_price_engine, docs_superpowers_specs_2026_08_26_price_engine_decision_center_design_scarcity_score, docs_superpowers_specs_2026_08_26_price_engine_decision_center_design_replacement_advantage, docs_superpowers_specs_2026_08_26_price_engine_decision_center_design_decision_center [EXTRACTED 1.00]
- **Ideal Squad Decision Flow** — giocatori_movimento_role_specific_scoring, giocatori_rosa_ideale_value_per_credit, giocatori_rosa_ideale_ideal_squad_construction [INFERRED 0.85]
- **Governed Decision Engine** — impossibile_mlops_governance_data_quality_layer, impossibile_mlops_governance_model_governance, visione_progetto_decision_engine [INFERRED 0.85]
- **Auction Intelligence Flow** — impossibile_asta_live_real_time_auction_state, impossibile_asta_live_auction_pressure, impossibile_asta_live_portfolio_risk [EXTRACTED 1.00]
- **Abbinamenti con punteggio minimo 0** — giocatori_griglia_portieri_2026_2027_inter, giocatori_griglia_portieri_2026_2027_milan, giocatori_griglia_portieri_2026_2027_juventus, giocatori_griglia_portieri_2026_2027_torino, giocatori_griglia_portieri_2026_2027_lazio, giocatori_griglia_portieri_2026_2027_roma [EXTRACTED 1.00]
- **Abbinamenti evidenziati con punteggio da 3 a 5** — giocatori_griglia_portieri_2026_2027_napoli, giocatori_griglia_portieri_2026_2027_roma, giocatori_griglia_portieri_2026_2027_inter, giocatori_griglia_portieri_2026_2027_sassuolo, giocatori_griglia_portieri_2026_2027_lecce, giocatori_griglia_portieri_2026_2027_parma, giocatori_griglia_portieri_2026_2027_atlanta, giocatori_griglia_portieri_2026_2027_frosinone, giocatori_griglia_portieri_2026_2027_genoa, giocatori_griglia_portieri_2026_2027_juventus [EXTRACTED 1.00]
- **Abbinamenti evidenziati con punteggio da 14 a 16** — giocatori_griglia_portieri_2026_2027_atlanta, giocatori_griglia_portieri_2026_2027_sassuolo, giocatori_griglia_portieri_2026_2027_frosinone, giocatori_griglia_portieri_2026_2027_genoa, giocatori_griglia_portieri_2026_2027_torino, giocatori_griglia_portieri_2026_2027_lecce, giocatori_griglia_portieri_2026_2027_milan, giocatori_griglia_portieri_2026_2027_lazio, giocatori_griglia_portieri_2026_2027_napoli [EXTRACTED 1.00]
- **Player Profile Analytics** — grafica_screenshot_2026_08_27_134454_harry_kane_profile, grafica_screenshot_2026_08_27_134454_overview_statistics, grafica_screenshot_2026_08_27_134454_recovery_indicator, grafica_screenshot_2026_08_27_134454_performance_radar_chart, grafica_screenshot_2026_08_27_134454_player_market_value [EXTRACTED 1.00]
- **GoalRush Team Management Workspace** — grafica_screenshot_2026_08_27_134511_team_summary, grafica_screenshot_2026_08_27_134511_player_roster_grid, grafica_screenshot_2026_08_27_134511_selected_player_detail, grafica_screenshot_2026_08_27_134511_player_statistics, grafica_screenshot_2026_08_27_134511_cost_chart [INFERRED 0.85]
- **Marcus Rashford Profile Analysis** — grafica_screenshot_2026_08_27_134522_player_summary_card, grafica_screenshot_2026_08_27_134522_performance_chart, grafica_screenshot_2026_08_27_134522_price_chart, grafica_screenshot_2026_08_27_134522_player_statistics [EXTRACTED 1.00]
- **Player Browsing and Inspection Flow** — grafica_screenshot_2026_08_27_134537_position_filters, grafica_screenshot_2026_08_27_134537_player_list, grafica_screenshot_2026_08_27_134537_selected_player_detail [INFERRED 0.85]
- **Player Card Information and Actions** — grafica_screenshot_2026_08_27_134549_fixture_difficulty_tags, grafica_screenshot_2026_08_27_134549_player_metrics, grafica_screenshot_2026_08_27_134549_contextual_player_actions, grafica_screenshot_2026_08_27_134549_player_status_controls [EXTRACTED 1.00]

## Communities (123 total, 22 thin omitted)

### Community 0 - "Dashboard Data Access Py"
Cohesion: 0.04
Nodes (74): get_match_review_queue(), Uncertain entity matches (spec section 5): a fuzzy match below 95% similarity…, clear_quotations_for_source_and_date(), finish_scraping_run(), get_all_latest_fcp_metrics(), get_all_match_confidences(), get_all_player_notes(), get_all_player_set_pieces() (+66 more)

### Community 1 - "Dashboard Data Access Py"
Cohesion: 0.07
Nodes (67): get_ideal_squad(), get_roster_with_profile(), get_squad_suggestions(), Every owned player (repository.get_roster), enriched with the same profile…, Rosa Ideale Realistica (spec sez. 26): per ogni ruolo con slot ancora liberi, i…, Rosa Ideale (spec sez. 25): i migliori giocatori per ruolo per Fantasy Value,…, get_connection(), add_opponent_pick() (+59 more)

### Community 2 - "Dashboard Data Access Py"
Cohesion: 0.07
Nodes (52): _attach_fcp_metrics(), _attach_tactical_profile_inputs(), _build_player_rows(), _compute_league_inflation(), _compute_ranked_role(), _enrich_role_rows(), evaluate_player_purchase(), get_auction_intelligence() (+44 more)

### Community 3 - "Pipeline Run Photos Transfermarkt"
Cohesion: 0.07
Nodes (44): main(), _players_needing_photos(), Top TOP_FRACTION of all players by current consensus price, still missing a…, run(), Response, build_session(), get(), Session with the shared User-Agent/headers and retry/backoff applied to every… (+36 more)

### Community 4 - "Pipeline Run Scraping Py"
Cohesion: 0.09
Nodes (33): NewPlayerSurgeError, Raised when a run creates more new players than NEW_PLAYER_SURGE_RATIO of the…, PlayerRecord, FailingScraper, FakeScraperA, FakeScraperB, FakeScraperInvalidTeam, FakeScraperMantraSource (+25 more)

### Community 5 - "Dashboard Data Access Py"
Cohesion: 0.08
Nodes (46): get_decision_center(), Decision Center (spec impossibile-analisi-avanzata.md sez. 8): per ogni ruolo,…, compute_all_opponent_models(), compute_auction_timing(), compute_dynamic_max_bid(), compute_expected_auction_price(), compute_max_theoretical_bid(), compute_opponent_budget_model() (+38 more)

### Community 6 - "Config Py"
Cohesion: 0.08
Nodes (38): Configurazione di lega centralizzata (TASK-019/A4): un solo posto per i…, _consensus_role_classic(), Weighted-majority vote across sources instead of "whichever record happened to…, _anchors_by_player(), Riconosce a quale stagione appartengono le statistiche di una quotazione. Il…, Riempie `quotations.stats_season` dove è NULL, per uno scrape_date o per tutto…, player_id -> [(season, appearances, avg_rating)], solo stagioni con almeno le…, (season, basis) per una singola riga, o (None, None) se resta ignota. Pura di… (+30 more)

### Community 7 - "Ranking Percentile Py"
Cohesion: 0.10
Nodes (36): percentile_rank(), Single percentile-rank implementation, used everywhere a player is compared…, 0-100, mid-rank: the single best value in the population always scores exactly…, compute_role_comparison(), Compares one player's core Fantacalcio metrics against the rest of his role…, classify_role(), Classifies players within one role's already-ranked list (rank_players output)…, rows: get_ranked_role's output for one role (already merged, scored, with… (+28 more)

### Community 8 - "Dashboard Components Py"
Cohesion: 0.10
Nodes (41): goalkeeper_team_rows(), _looks_like_crest(), _photo_data_uri(), Resolve a photo by filename against the repo's data/photos dir. Old rows may…, Spezza l'elenco squadre nelle righe della griglia. Funzione a sé, e non un…, _base_player_row(), DA6/TASK-029: a price converted from the listino (no real-auction source for…, DA6/TASK-029: presenze discordi tra le fonti (TASK-011) devono essere… (+33 more)

### Community 9 - "Db Repository Py"
Cohesion: 0.11
Nodes (37): get_pipeline_job_runs(), job -> {last_started_at, last_success_at, last_status, last_detail}. Letta da…, Registra l'esito di un job. success_at va passato solo quando lo status è di…, record_pipeline_job_run(), Namespace, is_due(), Job, main() (+29 more)

### Community 10 - "Consensus Engine Py"
Cohesion: 0.10
Nodes (31): _merge_player_rows(), find_player_by_name(), search_and_sort(), P1-001/TASK-010: a single wild outlier must not dominate the agreement score…, A single player can never actually cost more than the entire auction budget…, One real-auction reading can be a fluke (e.g. a single early-season sample) —…, test_find_player_by_name_case_insensitive(), test_find_player_by_name_returns_none_when_missing() (+23 more)

### Community 11 - "Ranking Ideal Squad Py"
Cohesion: 0.14
Nodes (29): build_ideal_squad(), compare_starters_to_lp(), compute_ideal_score(), _form_factor(), Motore della Rosa Ideale: costruisce la formazione ottimale combinando i…, Costruisce la rosa ideale (titolari + panchina). Args: players_by_role:…, 0.0-1.0 in base alle presenze. None = 0.5, stesso default neutro usato da…, Moltiplicatore 0.5-1.3 basato sulla media fantavoto delle ultime partite. Se… (+21 more)

### Community 12 - "Project Community"
Cohesion: 0.16
Nodes (20): ABC, Unico punto di ingresso della pipeline schedulata. Fino al 31/08/2026 questo…, I 6 scraper delle quotazioni: l'unica cosa che lo scheduler faceva prima del…, _run_quotations(), BaseScraper, FantacalcioItScraper, FantacalcioOnlineScraper, FantaCalciopediaScraper (+12 more)

### Community 13 - "Consensus Engine Py"
Cohesion: 0.07
Nodes (30): compute_listino_to_auction_factor(), Converts an already-canonicalized price_listino (0-40 scale) into auction-…, TASK-013: consensus/engine.py is the actual home of the multi-source consensus…, A near-zero count against a completed-season count is a season mismatch, not a…, The disagreement rule must not swallow the ordinary case: sources within the…, An absent factor must leave prices exactly as they were — a per-role caller…, The season-mismatch guard must stay narrow: 10 vs 20 is two sources differing…, Every source agreeing on ~0 is not a season mismatch — there is no completed-… (+22 more)

### Community 14 - "Dashboard Data Access Py"
Cohesion: 0.11
Nodes (26): get_recent_form(), Forma recente (spec sez. 16): media fantavoto sulle ultime `window` giornate…, init_db(), get_all_latest_team_fixture_difficulty(), get_recent_match_ratings(), insert_team_fixture_difficulty(), main(), run() (+18 more)

### Community 15 - "Consensus Engine Py"
Cohesion: 0.09
Nodes (29): _carries_stats(), compute_league_price_scale(), _compute_price(), _data_confidence(), _detect_outliers(), _price_agreement(), date, Multi-source consensus engine (TASK-013/A2/DB1): turns each player's raw per-… (+21 more)

### Community 16 - "Dashboard Components Py"
Cohesion: 0.12
Nodes (28): _melt_for_chart(), Radar/esagono sintetico del giocatore (Player Quality, Fantasy Value, Value for…, Come static_line_chart ma a dispersione — vedi lì per il perché., Scatter ALG FCP vs prezzo (sottovalutati in alto a sinistra) + istogramma…, 🟢/🟡/🔴 read on value_for_money_percentile (docs/scheda-giocatore.md sez. 26) —…, Come st.line_chart, ma senza lo zoom/pan a rotella del mouse che Streamlit…, Come static_line_chart ma a barre — vedi lì per il perché., _render_advanced_stats() (+20 more)

### Community 17 - "Dashboard Common Py"
Cohesion: 0.12
Nodes (21): get_db_connection(), _inject_card_css(), inject_global_css(), _open_player_detail(), _rank_badge_class(), Fasce (ranking.tiers.classify_role) for one role: Top / Semi-top / Titolari…, Vista dedicata Portieri (giocatori/portieri.md): titolare + riserva per…, Top-3 get a very tenuous gold tint (grafica.md sez. 7); everyone else stays… (+13 more)

### Community 18 - "Db Repository Py"
Cohesion: 0.09
Nodes (27): get_latest_fcp_metrics(), get_latest_player_fantanalisi_valuation(), insert_player_fantanalisi_valuation(), _insert_price(), TASK-006/P1-016: insert_quotation's ON CONFLICT upsert only protects rows…, TASK-009/D9: the seeded aliases must actually resolve to the same code their…, P1-017/TASK-020: same idempotency gap as quotations, for my_roster — a DB…, TASK-007/P0-007: identity_key normalizes casing/punctuation, so a source… (+19 more)

### Community 19 - "Pipeline Run Scraping Py"
Cohesion: 0.14
Nodes (26): TASK-005/S7: the single validation point every PlayerRecord passes through…, _validate_records(), compute_field_coverage(), Source x field coverage matrix (TASK-023/P1-018/S8) and per-record domain…, One entry per (source, field): how many of that source's latest quotations…, Returns (cleaned_record, problems). problems is a list of short human-readable…, validate_record(), Uno scraper nuovo non ancora dichiarato deve essere controllato su tutto:… (+18 more)

### Community 20 - "Ranking Goalkeepers Py"
Cohesion: 0.16
Nodes (26): build_goalkeeper_depth_chart(), _rank_keepers(), Groups dashboard.data_access.get_goalkeeper_pool(conn)'s already-ranked…, (portieri ordinati, criterio usato). Il criterio viene restituito e non tenuto…, rows: dashboard.data_access.get_goalkeeper_pool(conn) output (already filtered…, _priced(), portieri.md §18 nomina Meret come il caso da non sbagliare, e sui dati del…, Due portieri che costano quasi uguale non stanno dicendo niente sulla… (+18 more)

### Community 21 - "Project Community"
Cohesion: 0.17
Nodes (25): parametrize, build_optimal_squad(), Costruisce la rosa che massimizza gli expected_points totali dato il budget.…, _player(), TASK-016: at equal raw score, an unproven player (no appearances signal) must…, The same rule must hold for a pick from the bottom of the pool, which is where…, P0-005/TASK-016: a club whose lineup craters (injuries, a bad run of form)…, P0-005/TASK-016: before normalization, whichever role's raw score happened to… (+17 more)

### Community 22 - "Ranking Scorer Py"
Cohesion: 0.14
Nodes (25): compute_risk(), compute_score(), compute_value_for_money(), 0-100, higher = riskier: driven by how unreliable the appearance record is,…, Fantasy value earned per credit spent. None when there's no price to divide by…, Fantasy Value: how useful this player is for the fantasy game — production…, test_compute_risk_high_when_injured_and_unreliable(), test_compute_risk_higher_with_low_fcp_stability() (+17 more)

### Community 23 - "Db Repository Py"
Cohesion: 0.14
Nodes (24): count_players(), get_player_id_by_identity(), Read-only lookup by the same identity_key upsert_player uses, for callers that…, TASK-006 points 3-4: every write below passes commit=False and the whole run is…, run_pipeline(), FakeScraperTwoPlayers, TASK-005/S7: a scraper reporting a foreign/lower-league team (or a typo'd one)…, P0-003: an implausible fantamedia (99.0) is cleared, not written straight into… (+16 more)

### Community 24 - "Db Repository Py"
Cohesion: 0.16
Nodes (18): get_all_latest_team_strength(), team -> ultima riga scrappata (xg/xga/ppda/scrape_date), una per squadra —…, main(), run(), FantanalisiSquadreScraper, _parse_float(), parse_sections(), Scraper per i dati di squadra (xG/xGA/PPDA, fonte Understat) esposti da… (+10 more)

### Community 25 - "Dashboard Components Py"
Cohesion: 0.13
Nodes (21): Rosa-ideale.md sez. 14-15: coppie di giocatori in rosa che si completano…, Decision Center (dashboard.data_access.get_decision_center): i migliori…, render_correlation_section(), render_decision_center(), format_count(), get_auction_price_trend(), get_ideal_formation(), get_optimal_squad_lp() (+13 more)

### Community 26 - "Dashboard Data Access Py"
Cohesion: 0.16
Nodes (18): get_player_extra(), get_player_anagrafica(), get_transfermarkt_id(), upsert_player_anagrafica(), upsert_transfermarkt_id(), main(), run(), main() (+10 more)

### Community 27 - "Matching Player Matcher Py"
Cohesion: 0.15
Nodes (20): _group_records_with_confidence(), _initials_conflict(), _is_ambiguous(), match_name_to_player(), match_name_to_player_any_team(), Matches a bare (name, team) pair — as scraped from a page that doesn't expose…, Like match_name_to_player, but ignores team entirely — for matching a player…, True when two names share a surname but their abbreviated given-name tokens… (+12 more)

### Community 28 - "Matching Player Matcher Py"
Cohesion: 0.17
Nodes (21): match_records(), match_records_with_confidence(), Same grouping as match_records, but each record keeps the match confidence that…, TASK-030. Una fonte elenca ogni giocatore una volta sola: due righe della…, La regola non deve toccare il caso normale, che è tutto il punto del matching:…, Dopo uno split, il gruppo nuovo deve restare aperto alle altre fonti, o un…, _record(), test_a_third_source_can_still_join_a_group_that_already_split_one() (+13 more)

### Community 29 - "Ranking Goalkeeper Score Py"
Cohesion: 0.17
Nodes (20): _clean_sheet_proxy(), compute_goalkeeper_score(), _goals_conceded_goodness(), _rating_quality(), Goalkeeper-specific Fantasy Value (TASK-025b/P2-020, rosa-ideale.md §4's four-…, 0-1, same 5.0-8.0 band ranking.scorer.compute_player_quality stretches to 0-100…, 0-1: fewer goals conceded per appearance is better. Real DB range for keepers…, 1/(1+team_xga): a team conceding fewer expected goals per match makes a clean… (+12 more)

### Community 30 - "Db Repository Py"
Cohesion: 0.18
Nodes (19): get_latest_player_advanced_stats(), insert_player_advanced_stats(), _already_done_today(), main(), player_id già scritti oggi da questa fonte. UNIQUE(player_id, source,…, Ogni giocatore viene scritto appena la sua pagina è stata letta, non alla fine…, run(), test_player_advanced_stats_get_latest_returns_none_when_missing() (+11 more)

### Community 31 - "Ranking Scorer Py"
Cohesion: 0.12
Nodes (20): _appearances_estimate_from_range(), compute_neutral_tactical_profiles(), compute_price_fantamedia_curves(), estimate_fantamedia(), _median(), rank_players(), {role_classic: median tactical_profile_score} across `rows`, for the two…, {role_classic: [(price, fantamedia), ...] sorted by price} across `rows` with… (+12 more)

### Community 32 - "Fantacalcio Audit 2026 08"
Cohesion: 0.11
Nodes (20): Lazio player identity root cause, Data quality and coverage gaps, Missing decision-critical data, Auction decision and value-for-money system, Cross-source player reconciliation, Goalkeeper depth chart plan, Per-team goalkeeper hierarchy, Ruff lint check (+12 more)

### Community 33 - "Consensus Engine Py"
Cohesion: 0.12
Nodes (19): group_by_player(), player_id -> le sue righe. Vive qui e non in dashboard/data_access.py perché…, get_monitoring_data(), 🔴 the pipeline that owns this table has never written a row (P0-008: the case…, Data-health snapshot for the admin monitoring page: per-source freshness/…, _table_health_status(), _cached_monitoring_data(), cache_data (+11 more)

### Community 34 - "Dashboard Components Py"
Cohesion: 0.19
Nodes (17): Rosa-ideale.md sez. 26 (fasi asta) e sez. 28 (checklist finale)., render_auction_checklist_section(), _appearances_ok(), build_checklist(), current_phase(), _owned(), Auction-progress checklist and phase tracker (giocatori/rosa-ideale.md sez. 26…, budget_summary: ranking.budget.compute_budget_summary(roster) output. The first… (+9 more)

### Community 35 - "Scrapers Fantacalciopedia Py"
Cohesion: 0.18
Nodes (17): _normalize_competition(), parse_detail(), parse_html(), parse_season_stats(), Serie A" -> "serie_a", "BundesLiga (GER)" -> "bundesliga_ger" — a plain slug,…, Season-by-season presenze/gol/assist/media voto/ammonizioni/espulsioni from the…, TASK-008/P0-004: a season played abroad must be told apart from one played in…, test_normalize_competition_slugifies_a_foreign_league_name() (+9 more)

### Community 36 - "Db Connection Py"
Cohesion: 0.22
Nodes (16): _column_exists(), _merge_duplicate_players(), merge_players(), _migrate(), Connection, One-off cleanup (TASK-004c/P0-010): before identity_key included team, a player…, Sposta ogni riga figlia da `dup_id` a `keep_id` e cancella `dup_id`. Estratta…, CREATE TABLE IF NOT EXISTS in schema.sql never adds a column to a table that… (+8 more)

### Community 37 - "Ranking Fantamedia Py"
Cohesion: 0.23
Nodes (16): derive_fantamedia(), Fantamedia ricavata dalle componenti, invece che stimata dal prezzo. Il…, Fantamedia dalla riga di `player_season_stats`, o None se non è calcolabile o…, È il motivo per cui questa funzione esiste: la stima da prezzo dà lo stesso…, Un gol in 2 partite vale +1,5 di fantamedia e descrive l'episodio., 20 gol in 6 partite porterebbe a 16: non è una fantamedia, è un dato sbagliato.…, _season(), test_a_goalkeeper_pays_for_the_goals_he_concedes() (+8 more)

### Community 38 - "Scripts Simulate Auctions Py"
Cohesion: 0.18
Nodes (13): check_lp(), check_run(), load_pool(), main(), _my_role_priority(), _pick_price(), Simula N aste complete contro il pool di giocatori reale, per validare che…, Invarianti + raccolta dati per il report aggregato. Non solleva mai: ogni… (+5 more)

### Community 39 - "Ranking Purchase Advisor Py"
Cohesion: 0.28
Nodes (14): compute_marginal_squad_value(), evaluate_purchase(), Valutazione 'ne vale la pena?' per un giocatore ad un prezzo ipotetico.…, Global Fantasy Value vs Marginal Squad Value (spec impossibile-analisi-…, Args: player: riga giocatore arricchita (score, value_for_money, price_current,…, _player(), test_all_in_recommended_on_last_slot_with_a_top_ranked_player(), test_bargain_when_price_is_well_below_listed_price() (+6 more)

### Community 40 - "Ranking Tactical Profile Py"
Cohesion: 0.23
Nodes (13): compute_tactical_profile_score(), _numeric_avg_from_range(), fantasy_profile_score (giocatori/movimento.md sez. 15/18, giocatori/ rosa-…, 12/15" -> 13.5. Fantacalciopedia's predicted_goals/predicted_assists format…, None for portieri (role_classic == "P") — clean sheets/gol subiti are already…, test_goalkeepers_have_no_tactical_profile_score(), test_goals_and_assists_lift_the_score(), test_missing_role_mantra_falls_back_to_role_classic_baseline() (+5 more)

### Community 41 - "Scripts Diagnose Missing Prices"
Cohesion: 0.19
Nodes (14): find_split_identity(), La riga più vecchia che è quasi certamente la stessa persona, o None. Tre…, La regola che decide "queste due righe sono la stessa persona" è la parte…, È il caso su cui il prototipo fuzzy sbagliava: con due omonimi la regola deve…, Prefisso sui token, non distanza di edit: 'Nkunke' non è 'Nkunku'., Di Gregorio' ⊂ 'Di Gregorio Michele' sì; 'Gregorio Michele' no., La storia sta sulla riga vecchia: si unisce nella più vecchia., test_a_different_team_is_a_different_person() (+6 more)

### Community 42 - "Pipeline Run Fixture Difficulty"
Cohesion: 0.26
Nodes (9): main(), run(), FantanalisiCalendarioScraper, parse_team_scores(), Scraper per la difficoltà di calendario (finestra "prime 5 giornate", scala…, save_fixture_difficulty(), test_parse_team_scores_extracts_team_and_score(), test_parse_team_scores_handles_non_numeric_score() (+1 more)

### Community 43 - "Scrapers Fantacalcio It Py"
Cohesion: 0.23
Nodes (11): fetch_season_prices(), _parse_float(), parse_html(), A malformed price cell (trailing unit, separator the source recently changed,…, 2024/25' -> '2024-25', matching the site's own URL scheme (found by watching…, Same page template as the live quotations page, just an older season (site…, season_to_url_slug(), A badly formatted price cell must degrade to None for that row, not raise and… (+3 more)

### Community 44 - "Scrapers Fantanalisi Py"
Cohesion: 0.22
Nodes (12): _cell_or_none(), _parse_price(), parse_rows(), Aste live': prezzo medio osservato nelle aste reali del formato utente ('numero…, Testo grezzo della cella, o None se assente/vuota/placeholder ('-', '—') —…, test_parse_rows_captures_detail_url(), test_parse_rows_captures_fantanalisi_valuations(), test_parse_rows_detail_url_is_none_when_row_has_no_link() (+4 more)

### Community 45 - "Scrapers Fantanalisi Giocatore Py"
Cohesion: 0.21
Nodes (10): FantanalisiGiocatoreScraper, parse_percentile_titles(), Scraper per i percentili per-90 (xG/xA/tiri/rifiniture/coinvolgimento/ minuti)…, Come fetch_many, ma restituisce (detail_url, percentili) uno alla volta invece…, detail_urls: PlayerRecord.detail_url values (relative paths like…, test_parse_percentile_titles_extracts_all_metrics(), test_parse_percentile_titles_handles_empty_list(), test_parse_percentile_titles_ignores_unrelated_titles() (+2 more)

### Community 46 - "Db Repository Py"
Cohesion: 0.19
Nodes (13): get_all_latest_player_season_stats(), get_player_season_stats(), player_id -> most recent eligible season's row within MAX_SEASON_AGE of…, Most recent season first. A player can in principle have rows from more than…, seasons: scrapers.fantacalciopedia.parse_season_stats output for this player.…, upsert_player_season_stats(), TASK-008/P0-004 point 3: a foreign-league season, or one older than…, TASK-008/P0-004: a row with no competition label at all (every row written… (+5 more)

### Community 47 - "Pipeline Run Match Ratings"
Cohesion: 0.28
Nodes (10): main(), Stores the latest played giornata's per-match ratings. Running this weekly…, run(), fetch_voti(), _parse_grade(), parse_html(), Parses fantacalcio.it's match-by-match ratings page. Only the "Redazione…, test_parse_grade_discards_out_of_range_placeholder_values() (+2 more)

### Community 48 - "Ranking Lp Optimizer Py"
Cohesion: 0.17
Nodes (7): _appearances_reliability(), _expected_points_by_role(), _infeasible_reason(), Solver a programmazione lineare per la rosa ottimale (25 giocatori, 3-8-8-6,…, Best-effort diagnosis for why the solver couldn't find a feasible squad…, {player_id: score above that role's own average} — the LP's objective…, TASK-019/A4: config.py is the single source of truth for league rules — these…

### Community 49 - "Consensus Engine Py"
Cohesion: 0.18
Nodes (11): compute_source_scale_factors(), Per-source multiplier that rescales that source's raw price_current onto its…, The property the max anchor buys, stated directly: no rescaled reading can…, Regression for the clamp collapse (AUDIT_2026-08-30_CORREZIONI §5): with the…, test_compute_source_scale_factors_importable_and_works_standalone(), test_max_anchored_scale_factors_keep_the_two_priciest_players_distinct(), test_scale_factors_never_push_a_source_reading_above_the_ceiling(), P0-001/TASK-001: each source's raw price_current lives on its own scale… (+3 more)

### Community 50 - "Dashboard Data Access Py"
Cohesion: 0.33
Nodes (10): get_price_history_by_date(), {scrape_date: {source: price_current}}, one point per source per day (later…, get_price_history(), Full time series of every quotation ever recorded for this player, one row per…, _record(), test_historical_rows_excluded_from_live_consensus(), test_run_falls_back_to_any_team_match_for_transferred_player(), test_run_imports_a_season_and_matches_by_team() (+2 more)

### Community 51 - "Ranking Budget Py"
Cohesion: 0.35
Nodes (9): compute_budget_summary(), compute_role_budget_plan(), Per-role budget targets from ROLE_BUDGET_PCT, live-adjusted for what's already…, TASK-018/P1-012: with a full 500-credit budget and 25 empty slots, "remaining"…, test_compute_budget_summary_spendable_is_never_negative(), test_compute_budget_summary_spendable_reserves_a_credit_per_empty_slot(), test_compute_budget_summary_tracks_spent_and_slots(), test_compute_role_budget_plan_flags_over_budget_role() (+1 more)

### Community 52 - "Ranking Correlation Py"
Cohesion: 0.38
Nodes (9): find_correlations(), Flags positive and negative player correlations within the owned roster…, roster_rows: dashboard.data_access.get_roster_with_profile(conn) output, or any…, _row(), test_flags_negative_correlation_same_contested_role_same_team(), test_flags_positive_correlation_assistman_and_goleador_same_team(), test_ignores_portieri(), test_no_negative_correlation_for_non_contested_role_mantra() (+1 more)

### Community 53 - "Ranking Scorer Py"
Cohesion: 0.18
Nodes (11): compute_player_quality(), enrich_scores(), 0-100: raw footballing quality (avg_rating-driven), independent of fantasy…, Attach the full separated-score set (player_quality, risk, value_for_money,…, test_enrich_row_prefers_a_real_fantamedia_over_the_derived_one(), test_enrich_row_prefers_the_derived_one_over_the_price_estimate(), test_enrich_row_still_falls_back_to_the_price_estimate(), test_compute_player_quality_independent_of_price() (+3 more)

### Community 54 - "Fantacalcio Audit 2026 08"
Cohesion: 0.20
Nodes (10): LP starter probability weight fix, Auction price saturation fix, Ranking cache invalidation fix, Post-audit backlog, Player card technical and UI specification, Scraper and dashboard implementation plan, CI test matrix, CodeQL Python analysis (+2 more)

### Community 55 - "Dashboard Team Info Py"
Cohesion: 0.33
Nodes (8): get_role_fit(), get_team_info(), Static reference info about Serie A teams: city, stadium, rivals, playing…, Compito del giocatore nello stile della sua squadra, con pro e contro di quello…, test_cagliari_has_no_fabricated_rival(), test_get_role_fit_returns_none_for_unknown_role(), test_get_role_fit_returns_none_for_unknown_team(), test_get_role_fit_returns_pro_and_contro_for_known_style_keyword()

### Community 56 - "Giocatori Griglia Portieri 2026"
Cohesion: 0.27
Nodes (10): Atalanta, Frosinone, Genoa, Inter, Juventus, Lecce, Milan, Parma (+2 more)

### Community 57 - "Dashboard Components Py"
Cohesion: 0.22
Nodes (9): _cached_auction_intelligence(), cache_data, get_auction_intelligence ricalcola il consensus prezzo su ~700 giocatori (per…, Auction Intelligence Engine (spec sez. 84-99): la versione 'cockpit' compatta…, Sezione 'ne vale la pena?': prezzo ipotetico -> giudizio d'acquisto, con…, render_auction_intelligence(), render_purchase_evaluator(), get_purchase_history() (+1 more)

### Community 58 - "Project Community"
Cohesion: 0.39
Nodes (7): Exception, main(), run(), FcpDetail, fetch_detail(), test_run_saves_season_stats_from_the_same_detail_fetch(), test_run_skips_player_when_detail_fetch_fails()

### Community 59 - "Grafica Screenshot 2026 08"
Cohesion: 0.25
Nodes (9): Harry Kane Profile, Mobile Football Player Dashboard, Overview Statistics, Performance Radar Chart, Player Market Value, Player Summary Card, Recovery Indicator, Team and National Performance Comparison (+1 more)

### Community 60 - "Grafica Screenshot 2026 08"
Cohesion: 0.25
Nodes (9): Add to My Team Action, Favorite Player Action, Marcus Rashford Player Profile, My Team Dashboard, Performance by Fixture Chart, Performance Scope Filter, Player Statistics Panel, Player Summary Card (+1 more)

### Community 61 - "Fantacalcio Impossibile Analisi Avanzata"
Cohesion: 0.22
Nodes (9): Decision Center, Multi-Objective Optimizer, Price Engine, Streamlit-Independent Decision Engine, Fantasy Football Decision Engine, Fantasy Football Intelligence Dashboard, No Scraping in Dashboard, Repository Pattern (+1 more)

### Community 62 - "Ranking Price Engine Py"
Cohesion: 0.36
Nodes (7): compute_value_index(), Value Index (TASK-015/P1-004): how good a deal a player is relative to his…, None when either input is missing or the median is zero — no population to…, test_value_index_100_at_exactly_the_role_median(), test_value_index_above_100_when_more_efficient_than_median(), test_value_index_below_100_when_less_efficient_than_median(), test_value_index_none_without_inputs()

### Community 63 - "Dashboard Data Access Py"
Cohesion: 0.29
Nodes (4): is_current_serie_a_team(), Serie A 2026/27 roster — USER-VERIFIED ground truth. Venezia/Frosinone/Monza…, test_is_current_serie_a_team_follows_verified_roster(), test_schema_teams_table_matches_verified_roster()

### Community 64 - "Ranking Scorer Py"
Cohesion: 0.25
Nodes (8): compute_decision_score(), Combines fantasy value, price efficiency and risk into one number for ranking…, P1-001: monotonicity over the full confidence range, not just a couple of…, test_compute_decision_score_is_never_improved_by_lower_confidence(), TASK-010/P1-001: uncertainty must increase effective risk, not discount it.…, test_compute_decision_score_confidence_never_exceeds_full_confidence_baseline(), test_compute_decision_score_lower_confidence_never_improves_the_score(), test_compute_decision_score_penalizes_risk()

### Community 65 - "Scrapers Pianetafanta Py"
Cohesion: 0.32
Nodes (6): _dismiss_cookie_banner(), _parse_price(), parse_team_rows(), row_texts: list of [R, R1, GIOCATORE, QI, QA, +/-] cell-text rows for a single…, test_parse_team_rows_extracts_players(), test_parse_team_rows_skips_incomplete_rows()

### Community 66 - "Db Repository Py"
Cohesion: 0.48
Nodes (5): get_player_set_pieces(), main(), run(), test_run_matches_by_team_and_fuzzy_name(), test_run_replaces_previous_snapshot_from_same_source()

### Community 67 - "Giocatori Movimento Md"
Cohesion: 0.29
Nodes (7): Dynamic Tactical Profile, Real Role over Official Role, Role-Specific Player Scoring, Ideal Squad Construction, Squad Correlations, Value per Credit, PuLP

### Community 68 - "Grafica Screenshot 2026 08"
Cohesion: 0.33
Nodes (7): Player Cost Chart, GoalRush My Team Screen, Player Roster Grid, Player Statistics, Position Filters, Selected Player Detail, Team Summary

### Community 69 - "Grafica Screenshot 2026 08"
Cohesion: 0.33
Nodes (7): CoachPro Players Interface, Federico Bernardeschi, Player Performance Attributes, Player List, Player Position Filters, Selected Player Detail, Squad Navigation

### Community 70 - "Scrapers Fantacalcio Online Py"
Cohesion: 0.48
Nodes (4): _parse_float(), parse_html(), _parse_int(), test_parse_html_extracts_players()

### Community 71 - "Dashboard Data Access Py"
Cohesion: 0.33
Nodes (6): _cached_data_freshness_summary(), get_data_freshness_summary(), cache_data, The actual computation behind get_data_freshness_summary — split out so it's…, Sez. DA5/TASK-028: "dati al 26/08, 6 fonti su 6, 407 giocatori valutati, 396…, test_get_data_freshness_summary_none_reference_date_when_never_scraped()

### Community 72 - "Specs 2026 08 26"
Cohesion: 0.33
Nodes (6): Decision Center, Price Engine, Replacement Advantage, Scarcity Score, Team Strength Metrics, Auction Price Estimates by League Format

### Community 73 - "Grafica Screenshot 2026 08"
Cohesion: 0.33
Nodes (6): Contextual Player Actions, Fantasy Football Player Card Grid, Fixture Difficulty Tags, Player Card, Player Metrics, Player Status Controls

### Community 74 - "Fantacalcio Backlog 2026 08"
Cohesion: 0.40
Nodes (5): Incomplete pipeline scheduling, Multi-source normalization and refresh, Scraper to matching to ranking to dashboard architecture, Multi-source scraping and ranking pipeline, Isolated scheduled jobs

### Community 75 - "Specs 2026 08 25"
Cohesion: 0.40
Nodes (5): Conservative Player-ID Matching, Fantacalciopedia Player Detail Metrics, Optional Risk Inputs, Investment Stability and Injury Resistance, Donyell Malen Injury History

### Community 76 - "Giocatori Griglia Portieri 2026"
Cohesion: 0.40
Nodes (5): Coppie sfavorevoli evidenziate: Atalanta-Sassuolo, Frosinone-Genoa, Genoa-Torino e Lecce-Sassuolo 14; Milan-Sassuolo 15; Lazio-Napoli 16, Coppie favorevoli evidenziate: Napoli-Roma 3; Inter-Sassuolo, Lecce-Parma e Parma-Sassuolo 4; Atalanta-Frosinone e Genoa-Juventus 5, Coppie ottimali con punteggio 0: Inter-Milan, Juventus-Torino, Lazio-Roma, Matrice abbinamenti portieri 2026-2027, Ottimizzazione delle coppie di portieri

### Community 77 - "Fantacalcio Impossibile Mlops Governance"
Cohesion: 0.40
Nodes (5): Data Quality Layer, Leakage-Free Backtesting, Model Governance, Entity Matching, Multi-Source Consensus

### Community 78 - "Tests Test Data Access"
Cohesion: 0.40
Nodes (5): _rankable_midfielder(), TASK-015/P1-004: value_index replaces the old Price Engine's…, Auction Intelligence covers the full live-auction sheet: fair price, inflation,…, test_get_auction_intelligence_maps_every_market_signal(), test_get_value_index_returns_a_role_relative_efficiency_ratio()

### Community 79 - "Plans 2026 08 27"
Cohesion: 0.50
Nodes (4): Fantanalisi Advanced Player Statistics, Fixture Difficulty, Player External Data Integration, Transfermarkt Biographical Data

### Community 80 - "Specs 2026 08 22"
Cohesion: 0.50
Nodes (4): Fantacalcio Ranking Engine, Modular Scraping Architecture, Cross-Source Player Matching, Multipage Streamlit Dashboard

### Community 81 - "Fixtures Fantacalciopedia Detail Sample"
Cohesion: 0.50
Nodes (4): Fantacalciopedia Algorithm Score, Multi-Season Player Statistics, Player Skill Tags, Predicted Appearances Goals and Assists

### Community 82 - "Grafica Grafica Md"
Cohesion: 0.50
Nodes (4): Player Card Design System, Responsive Player Card Grid, Player Card Visual Hierarchy, Streamlit

### Community 83 - "Fantacalcio Agents Md"
Cohesion: 0.67
Nodes (3): AI agent operating rules, Duplicated AI rule files, Canonical AGENTS.md reference

### Community 84 - "Fantacalcio Audit 2026 08"
Cohesion: 0.67
Nodes (3): Verified corrections to the August 30 audit, Data and pipeline audit, Player selection on healthy data

### Community 85 - "Plans 2026 08 27"
Cohesion: 0.67
Nodes (3): Auction Checklist and Phase Tracker, No New Scraper or Schema, Player Correlations

### Community 86 - "Plans 2026 08 27"
Cohesion: 0.67
Nodes (3): Player Detail UI Polish, Role Percentile Comparison, Rules-Based Player Verdict

### Community 87 - "Plans 2026 08 27"
Cohesion: 0.67
Nodes (3): Bounded Fantasy Value Adjustment, Role Mantra, Tactical Profile Score

### Community 88 - "Fixtures Transfermarkt Search Sample"
Cohesion: 0.67
Nodes (3): Donyell Malen, Transfermarkt Search Result, Beautiful Soup 4

### Community 89 - "Giocatori Griglia Portieri 2026"
Cohesion: 1.00
Nodes (3): Lazio, Napoli, Roma

### Community 90 - "Giocatori Portieri Md"
Cohesion: 0.67
Nodes (3): Goalkeeper Hierarchy Resolution, Real Roster at Scrape Time, Transfer-Aware Goalkeeper Updates

### Community 91 - "Fantacalcio Impossibile Asta Live"
Cohesion: 0.67
Nodes (3): Auction Pressure, Portfolio Risk, Real-Time Auction State

## Knowledge Gaps
- **97 isolated node(s):** `CodeQL Python analysis`, `Ruff lint check`, `Conda build, Flake8 and pytest workflow`, `Verified corrections to the August 30 audit`, `Auction price saturation fix` (+92 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **22 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_connection()` connect `Dashboard Data Access Py` to `Dashboard Data Access Py`, `Dashboard Data Access Py`, `Pipeline Run Photos Transfermarkt`, `Pipeline Run Scraping Py`, `Dashboard Data Access Py`, `Config Py`, `Dashboard Components Py`, `Db Repository Py`, `Consensus Engine Py`, `Project Community`, `Dashboard Data Access Py`, `Dashboard Common Py`, `Db Repository Py`, `Pipeline Run Scraping Py`, `Db Repository Py`, `Db Repository Py`, `Dashboard Components Py`, `Dashboard Data Access Py`, `Matching Player Matcher Py`, `Db Repository Py`, `Consensus Engine Py`, `Dashboard Components Py`, `Db Connection Py`, `Scripts Simulate Auctions Py`, `Scripts Diagnose Missing Prices`, `Pipeline Run Fixture Difficulty`, `Db Repository Py`, `Pipeline Run Match Ratings`, `Dashboard Data Access Py`, `Project Community`, `Db Repository Py`, `Dashboard Data Access Py`, `Tests Test Data Access`, `Project Community`?**
  _High betweenness centrality (0.120) - this node is a cross-community bridge._
- **Why does `init_db()` connect `Dashboard Data Access Py` to `Dashboard Data Access Py`, `Dashboard Data Access Py`, `Dashboard Data Access Py`, `Pipeline Run Photos Transfermarkt`, `Pipeline Run Scraping Py`, `Dashboard Data Access Py`, `Config Py`, `Dashboard Components Py`, `Db Repository Py`, `Consensus Engine Py`, `Project Community`, `Dashboard Common Py`, `Db Repository Py`, `Pipeline Run Scraping Py`, `Db Repository Py`, `Db Repository Py`, `Dashboard Components Py`, `Dashboard Data Access Py`, `Matching Player Matcher Py`, `Db Repository Py`, `Consensus Engine Py`, `Dashboard Components Py`, `Db Connection Py`, `Scripts Diagnose Missing Prices`, `Pipeline Run Fixture Difficulty`, `Db Repository Py`, `Pipeline Run Match Ratings`, `Dashboard Data Access Py`, `Project Community`, `Dashboard Data Access Py`, `Db Repository Py`, `Dashboard Data Access Py`, `Tests Test Data Access`?**
  _High betweenness centrality (0.084) - this node is a cross-community bridge._
- **Why does `PlayerRecord` connect `Pipeline Run Scraping Py` to `Scrapers Pianetafanta Py`, `Scrapers Fantacalciopedia Py`, `Scrapers Fantacalcio Online Py`, `Scrapers Fantacalcio It Py`, `Project Community`, `Scrapers Fantanalisi Py`, `Dashboard Data Access Py`, `Dashboard Data Access Py`, `Pipeline Run Scraping Py`, `Db Repository Py`, `Project Community`, `Matching Player Matcher Py`, `Db Repository Py`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **Are the 23 inferred relationships involving `PlayerRecord` (e.g. with `FantacalcioItScraper` and `FantacalcioOnlineScraper`) actually correct?**
  _`PlayerRecord` has 23 INFERRED edges - model-reasoned connections that need verification._
- **What connects `CodeQL Python analysis`, `Ruff lint check`, `Conda build, Flake8 and pytest workflow` to the rest of the system?**
  _97 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Dashboard Data Access Py` be split into smaller, more focused modules?**
  _Cohesion score 0.044684684684684686 - nodes in this community are weakly interconnected._
- **Should `Dashboard Data Access Py` be split into smaller, more focused modules?**
  _Cohesion score 0.07236544549977386 - nodes in this community are weakly interconnected._