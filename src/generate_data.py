"""Generate reproducible synthetic data for a search feature experiment."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
SCHEMA_PATH = ROOT / "sql" / "01_schema.sql"
DATABASE_PATH = RAW_DIR / "search_experiment.db"
RANDOM_SEED = 20260916
EXPERIMENT_START = pd.Timestamp("2026-05-01")
EXPERIMENT_DAYS = 28


def build_assignments(
    rng: np.random.Generator, user_count: int = 12_000
) -> pd.DataFrame:
    """Create one random experiment assignment per eligible search user."""
    user_ids = [f"USR{index:05d}" for index in range(1, user_count + 1)]
    return pd.DataFrame(
        {
            "user_id": user_ids,
            "variant": rng.choice(
                ["control", "improved_results"], size=user_count, p=[0.5, 0.5]
            ),
            "assigned_at": "2026-05-01T00:00:00Z",
            "platform": rng.choice(
                ["Mobile", "Desktop", "TV"], size=user_count, p=[0.58, 0.28, 0.14]
            ),
            "region": rng.choice(
                ["United States", "Canada", "United Kingdom", "Other"],
                size=user_count,
                p=[0.62, 0.12, 0.11, 0.15],
            ),
            "user_tenure": rng.choice(
                ["New", "Existing"], size=user_count, p=[0.27, 0.73]
            ),
        }
    )


def build_search_sessions(
    rng: np.random.Generator, assignments: pd.DataFrame
) -> pd.DataFrame:
    """Create search sessions whose outcomes vary by assignment and context."""
    tenure_session_effect = assignments["user_tenure"].map(
        {"New": 0.0, "Existing": 1.4}
    )
    session_counts = 1 + rng.poisson(4.8 + tenure_session_effect.to_numpy())

    user_index = np.repeat(np.arange(len(assignments)), session_counts)
    session_count = len(user_index)
    repeated = assignments.iloc[user_index].reset_index(drop=True)

    query_categories = rng.choice(
        ["Entertainment", "How-to", "News", "Music", "Shopping"],
        size=session_count,
        p=[0.29, 0.24, 0.17, 0.18, 0.12],
    )
    treatment = repeated["variant"].eq("improved_results").to_numpy()

    category_zero_effect = pd.Series(query_categories).map(
        {
            "Entertainment": -0.010,
            "How-to": 0.005,
            "News": 0.000,
            "Music": -0.012,
            "Shopping": 0.018,
        }
    ).to_numpy()
    zero_probability = np.clip(
        0.076 + category_zero_effect - (0.011 * treatment), 0.02, 0.20
    )
    zero_results = rng.random(session_count) < zero_probability

    platform_error_effect = repeated["platform"].map(
        {"Mobile": 0.000, "Desktop": -0.001, "TV": 0.004}
    ).to_numpy()
    error_probability = np.clip(
        0.010 + platform_error_effect + (0.0003 * treatment), 0.002, 0.04
    )
    search_error = rng.random(session_count) < error_probability

    category_click_effect = pd.Series(query_categories).map(
        {
            "Entertainment": 0.020,
            "How-to": -0.005,
            "News": -0.012,
            "Music": 0.032,
            "Shopping": -0.035,
        }
    ).to_numpy()
    platform_click_effect = repeated["platform"].map(
        {"Mobile": 0.000, "Desktop": 0.012, "TV": -0.030}
    ).to_numpy()
    click_probability = np.clip(
        0.590
        + category_click_effect
        + platform_click_effect
        + (0.026 * treatment),
        0.30,
        0.80,
    )
    clicked_result = (
        (rng.random(session_count) < click_probability)
        & ~zero_results
        & ~search_error
    )

    watch_scale = pd.Series(query_categories).map(
        {
            "Entertainment": 4.4,
            "How-to": 3.5,
            "News": 2.8,
            "Music": 4.8,
            "Shopping": 2.4,
        }
    ).to_numpy()
    watch_minutes = rng.gamma(shape=1.8, scale=watch_scale, size=session_count)
    watch_minutes = watch_minutes * np.where(treatment, 1.035, 1.0)
    watch_minutes = np.where(clicked_result, watch_minutes, 0.0)
    watch_minutes = np.round(watch_minutes, 2)

    successful_search = clicked_result & (watch_minutes >= 2.0)

    time_to_click = rng.lognormal(mean=2.35, sigma=0.48, size=session_count)
    time_to_click = time_to_click * np.where(treatment, 0.94, 1.0)
    time_to_click = np.where(clicked_result, np.round(time_to_click, 1), np.nan)

    rank_probability = np.where(treatment, 0.38, 0.34)
    clicked_rank_values = rng.geometric(rank_probability, size=session_count)
    clicked_rank_values = np.clip(clicked_rank_values, 1, 20)
    clicked_rank = pd.array(
        np.where(clicked_result, clicked_rank_values, np.nan), dtype="Int64"
    )

    baseline_results = rng.poisson(lam=np.where(treatment, 20.0, 18.5))
    results_returned = np.where(zero_results | search_error, 0, baseline_results)

    day_offsets = rng.integers(0, EXPERIMENT_DAYS, size=session_count)
    search_dates = (EXPERIMENT_START + pd.to_timedelta(day_offsets, unit="D")).strftime(
        "%Y-%m-%d"
    )

    return pd.DataFrame(
        {
            "session_id": [
                f"SES{index:07d}" for index in range(1, session_count + 1)
            ],
            "user_id": repeated["user_id"],
            "search_date": search_dates,
            "query_category": query_categories,
            "query_length_words": np.clip(
                rng.poisson(lam=3.1, size=session_count) + 1, 1, 12
            ),
            "results_returned": results_returned,
            "zero_results": zero_results.astype(int),
            "clicked_result": clicked_result.astype(int),
            "successful_search": successful_search.astype(int),
            "time_to_first_click_seconds": time_to_click,
            "clicked_rank": clicked_rank,
            "watch_minutes_after_search": watch_minutes,
            "search_error": search_error.astype(int),
        }
    )


def write_outputs(
    assignments: pd.DataFrame, search_sessions: pd.DataFrame
) -> None:
    """Write CSV inputs and an equivalent SQLite database."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    assignments.to_csv(RAW_DIR / "experiment_assignments.csv", index=False)
    search_sessions.to_csv(RAW_DIR / "search_sessions.csv", index=False)

    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        assignments.to_sql(
            "experiment_assignments", connection, if_exists="append", index=False
        )
        search_sessions.to_sql(
            "search_sessions", connection, if_exists="append", index=False
        )


def main() -> None:
    rng = np.random.default_rng(RANDOM_SEED)
    assignments = build_assignments(rng)
    search_sessions = build_search_sessions(rng, assignments)
    write_outputs(assignments, search_sessions)
    print(
        f"Created {len(assignments):,} assignments and "
        f"{len(search_sessions):,} search sessions."
    )


if __name__ == "__main__":
    main()
