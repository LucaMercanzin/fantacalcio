from dashboard.team_info import get_role_fit, get_team_info


def test_cagliari_has_no_fabricated_rival():
    info = get_team_info("Cagliari")
    assert info["rivali"] == []


def test_get_role_fit_returns_pro_and_contro_for_known_style_keyword():
    # Napoli's style mentions "palleggio veloce" and "ampiezza" (see TEAM_INFO)
    fit = get_role_fit("Napoli", "A")

    assert fit is not None
    assert "compito" in fit
    assert fit["pro"]
    assert fit["contro"]


def test_get_role_fit_returns_none_for_unknown_team():
    assert get_role_fit("Nonexistent FC", "A") is None


def test_get_role_fit_returns_none_for_unknown_role():
    assert get_role_fit("Napoli", "Z") is None
