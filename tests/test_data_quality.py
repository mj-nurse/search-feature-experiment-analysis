from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"


def read_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    assignments = pd.read_csv(RAW_DIR / "experiment_assignments.csv")
    sessions = pd.read_csv(RAW_DIR / "search_sessions.csv")
    return assignments, sessions


def test_primary_keys_are_unique() -> None:
    assignments, sessions = read_inputs()
    assert assignments["user_id"].is_unique
    assert sessions["session_id"].is_unique


def test_every_session_has_one_valid_assignment() -> None:
    assignments, sessions = read_inputs()
    assert set(assignments["variant"]) == {"control", "improved_results"}
    assert sessions["user_id"].isin(assignments["user_id"]).all()
    assert assignments["user_id"].isin(sessions["user_id"]).all()


def test_session_values_follow_domain_rules() -> None:
    _, sessions = read_inputs()
    binary_columns = [
        "zero_results",
        "clicked_result",
        "successful_search",
        "search_error",
    ]
    for column in binary_columns:
        assert sessions[column].isin([0, 1]).all()
    assert (sessions["query_length_words"] > 0).all()
    assert (sessions["results_returned"] >= 0).all()
    assert (sessions["watch_minutes_after_search"] >= 0).all()


def test_search_outcomes_are_internally_consistent() -> None:
    _, sessions = read_inputs()
    successful = sessions["successful_search"].eq(1)
    assert sessions.loc[successful, "clicked_result"].eq(1).all()
    assert sessions.loc[successful, "watch_minutes_after_search"].ge(2).all()

    not_clicked = sessions["clicked_result"].eq(0)
    assert sessions.loc[not_clicked, "clicked_rank"].isna().all()
    assert sessions.loc[not_clicked, "time_to_first_click_seconds"].isna().all()


def test_experiment_dates_and_assignment_balance() -> None:
    assignments, sessions = read_inputs()
    assert assignments["assigned_at"].eq("2026-05-01T00:00:00Z").all()
    assert sessions["search_date"].between("2026-05-01", "2026-05-28").all()
    assignment_share = assignments["variant"].value_counts(normalize=True)
    assert assignment_share.between(0.48, 0.52).all()
