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

CREATE TABLE IF NOT EXISTS player_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL UNIQUE REFERENCES players(id),
    notes TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
