from scrapers.fantacalcio_rigoristi import parse_html

SAMPLE_HTML = """
<div id="team-1" class="card team-card">
    <header class="team-info">
        <span class="team-name">Atalanta</span>
    </header>
    <div class="row row-responsive">
        <div class="col">
            <header class="primary">Rigori</header>
            <ol class="pill-list ranked dark">
                <li>
                    <a class="player-name player-link"
                       href="https://www.fantacalcio.it/serie-a/squadre/atalanta/scamacca/2137">
                        <span>Scamacca</span>
                    </a>
                </li>
                <li>
                    <a class="player-name player-link"
                       href="https://www.fantacalcio.it/serie-a/squadre/atalanta/krstovic/6435">
                        <span>Krstovic</span>
                    </a>
                </li>
            </ol>
        </div>
        <div class="col">
            <header>Calci piazzati</header>
            <ol class="pill-list ranked dark">
                <li data-id="5995">
                    <a class="player-name player-link"
                       href="https://www.fantacalcio.it/serie-a/squadre/atalanta/de-ketelaere/5995">
                        <span>De Ketelaere</span>
                    </a>
                </li>
            </ol>
        </div>
    </div>
</div>
"""


def test_parse_html_extracts_rigori_and_punizioni_with_rank_and_id():
    entries = parse_html(SAMPLE_HTML)

    assert entries == [
        {"team": "Atalanta", "category": "rigori", "rank": 1,
         "player_name": "Scamacca", "fantacalcio_player_id": 2137},
        {"team": "Atalanta", "category": "rigori", "rank": 2,
         "player_name": "Krstovic", "fantacalcio_player_id": 6435},
        {"team": "Atalanta", "category": "punizioni", "rank": 1,
         "player_name": "De Ketelaere", "fantacalcio_player_id": 5995},
    ]


def test_parse_html_returns_empty_list_for_no_teams():
    assert parse_html("<html><body>nothing here</body></html>") == []
