CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL,
    team TEXT NOT NULL,
    role_classic TEXT NOT NULL,
    role_mantra TEXT,
    photo_path TEXT,
    UNIQUE(canonical_name, team)
);

CREATE TABLE IF NOT EXISTS quotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(id),
    source TEXT NOT NULL,
    scrape_date TEXT NOT NULL,
    price_current REAL,
    price_initial REAL,
    status TEXT,
    fantamedia REAL,
    avg_rating REAL,
    appearances INTEGER
);

CREATE TABLE IF NOT EXISTS my_roster (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(id),
    price_paid REAL NOT NULL,
    date_added TEXT NOT NULL
);

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

CREATE TABLE IF NOT EXISTS sources (
    name TEXT PRIMARY KEY,
    weight REAL NOT NULL DEFAULT 1
);

INSERT OR IGNORE INTO sources (name, weight) VALUES
    ('fantacalcio_it', 3),
    ('fantacalciopedia', 2),
    ('fantapazz', 1.5),
    ('pianetafanta', 1.5);

CREATE TABLE IF NOT EXISTS player_source_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(id),
    source TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_team TEXT NOT NULL,
    confidence REAL NOT NULL,
    matched_at TEXT NOT NULL,
    UNIQUE(player_id, source)
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
