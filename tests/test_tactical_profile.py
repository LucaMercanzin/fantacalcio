from ranking.tactical_profile import compute_tactical_profile_score


def test_goalkeepers_have_no_tactical_profile_score():
    row = {"role_classic": "P", "role_mantra": "POR"}
    assert compute_tactical_profile_score(row) is None


def test_quinto_offensivo_scores_higher_than_centrale_puro():
    quinto = {"role_classic": "D", "role_mantra": "E"}
    centrale = {"role_classic": "D", "role_mantra": "DC"}
    assert compute_tactical_profile_score(quinto) > compute_tactical_profile_score(centrale)


def test_trequartista_scores_higher_than_mediano():
    trequartista = {"role_classic": "C", "role_mantra": "T"}
    mediano = {"role_classic": "C", "role_mantra": "M"}
    assert compute_tactical_profile_score(trequartista) > compute_tactical_profile_score(mediano)


def test_goals_and_assists_lift_the_score():
    plain = {"role_classic": "C", "role_mantra": "C"}
    productive = {
        "role_classic": "C", "role_mantra": "C",
        "season_goals_scored": 8, "season_assists": 7,
    }
    assert compute_tactical_profile_score(productive) > compute_tactical_profile_score(plain)


def test_penalty_taker_gets_a_set_piece_bonus():
    base = {"role_classic": "D", "role_mantra": "DC"}
    rigorista = {
        "role_classic": "D", "role_mantra": "DC",
        "set_pieces": [{"category": "rigori", "rank": 1}],
    }
    assert compute_tactical_profile_score(rigorista) > compute_tactical_profile_score(base)


def test_missing_role_mantra_falls_back_to_role_classic_baseline():
    row = {"role_classic": "D", "role_mantra": None}
    score = compute_tactical_profile_score(row)
    assert score is not None and 0 <= score <= 100


def test_predicted_goals_used_when_no_season_stats_yet():
    # New signing (movimento.md sez. 22): no player_season_stats row yet,
    # falls back to Fantacalciopedia's "gol previsti" range.
    row = {
        "role_classic": "A", "role_mantra": "PC",
        "predicted_goals": "12/15", "predicted_assists": "3/5",
    }
    no_data = {"role_classic": "A", "role_mantra": "PC"}
    assert compute_tactical_profile_score(row) > compute_tactical_profile_score(no_data)


def test_score_is_clipped_to_0_100():
    row = {
        "role_classic": "C", "role_mantra": "T",
        "season_goals_scored": 40, "season_assists": 40,
        "set_pieces": [{"category": "rigori", "rank": 1}, {"category": "punizioni", "rank": 1}],
    }
    assert compute_tactical_profile_score(row) == 100.0
