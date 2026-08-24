from scrapers.fantacalcio_voti import parse_html

SAMPLE_HTML = """
<html><head><title>Voti Fantacalcio Serie A 1 giornata - stagione 2026/27</title></head>
<body>
<ul class="teams my-3">
  <li id="team-1" class="team-table">
    <header><div class="match-score"><span class="current">Atalanta</span></div></header>
    <div class="team-table-body">
      <table class="grades-table">
        <thead><tr><th><div class="team-info">
          <a class="team-name team-link" href="#">Atalanta</a>
        </div></th></tr></thead>
        <tbody>
          <tr>
            <td>
              <div class="player-item cell">
                <span class="role" data-value="p"></span>
                <a class="player-name player-link" href="https://www.fantacalcio.it/serie-a/squadre/atalanta/carnesecchi/4431">
                  <span>Carnesecchi</span>
                </a>
              </div>
            </td>
            <td>
              <div class="group">
                <div class="pill">
                  <span class="player-grade" data-value="6,5"></span>
                  <span class="player-fanta-grade" data-value="6,5"></span>
                </div>
                <div class="pill">
                  <span class="player-grade" data-value="6"></span>
                  <span class="player-fanta-grade" data-value="6"></span>
                </div>
              </div>
            </td>
          </tr>
          <tr>
            <td>
              <div class="player-item cell">
                <span class="role" data-value="a"></span>
                <a class="player-name player-link" href="https://www.fantacalcio.it/serie-a/squadre/atalanta/scamacca/2137">
                  <span>Scamacca</span>
                </a>
              </div>
            </td>
            <td>
              <div class="group">
                <div class="pill">
                  <span class="player-grade " data-value=""></span>
                  <span class="player-fanta-grade" data-value=""></span>
                </div>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </li>
</ul>
</body></html>
"""


def test_parse_html_extracts_giornata_season_and_entries():
    result = parse_html(SAMPLE_HTML)

    assert result["giornata"] == 1
    assert result["season"] == "2026/27"
    assert result["entries"] == [
        {"team": "Atalanta", "player_name": "Carnesecchi", "fantacalcio_player_id": 4431,
         "role": "P", "voto": 6.5, "fantavoto": 6.5},
        {"team": "Atalanta", "player_name": "Scamacca", "fantacalcio_player_id": 2137,
         "role": "A", "voto": None, "fantavoto": None},
    ]


def test_parse_grade_discards_out_of_range_placeholder_values():
    from scrapers.fantacalcio_voti import _parse_grade

    assert _parse_grade("55") is None
    assert _parse_grade("56") is None
    assert _parse_grade("6,5") == 6.5
    assert _parse_grade("7") == 7.0
    assert _parse_grade("") is None


def test_parse_html_handles_unrecognized_title():
    result = parse_html("<html><head><title>Something else</title></head><body></body></html>")

    assert result["giornata"] is None
    assert result["season"] is None
    assert result["entries"] == []
