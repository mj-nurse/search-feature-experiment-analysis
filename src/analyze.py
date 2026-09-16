"""Validate the experiment data and prepare analysis outputs."""

from __future__ import annotations

import math
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
OUTPUT_DIR = ROOT / "data" / "processed"
DATABASE_PATH = RAW_DIR / "search_experiment.db"
QUERY_PATH = ROOT / "sql" / "02_experiment_analysis.sql"
VARIANT_ORDER = ["control", "improved_results"]
COLORS = {"control": "#5F6368", "improved_results": "#1A73E8"}


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    assignments = pd.read_csv(RAW_DIR / "experiment_assignments.csv")
    sessions = pd.read_csv(RAW_DIR / "search_sessions.csv")
    return assignments, sessions


def validate_data(assignments: pd.DataFrame, sessions: pd.DataFrame) -> None:
    assert assignments["user_id"].is_unique
    assert sessions["session_id"].is_unique
    assert sessions["user_id"].isin(assignments["user_id"]).all()
    assert set(assignments["variant"]) == set(VARIANT_ORDER)
    assert sessions["search_date"].between("2026-05-01", "2026-05-28").all()
    assert sessions["successful_search"].isin([0, 1]).all()
    assert sessions["clicked_result"].isin([0, 1]).all()
    assert sessions["search_error"].isin([0, 1]).all()
    assert sessions["zero_results"].isin([0, 1]).all()
    assert (sessions["results_returned"] >= 0).all()
    assert (sessions["watch_minutes_after_search"] >= 0).all()

    successful = sessions["successful_search"].eq(1)
    assert sessions.loc[successful, "clicked_result"].eq(1).all()
    assert sessions.loc[successful, "watch_minutes_after_search"].ge(2).all()

    not_clicked = sessions["clicked_result"].eq(0)
    assert sessions.loc[not_clicked, "clicked_rank"].isna().all()
    assert sessions.loc[not_clicked, "time_to_first_click_seconds"].isna().all()


def create_user_metrics(
    assignments: pd.DataFrame, sessions: pd.DataFrame
) -> pd.DataFrame:
    session_rollup = (
        sessions.groupby("user_id", as_index=False)
        .agg(
            search_sessions=("session_id", "count"),
            successful_searches=("successful_search", "sum"),
            success_rate=("successful_search", "mean"),
            click_through_rate=("clicked_result", "mean"),
            zero_result_rate=("zero_results", "mean"),
            error_rate=("search_error", "mean"),
            avg_watch_minutes=("watch_minutes_after_search", "mean"),
            avg_time_to_click_seconds=("time_to_first_click_seconds", "mean"),
        )
    )
    return assignments.merge(session_rollup, on="user_id", how="inner", validate="1:1")


def create_variant_summary(
    assignments: pd.DataFrame,
    sessions: pd.DataFrame,
    user_metrics: pd.DataFrame,
) -> pd.DataFrame:
    session_level = sessions.merge(
        assignments[["user_id", "variant"]], on="user_id", how="left", validate="m:1"
    )
    session_summary = (
        session_level.groupby("variant", as_index=False)
        .agg(
            search_sessions=("session_id", "count"),
            session_success_rate=("successful_search", "mean"),
            session_click_through_rate=("clicked_result", "mean"),
            session_zero_result_rate=("zero_results", "mean"),
            session_error_rate=("search_error", "mean"),
            avg_watch_minutes=("watch_minutes_after_search", "mean"),
            avg_time_to_click_seconds=("time_to_first_click_seconds", "mean"),
        )
    )
    user_summary = (
        user_metrics.groupby("variant", as_index=False)
        .agg(
            assigned_users=("user_id", "count"),
            mean_user_success_rate=("success_rate", "mean"),
            user_success_rate_sd=("success_rate", "std"),
            mean_user_error_rate=("error_rate", "mean"),
        )
    )
    user_summary["primary_ci_margin"] = 1.96 * (
        user_summary["user_success_rate_sd"]
        / np.sqrt(user_summary["assigned_users"])
    )
    user_summary["primary_ci_lower"] = (
        user_summary["mean_user_success_rate"] - user_summary["primary_ci_margin"]
    )
    user_summary["primary_ci_upper"] = (
        user_summary["mean_user_success_rate"] + user_summary["primary_ci_margin"]
    )
    summary = user_summary.merge(session_summary, on="variant", validate="1:1")
    summary["variant"] = pd.Categorical(
        summary["variant"], categories=VARIANT_ORDER, ordered=True
    )
    return summary.sort_values("variant").reset_index(drop=True)


def create_daily_metrics(
    assignments: pd.DataFrame, sessions: pd.DataFrame
) -> pd.DataFrame:
    session_level = sessions.merge(
        assignments[["user_id", "variant"]], on="user_id", how="left", validate="m:1"
    )
    return (
        session_level.groupby(["search_date", "variant"], as_index=False)
        .agg(
            search_sessions=("session_id", "count"),
            successful_search_rate=("successful_search", "mean"),
            click_through_rate=("clicked_result", "mean"),
            search_error_rate=("search_error", "mean"),
        )
        .sort_values(["search_date", "variant"])
    )


def create_segment_summary(user_metrics: pd.DataFrame) -> pd.DataFrame:
    return (
        user_metrics.groupby(["platform", "variant"], as_index=False)
        .agg(
            users=("user_id", "count"),
            search_sessions=("search_sessions", "sum"),
            mean_user_success_rate=("success_rate", "mean"),
            mean_user_click_through_rate=("click_through_rate", "mean"),
            mean_user_error_rate=("error_rate", "mean"),
        )
        .sort_values(["platform", "variant"])
    )


def mean_difference_test(
    treatment: pd.Series, control: pd.Series
) -> tuple[float, float, float, float]:
    """Return treatment-control difference, normal CI, and approximate p-value."""
    difference = treatment.mean() - control.mean()
    standard_error = math.sqrt(
        treatment.var(ddof=1) / len(treatment) + control.var(ddof=1) / len(control)
    )
    lower = difference - (1.96 * standard_error)
    upper = difference + (1.96 * standard_error)
    z_score = difference / standard_error
    p_value = math.erfc(abs(z_score) / math.sqrt(2))
    return difference, lower, upper, p_value


def create_experiment_result(
    assignments: pd.DataFrame, user_metrics: pd.DataFrame
) -> pd.DataFrame:
    treatment = user_metrics.loc[
        user_metrics["variant"].eq("improved_results"), "success_rate"
    ]
    control = user_metrics.loc[user_metrics["variant"].eq("control"), "success_rate"]
    difference, lower, upper, p_value = mean_difference_test(treatment, control)

    treatment_error = user_metrics.loc[
        user_metrics["variant"].eq("improved_results"), "error_rate"
    ]
    control_error = user_metrics.loc[
        user_metrics["variant"].eq("control"), "error_rate"
    ]
    error_difference, error_lower, error_upper, error_p_value = mean_difference_test(
        treatment_error, control_error
    )

    counts = assignments["variant"].value_counts().reindex(VARIANT_ORDER)
    expected = len(assignments) / 2
    chi_square = float(((counts - expected) ** 2 / expected).sum())
    sample_ratio_p_value = math.erfc(math.sqrt(chi_square / 2))

    control_mean = control.mean()
    treatment_mean = treatment.mean()
    rollout_signal = (
        lower > 0 and error_upper < 0.005 and sample_ratio_p_value >= 0.01
    )

    return pd.DataFrame(
        [
            {
                "control_mean_user_success_rate": control_mean,
                "treatment_mean_user_success_rate": treatment_mean,
                "absolute_lift_percentage_points": difference * 100,
                "relative_lift_pct": (difference / control_mean) * 100,
                "lift_ci_lower_percentage_points": lower * 100,
                "lift_ci_upper_percentage_points": upper * 100,
                "approx_primary_p_value": p_value,
                "error_rate_difference_percentage_points": error_difference * 100,
                "error_diff_ci_lower_percentage_points": error_lower * 100,
                "error_diff_ci_upper_percentage_points": error_upper * 100,
                "approx_error_p_value": error_p_value,
                "sample_ratio_p_value": sample_ratio_p_value,
                "synthetic_rollout_signal": rollout_signal,
            }
        ]
    )


def create_charts(
    variant_summary: pd.DataFrame, daily_metrics: pd.DataFrame
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    labels = ["Control", "Improved results"]
    values = variant_summary["mean_user_success_rate"] * 100
    lower_errors = (
        variant_summary["mean_user_success_rate"]
        - variant_summary["primary_ci_lower"]
    ) * 100
    upper_errors = (
        variant_summary["primary_ci_upper"]
        - variant_summary["mean_user_success_rate"]
    ) * 100

    figure, axis = plt.subplots(figsize=(8, 5))
    bars = axis.bar(
        labels,
        values,
        color=[COLORS[variant] for variant in VARIANT_ORDER],
        edgecolor="#303134",
        linewidth=0.7,
        yerr=np.vstack([lower_errors, upper_errors]),
        capsize=5,
    )
    axis.set_title("Mean User Search Success Rate by Experiment Variant")
    axis.set_ylabel("Mean user success rate (%)")
    axis.set_ylim(0, max(values.max() * 1.22, 60))
    axis.grid(axis="y", color="#DADCE0", linewidth=0.7, alpha=0.8)
    axis.set_axisbelow(True)
    for bar, value in zip(bars, values, strict=True):
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            value + 1.3,
            f"{value:.1f}%",
            ha="center",
            va="bottom",
            color="#202124",
        )
    figure.tight_layout()
    figure.savefig(OUTPUT_DIR / "primary_metric_by_variant.png", dpi=180)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(10, 5.5))
    for variant in VARIANT_ORDER:
        subset = daily_metrics[daily_metrics["variant"].eq(variant)]
        axis.plot(
            pd.to_datetime(subset["search_date"]),
            subset["successful_search_rate"] * 100,
            label="Control" if variant == "control" else "Improved results",
            color=COLORS[variant],
            linewidth=2.0,
            marker="o",
            markersize=3.5,
        )
    figure.suptitle("Daily Search Success Rate During the 28-Day Experiment", y=0.98)
    axis.set_title(
        "Focused y-axis; synthetic search sessions, May 1-28, 2026",
        fontsize=10,
        color="#5F6368",
        pad=10,
    )
    axis.set_ylabel("Successful search rate (%)")
    axis.set_xlabel("Search date")
    axis.grid(axis="y", color="#DADCE0", linewidth=0.7, alpha=0.8)
    axis.legend(frameon=False)
    figure.autofmt_xdate(rotation=30)
    figure.tight_layout(rect=[0, 0, 1, 0.94])
    figure.savefig(OUTPUT_DIR / "daily_search_success_rate.png", dpi=180)
    plt.close(figure)


def validate_sql_queries() -> int:
    statements = [
        statement.strip()
        for statement in QUERY_PATH.read_text(encoding="utf-8").split(";")
        if statement.strip()
    ]
    with sqlite3.connect(DATABASE_PATH) as connection:
        for statement in statements:
            connection.execute(statement).fetchall()
    return len(statements)


def main() -> None:
    assignments, sessions = load_data()
    validate_data(assignments, sessions)
    user_metrics = create_user_metrics(assignments, sessions)
    variant_summary = create_variant_summary(assignments, sessions, user_metrics)
    daily_metrics = create_daily_metrics(assignments, sessions)
    segment_summary = create_segment_summary(user_metrics)
    experiment_result = create_experiment_result(assignments, user_metrics)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    user_metrics.to_csv(OUTPUT_DIR / "user_level_metrics.csv", index=False)
    variant_summary.to_csv(OUTPUT_DIR / "variant_summary.csv", index=False)
    daily_metrics.to_csv(OUTPUT_DIR / "daily_metrics.csv", index=False)
    segment_summary.to_csv(OUTPUT_DIR / "platform_summary.csv", index=False)
    experiment_result.to_csv(OUTPUT_DIR / "experiment_result.csv", index=False)
    create_charts(variant_summary, daily_metrics)

    query_count = validate_sql_queries()
    result = experiment_result.iloc[0]
    print(f"Validated {query_count} SQL analyses.")
    print(
        "Primary metric lift: "
        f"{result['absolute_lift_percentage_points']:.2f} percentage points "
        f"(approx. p={result['approx_primary_p_value']:.4f})."
    )


if __name__ == "__main__":
    main()
