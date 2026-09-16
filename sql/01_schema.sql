DROP TABLE IF EXISTS search_sessions;
DROP TABLE IF EXISTS experiment_assignments;

CREATE TABLE experiment_assignments (
    user_id TEXT PRIMARY KEY,
    variant TEXT NOT NULL CHECK (variant IN ('control', 'improved_results')),
    assigned_at TEXT NOT NULL,
    platform TEXT NOT NULL CHECK (platform IN ('Mobile', 'Desktop', 'TV')),
    region TEXT NOT NULL,
    user_tenure TEXT NOT NULL CHECK (user_tenure IN ('New', 'Existing'))
);

CREATE TABLE search_sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    search_date TEXT NOT NULL,
    query_category TEXT NOT NULL,
    query_length_words INTEGER NOT NULL CHECK (query_length_words > 0),
    results_returned INTEGER NOT NULL CHECK (results_returned >= 0),
    zero_results INTEGER NOT NULL CHECK (zero_results IN (0, 1)),
    clicked_result INTEGER NOT NULL CHECK (clicked_result IN (0, 1)),
    successful_search INTEGER NOT NULL CHECK (successful_search IN (0, 1)),
    time_to_first_click_seconds REAL,
    clicked_rank INTEGER,
    watch_minutes_after_search REAL NOT NULL CHECK (watch_minutes_after_search >= 0),
    search_error INTEGER NOT NULL CHECK (search_error IN (0, 1)),
    FOREIGN KEY (user_id) REFERENCES experiment_assignments(user_id)
);
