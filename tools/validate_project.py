"""Cross-check SQL results against pandas outputs and core data rules."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
DATABASE_PATH = RAW_DIR / "search_experiment.db"


def main() -> None:
    assignments = pd.read_csv(RAW_DIR / "experiment_assignments.csv")
    sessions = pd.read_csv(RAW_DIR / "search_sessions.csv")
    variant_summary = pd.read_csv(PROCESSED_DIR / "variant_summary.csv")

    with sqlite3.connect(DATABASE_PATH) as connection:
        sql_summary = pd.read_sql_query(
            """
            SELECT
                a.variant,
                COUNT(*) AS search_sessions,
                AVG(s.successful_search) AS session_success_rate,
                AVG(s.search_error) AS session_error_rate
            FROM search_sessions AS s
            JOIN experiment_assignments AS a
                ON s.user_id = a.user_id
            GROUP BY a.variant
            ORDER BY a.variant
            """,
            connection,
        )
        table_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ["experiment_assignments", "search_sessions"]
        }

    pandas_summary = variant_summary[
        ["variant", "search_sessions", "session_success_rate", "session_error_rate"]
    ].sort_values("variant")
    sql_summary = sql_summary.sort_values("variant")

    assert sql_summary["variant"].tolist() == pandas_summary["variant"].tolist()
    assert sql_summary["search_sessions"].tolist() == pandas_summary[
        "search_sessions"
    ].tolist()
    assert np.allclose(
        sql_summary["session_success_rate"], pandas_summary["session_success_rate"]
    )
    assert np.allclose(
        sql_summary["session_error_rate"], pandas_summary["session_error_rate"]
    )
    assert table_counts == {
        "experiment_assignments": len(assignments),
        "search_sessions": len(sessions),
    }
    assert sessions["user_id"].isin(assignments["user_id"]).all()

    print("SQL and pandas experiment summaries match.")
    print(f"Validated table counts: {table_counts}")


if __name__ == "__main__":
    main()
