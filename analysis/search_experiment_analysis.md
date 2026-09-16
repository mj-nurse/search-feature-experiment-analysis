Search Feature Experiment and User Engagement Analysis
================
Marlon Nurse

- [Overview](#overview)
- [Experiment design](#experiment-design)
- [Data checks](#data-checks)
- [Assignment balance](#assignment-balance)
- [User-level metrics](#user-level-metrics)
- [Primary statistical test](#primary-statistical-test)
- [Guardrail test](#guardrail-test)
- [Platform results](#platform-results)
- [Interpretation](#interpretation)

## Overview

This analysis evaluates a synthetic 28-day randomized experiment
comparing the existing search experience with an improved-results
variant. The assignment unit is the user, so the primary statistical
test is performed on user-level success rates rather than treating
repeated search sessions as independent observations.

``` r
library(dplyr)
library(ggplot2)
library(knitr)

project_root <- if (file.exists("requirements.txt")) "." else ".."

read_project_csv <- function(file_name) {
  file_path <- file.path(project_root, "data", "raw", file_name)

  if (!file.exists(file_path)) {
    stop(
      paste0(
        "Could not find ", file_path,
        ". Open the repository as an RStudio project or knit from the analysis folder."
      )
    )
  }

  read.csv(
    file_path,
    row.names = NULL,
    check.names = FALSE,
    stringsAsFactors = FALSE
  )
}

assignments <- read.csv("https://raw.githubusercontent.com/mj-nurse/search-feature-experiment-analysis/refs/heads/main/data/raw/experiment_assignments.csv")
sessions <- read.csv("https://raw.githubusercontent.com/mj-nurse/search-feature-experiment-analysis/refs/heads/main/data/raw/search_sessions.csv")
```

## Experiment design

- **Population:** 12,000 synthetic users with at least one search
  session
- **Randomization unit:** User
- **Control:** Existing search results
- **Treatment:** Improved search results
- **Primary metric:** Mean user search success rate, where a successful
  session includes a result click followed by at least two minutes of
  watch time
- **Diagnostics:** Click-through rate, zero-result rate, and watch time
  after search
- **Guardrail:** Search error rate

Secondary and segment results are exploratory. The primary metric is
evaluated with a two-sided Welch t-test at the user level.

## Data checks

``` r
data_checks <- data.frame(
  check = c(
    "Unique user assignments",
    "Unique search sessions",
    "Sessions with valid assigned user",
    "Successful sessions with a click",
    "Successful sessions with at least two watch minutes"
  ),
  passed = c(
    !any(duplicated(assignments$user_id)),
    !any(duplicated(sessions$session_id)),
    all(sessions$user_id %in% assignments$user_id),
    all(sessions$clicked_result[sessions$successful_search == 1] == 1),
    all(sessions$watch_minutes_after_search[sessions$successful_search == 1] >= 2)
  )
)

kable(data_checks)
```

| check                                               | passed |
|:----------------------------------------------------|:-------|
| Unique user assignments                             | TRUE   |
| Unique search sessions                              | TRUE   |
| Sessions with valid assigned user                   | TRUE   |
| Successful sessions with a click                    | TRUE   |
| Successful sessions with at least two watch minutes | TRUE   |

## Assignment balance

``` r
assignment_counts <- table(
  factor(
    assignments$variant,
    levels = c("control", "improved_results")
  )
)

assignment_summary <- data.frame(
  variant = names(assignment_counts),
  assigned_users = as.integer(assignment_counts),
  assignment_share = as.integer(assignment_counts) / sum(assignment_counts)
)

kable(assignment_summary, digits = 3)
```

| variant          | assigned_users | assignment_share |
|:-----------------|---------------:|-----------------:|
| control          |           6046 |            0.504 |
| improved_results |           5954 |            0.496 |

``` r
srm_test <- chisq.test(assignment_counts, p = c(0.5, 0.5))
srm_test
```

    ## 
    ##  Chi-squared test for given probabilities
    ## 
    ## data:  assignment_counts
    ## X-squared = 0.70533, df = 1, p-value = 0.401

## User-level metrics

``` r
user_metrics <- sessions %>%
  group_by(user_id) %>%
  summarise(
    search_sessions = n(),
    success_rate = mean(successful_search),
    click_through_rate = mean(clicked_result),
    zero_result_rate = mean(zero_results),
    error_rate = mean(search_error),
    avg_watch_minutes = mean(watch_minutes_after_search),
    .groups = "drop"
  ) %>%
  inner_join(assignments, by = "user_id")

variant_summary <- user_metrics %>%
  group_by(variant) %>%
  summarise(
    users = n(),
    mean_user_success_rate = mean(success_rate),
    mean_user_click_through_rate = mean(click_through_rate),
    mean_user_zero_result_rate = mean(zero_result_rate),
    mean_user_error_rate = mean(error_rate),
    avg_watch_minutes = mean(avg_watch_minutes),
    .groups = "drop"
  )

kable(variant_summary, digits = 4)
```

| variant | users | mean_user_success_rate | mean_user_click_through_rate | mean_user_zero_result_rate | mean_user_error_rate | avg_watch_minutes |
|:---|---:|---:|---:|---:|---:|---:|
| control | 6046 | 0.4630 | 0.5442 | 0.0729 | 0.0098 | 3.7252 |
| improved_results | 5954 | 0.4974 | 0.5758 | 0.0630 | 0.0114 | 4.0848 |

## Primary statistical test

``` r
control_success <- user_metrics %>%
  filter(variant == "control") %>%
  pull(success_rate)

treatment_success <- user_metrics %>%
  filter(variant == "improved_results") %>%
  pull(success_rate)

primary_test <- t.test(
  treatment_success,
  control_success,
  alternative = "two.sided",
  var.equal = FALSE,
  conf.level = 0.95
)

primary_result <- data.frame(
  control_mean = mean(control_success),
  treatment_mean = mean(treatment_success),
  absolute_lift_percentage_points =
    (mean(treatment_success) - mean(control_success)) * 100,
  relative_lift_pct =
    (mean(treatment_success) / mean(control_success) - 1) * 100,
  ci_lower_percentage_points = primary_test$conf.int[1] * 100,
  ci_upper_percentage_points = primary_test$conf.int[2] * 100,
  p_value = primary_test$p.value
)

kable(primary_result, digits = 4)
```

| control_mean | treatment_mean | absolute_lift_percentage_points | relative_lift_pct | ci_lower_percentage_points | ci_upper_percentage_points | p_value |
|---:|---:|---:|---:|---:|---:|---:|
| 0.463 | 0.4974 | 3.4439 | 7.4386 | 2.6962 | 4.1916 | 0 |

``` r
primary_test
```

    ## 
    ##  Welch Two Sample t-test
    ## 
    ## data:  treatment_success and control_success
    ## t = 9.0282, df = 11993, p-value < 2.2e-16
    ## alternative hypothesis: true difference in means is not equal to 0
    ## 95 percent confidence interval:
    ##  0.02696184 0.04191631
    ## sample estimates:
    ## mean of x mean of y 
    ## 0.4974186 0.4629795

## Guardrail test

``` r
control_error <- user_metrics %>%
  filter(variant == "control") %>%
  pull(error_rate)

treatment_error <- user_metrics %>%
  filter(variant == "improved_results") %>%
  pull(error_rate)

guardrail_test <- t.test(
  treatment_error,
  control_error,
  alternative = "two.sided",
  var.equal = FALSE,
  conf.level = 0.95
)

guardrail_result <- data.frame(
  control_error_rate = mean(control_error),
  treatment_error_rate = mean(treatment_error),
  difference_percentage_points =
    (mean(treatment_error) - mean(control_error)) * 100,
  ci_lower_percentage_points = guardrail_test$conf.int[1] * 100,
  ci_upper_percentage_points = guardrail_test$conf.int[2] * 100,
  p_value = guardrail_test$p.value
)

kable(guardrail_result, digits = 4)
```

| control_error_rate | treatment_error_rate | difference_percentage_points | ci_lower_percentage_points | ci_upper_percentage_points | p_value |
|---:|---:|---:|---:|---:|---:|
| 0.0098 | 0.0114 | 0.1597 | 0.0039 | 0.3156 | 0.0445 |

## Platform results

``` r
platform_summary <- user_metrics %>%
  group_by(platform, variant) %>%
  summarise(
    users = n(),
    mean_user_success_rate = mean(success_rate),
    mean_user_error_rate = mean(error_rate),
    .groups = "drop"
  )

kable(platform_summary, digits = 4)
```

| platform | variant          | users | mean_user_success_rate | mean_user_error_rate |
|:---------|:-----------------|------:|-----------------------:|---------------------:|
| Desktop  | control          |  1670 |                 0.4777 |               0.0086 |
| Desktop  | improved_results |  1661 |                 0.5037 |               0.0118 |
| Mobile   | control          |  3522 |                 0.4596 |               0.0093 |
| Mobile   | improved_results |  3451 |                 0.4976 |               0.0106 |
| TV       | control          |   854 |                 0.4482 |               0.0142 |
| TV       | improved_results |   842 |                 0.4844 |               0.0138 |

``` r
ggplot(
  variant_summary,
  aes(
    x = factor(
      variant,
      levels = c("control", "improved_results"),
      labels = c("Control", "Improved results")
    ),
    y = mean_user_success_rate,
    fill = variant
  )
) +
  geom_col(width = 0.65, color = "#303134", show.legend = FALSE) +
  geom_text(
    aes(label = scales::percent(mean_user_success_rate, accuracy = 0.1)),
    vjust = -0.5
  ) +
  scale_fill_manual(values = c("#5F6368", "#1A73E8")) +
  scale_y_continuous(
    labels = scales::percent_format(accuracy = 1),
    limits = c(0, 0.60)
  ) +
  labs(
    title = "Mean User Search Success Rate by Experiment Variant",
    subtitle = "Synthetic 28-day randomized experiment; user is the analysis unit",
    x = "Experiment variant",
    y = "Mean user success rate"
  ) +
  theme_minimal()
```

![](search_experiment_analysis_files/figure-gfm/primary-chart-1.png)<!-- -->

## Interpretation

The experiment should be evaluated using the pre-specified user-level
primary metric, assignment-balance check, confidence interval, and
search-error guardrail. Platform and query-category results can help
identify follow-up questions, but they should not replace the overall
randomized comparison or be treated as independently confirmed effects
without adjustment for multiple testing.

Because the dataset is synthetic, the result demonstrates an
experiment-analysis workflow rather than the performance of a real
search product.
