CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL,
    team TEXT NOT NULL,
    role_classic TEXT NOT NULL,
    role_mantra TEXT,
    photo_path TEXT,
    -- normalize_name(canonical_name) || '|' || normalize_team(team): the
    -- real identity a player is looked up by (repository.upsert_player).
    -- canonical_name/team are just the display strings a source happened to
    -- report; if the source that provided the longest name/team goes
    -- missing on a later run, they can change without creating a new player
    -- row (TASK-007/P0-007).
    identity_key TEXT,
    UNIQUE(canonical_name, team)
);
-- Retrofitted via a plain ALTER TABLE on pre-existing DBs (see _migrate() in
-- db/connection.py), so declared as a separate index rather than an inline
-- UNIQUE column constraint — same reasoning as idx_quotations_unique.
CREATE UNIQUE INDEX IF NOT EXISTS idx_players_identity_key ON players(identity_key);

CREATE TABLE IF NOT EXISTS quotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(id),
    source TEXT NOT NULL,
    scrape_date TEXT NOT NULL,
    price_current REAL,
    price_initial REAL,
    status TEXT,
    -- 0 is how some sources spell "no fantamedia yet" (P0-003), not a real
    -- average — it must arrive here as NULL (see scrapers/fantacalciopedia.py).
    fantamedia REAL CHECK (fantamedia IS NULL OR fantamedia > 0),
    avg_rating REAL,
    appearances INTEGER
);

-- Every "latest quotation" query (get_latest_quotations, get_all_latest_quotations,
-- get_latest_quotations_for_player) filters/joins on player_id and picks the
-- newest row per (player_id, source) via a correlated subquery — without this
-- index that subquery is a full table scan per row, and quotations grows by
-- ~4-6 rows per player on every scraping run.
CREATE INDEX IF NOT EXISTS idx_quotations_player_source_date
    ON quotations(player_id, source, scrape_date DESC, id DESC);
-- Idempotency guard (TASK-006/P1-016): re-scraping the same (player, source,
-- day) must update the existing row (see repository.insert_quotation's
-- ON CONFLICT), not add a duplicate. On a DB that predates this index,
-- _migrate() dedupes existing rows first so this CREATE doesn't fail.
CREATE UNIQUE INDEX IF NOT EXISTS idx_quotations_unique
    ON quotations(player_id, source, scrape_date);
-- Feeds get_source_stats' GROUP BY source and get_price_history's per-player scan.
CREATE INDEX IF NOT EXISTS idx_quotations_source ON quotations(source);
CREATE INDEX IF NOT EXISTS idx_players_role ON players(role_classic);

CREATE TABLE IF NOT EXISTS my_roster (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(id),
    price_paid REAL NOT NULL,
    date_added TEXT NOT NULL
);
-- A double-submit of the "add to roster" form (or re-adding after a typo)
-- must update the existing entry, not silently double-count the player in
-- budget/slot math (repository.add_roster_entry's ON CONFLICT relies on
-- this). On a DB that predates this index, _migrate() dedupes existing
-- rows first so this CREATE doesn't fail (P1-017/TASK-020).
CREATE UNIQUE INDEX IF NOT EXISTS idx_my_roster_player
    ON my_roster(player_id);

CREATE TABLE IF NOT EXISTS opponent_picks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(id),
    opponent_name TEXT NOT NULL,
    price_paid REAL,
    date_added TEXT NOT NULL,
    UNIQUE(player_id)
);

CREATE TABLE IF NOT EXISTS player_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL UNIQUE REFERENCES players(id),
    notes TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS player_transfermarkt_ids (
    player_id INTEGER PRIMARY KEY REFERENCES players(id),
    transfermarkt_id INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);

-- weight: how much this source counts for the price/credit consensus.
-- weight_stats: how much it counts for everything else (fantamedia, media
-- voto, presenze) — kept separate because fantacalcio_online/fantanalisi are
-- trustworthy for real auction credits but aren't specialized stats sources,
-- so they shouldn't drown out fantacalcio_it/fantacalciopedia there.
CREATE TABLE IF NOT EXISTS sources (
    name TEXT PRIMARY KEY,
    weight REAL NOT NULL DEFAULT 1,
    weight_stats REAL NOT NULL DEFAULT 1
);

-- Valori scelti dall'utente (2026-08-26): percentuali dirette (sommano a
-- 100 in ciascuna colonna), non pesi relativi arbitrari come prima.
INSERT OR IGNORE INTO sources (name, weight, weight_stats) VALUES
    ('fantacalcio_online', 45, 10),
    ('fantanalisi', 35, 25),
    ('fantapazz', 10, 25),
    ('fantacalcio_it', 0, 20),
    ('pianetafanta', 5, 10),
    ('fantacalciopedia', 5, 10);

CREATE TABLE IF NOT EXISTS player_source_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(id),
    source TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_team TEXT NOT NULL,
    confidence REAL NOT NULL,
    matched_at TEXT NOT NULL,
    -- Human review of this fuzzy match: 'confirmed' (🟢 stessa persona),
    -- 'unsure' (🟡 non so), 'rejected' (🔴 non è la stessa persona — la
    -- quotazione di questa fonte viene esclusa dal consensus del giocatore).
    -- NULL = non ancora rivisto.
    review_status TEXT,
    UNIQUE(player_id, source)
);

CREATE TABLE IF NOT EXISTS player_set_pieces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(id),
    category TEXT NOT NULL,
    rank INTEGER NOT NULL,
    source TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(player_id, category, source)
);

CREATE TABLE IF NOT EXISTS player_match_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(id),
    season TEXT NOT NULL,
    giornata INTEGER NOT NULL,
    voto REAL,
    fantavoto REAL,
    source TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(player_id, season, giornata, source)
);

CREATE TABLE IF NOT EXISTS player_injuries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(id),
    season TEXT NOT NULL,
    injury_type TEXT NOT NULL,
    date_from TEXT,
    date_to TEXT,
    days_out INTEGER,
    matches_missed INTEGER,
    UNIQUE(player_id, season, injury_type, date_from)
);

CREATE TABLE IF NOT EXISTS fcp_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(id),
    scrape_date TEXT NOT NULL,
    alg_fcp REAL,
    punteggio_fcp REAL,
    investment_stability_pct REAL,
    injury_resistance_pct REAL,
    predicted_appearances TEXT,
    predicted_goals TEXT,
    predicted_assists TEXT,
    skills TEXT
);

-- get_all_latest_fcp_metrics/get_latest_fcp_metrics pick the newest row per
-- player_id via the same correlated-subquery pattern as quotations.
CREATE INDEX IF NOT EXISTS idx_fcp_metrics_player_date
    ON fcp_metrics(player_id, scrape_date DESC, id DESC);

-- One row per (player, season): goals_scored is for outfield players,
-- goals_conceded for portieri (Fantacalciopedia's own "golF"/"golS" split —
-- see scrapers.fantacalciopedia.parse_season_stats), only one of the two is
-- ever populated on a given row. UNIQUE(player_id, season) since this is a
-- re-scrape-and-replace table (upsert_player_season_stats), not an
-- append-only history like quotations — a season's stats don't need
-- multiple dated snapshots, just the latest scrape.
CREATE TABLE IF NOT EXISTS player_season_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(id),
    season TEXT NOT NULL,
    source TEXT NOT NULL,
    appearances INTEGER,
    goals_scored INTEGER,
    goals_conceded INTEGER,
    assists INTEGER,
    avg_rating REAL,
    yellow_cards INTEGER,
    red_cards INTEGER,
    scraped_at TEXT NOT NULL,
    UNIQUE(player_id, season, source)
);
CREATE INDEX IF NOT EXISTS idx_player_season_stats_player
    ON player_season_stats(player_id);

-- Forza squadra (xG/xGA/PPDA, dati Understat via fantanalisi.it/squadre):
-- storicizzata come le quotazioni (una riga per scrape, mai overwrite) —
-- vedi scrapers/fantanalisi_squadre.py. Solo aggregati per squadra
-- disponibili sulla fonte, non serie temporali per giornata.
CREATE TABLE IF NOT EXISTS team_strength (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team TEXT NOT NULL,
    xg REAL,
    xga REAL,
    ppda REAL,
    source TEXT NOT NULL,
    scrape_date TEXT NOT NULL,
    UNIQUE(team, source, scrape_date)
);
CREATE INDEX IF NOT EXISTS idx_team_strength_team ON team_strength(team);

-- Anagrafica (età/altezza/piede/nazionalità/numero maglia), fonte
-- Transfermarkt (scrapers/transfermarkt.py, PROFILE_URL). Non cambia in
-- corso di stagione (a parte trasferimenti/numero maglia): upsert-in-place
-- come player_transfermarkt_ids, non storicizzata come le quotazioni.
CREATE TABLE IF NOT EXISTS player_anagrafica (
    player_id INTEGER PRIMARY KEY REFERENCES players(id),
    birth_date TEXT,
    height_cm INTEGER,
    foot TEXT,
    nationality TEXT,
    shirt_number INTEGER,
    updated_at TEXT NOT NULL
);

-- Percentili per-90 (xG/xA/tiri/rifiniture/coinvolgimento/minuti) rispetto
-- al ruolo, fonte Understat via fantanalisi.it/giocatori/{id}-{slug}
-- (scrapers/fantanalisi_giocatore.py). Storicizzata come team_strength: i
-- percentili si spostano nel corso della stagione, una riga per scrape.
CREATE TABLE IF NOT EXISTS player_advanced_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(id),
    xg90_percentile INTEGER,
    xa90_percentile INTEGER,
    shots90_percentile INTEGER,
    key_passes90_percentile INTEGER,
    involvement_percentile INTEGER,
    minutes_percentile INTEGER,
    source TEXT NOT NULL,
    scrape_date TEXT NOT NULL,
    UNIQUE(player_id, source, scrape_date)
);
CREATE INDEX IF NOT EXISTS idx_player_advanced_stats_player
    ON player_advanced_stats(player_id);

-- Difficoltà del calendario (finestra "prime 5 giornate", scala 0-100:
-- 0=più duro, 100=più morbido), fonte fantanalisi.it/calendario
-- (scrapers/fantanalisi_calendario.py). difficulty_attack = morbidezza per
-- chi attacca (quanto concede l'avversario), difficulty_defense = per la
-- porta (quanto poco segna l'avversario). Storicizzata come team_strength:
-- la finestra "prime 5" si sposta di giornata in giornata.
CREATE TABLE IF NOT EXISTS team_fixture_difficulty (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team TEXT NOT NULL,
    difficulty_attack INTEGER,
    difficulty_defense INTEGER,
    window_label TEXT NOT NULL,
    source TEXT NOT NULL,
    scrape_date TEXT NOT NULL,
    UNIQUE(team, window_label, source, scrape_date)
);
CREATE INDEX IF NOT EXISTS idx_team_fixture_difficulty_team
    ON team_fixture_difficulty(team);

-- Valutazioni proprietarie di fantanalisi.it (Fasce affare, Max bid, Tier,
-- Risk badge) dalla tabella /giocatori — testo grezzo, non riparsato in
-- numeri (formato non verificato dal vivo). Solo informative: non
-- alimentano i calcoli interni (ranking/scorer.py, tiers.py, verdict.py
-- hanno i propri equivalenti). Storicizzata come team_strength/
-- player_advanced_stats: una riga per scrape.
CREATE TABLE IF NOT EXISTS player_fantanalisi_valuations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(id),
    fair_price_range TEXT,
    max_bid TEXT,
    tier TEXT,
    risk TEXT,
    source TEXT NOT NULL,
    scrape_date TEXT NOT NULL,
    UNIQUE(player_id, source, scrape_date)
);
CREATE INDEX IF NOT EXISTS idx_player_fantanalisi_valuations_player
    ON player_fantanalisi_valuations(player_id);

-- The current Serie A team universe. NOTE: the opus review's "P0-006"
-- asserted Frosinone/Monza/Venezia were relegated and Cremonese/Pisa/Verona
-- replaced them — that was a false positive. USER-VERIFIED 2026/27 roster:
-- Venezia/Frosinone/Monza are the promoted sides (docs/superpowers/plans/
-- 2026-08-27-portieri-depth-chart.md + project owner). These rows mirror
-- dashboard/data_access.py's TEAM_ABBREV_TO_FULL and MUST stay in sync with
-- it — the two previously diverged and caused a spurious "fix" loop.
-- is_promoted defaults to 0 (not fabricated) — set it explicitly once a
-- real source confirms which clubs just came up, don't guess.
CREATE TABLE IF NOT EXISTS teams (
    code TEXT NOT NULL,             -- matching.player_matcher.normalize_team(full_name)
    full_name TEXT NOT NULL,
    season TEXT NOT NULL,
    is_promoted INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (code, season)
);

-- Corrected 2026/27 Serie A roster (user-verified, see comment above).
INSERT OR IGNORE INTO teams (code, full_name, season, is_promoted) VALUES
    ('ata', 'Atalanta', '2026/27', 0),
    ('bol', 'Bologna', '2026/27', 0),
    ('cag', 'Cagliari', '2026/27', 0),
    ('com', 'Como', '2026/27', 0),
    ('fio', 'Fiorentina', '2026/27', 0),
    ('fro', 'Frosinone', '2026/27', 0),
    ('gen', 'Genoa', '2026/27', 0),
    ('int', 'Inter', '2026/27', 0),
    ('juv', 'Juventus', '2026/27', 0),
    ('laz', 'Lazio', '2026/27', 0),
    ('lec', 'Lecce', '2026/27', 0),
    ('mil', 'Milan', '2026/27', 0),
    ('mon', 'Monza', '2026/27', 0),
    ('nap', 'Napoli', '2026/27', 0),
    ('par', 'Parma', '2026/27', 0),
    ('rom', 'Roma', '2026/27', 0),
    ('sas', 'Sassuolo', '2026/27', 0),
    ('tor', 'Torino', '2026/27', 0),
    ('udi', 'Udinese', '2026/27', 0),
    ('ven', 'Venezia', '2026/27', 0);
