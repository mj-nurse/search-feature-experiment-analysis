# Search Experiment Readout

## Decision

The synthetic experiment meets the stated rollout rule: the primary user-level search success metric improved, the upper confidence bound for the search-error increase remained below the 0.5 percentage-point guardrail threshold, and the assignment-balance check passed.

A staged rollout signal is appropriate for this generated scenario. The search-error increase should still be investigated before broad expansion because the treatment error rate was slightly higher than the control rate.

## Experiment scope

- **Period:** May 1–28, 2026
- **Population:** 12,000 synthetic search users
- **Randomization:** User-level, approximately 50/50
- **Control users:** 6,046
- **Treatment users:** 5,954
- **Search sessions:** 81,816

## Primary result

Mean user search success rate increased from **46.30%** in control to **49.74%** in treatment.

- **Absolute lift:** 3.44 percentage points
- **Relative lift:** 7.44%
- **Approximate 95% confidence interval:** 2.70 to 4.19 percentage points
- **Approximate two-sided p-value:** < 0.001

The primary result is calculated at the user level to match the experiment's randomization unit.

## Diagnostic metrics

- Session click-through rate increased from **54.29% to 57.58%**.
- Zero-result rate decreased from **7.36% to 6.27%**.
- Average watch time after search increased from **3.72 to 4.08 minutes per session**.
- Average time to first click decreased from **11.79 to 11.06 seconds**.

These metrics help explain the primary result but were not designated as separate confirmatory endpoints.

## Guardrail and validity checks

- Mean user error rate increased from **0.98% to 1.14%**.
- The estimated error-rate difference was **0.16 percentage points**, with an approximate 95% interval from **0.00 to 0.32 points**.
- The upper confidence bound remained below the stated 0.5-point threshold.
- The sample-ratio mismatch check returned **p = 0.401**, providing no evidence of assignment imbalance.
- Data tests found unique assignment and session keys, complete assignment coverage, valid experiment dates, and internally consistent search outcomes.

## Recommended follow-up

1. Review treatment error logs by platform and query category before increasing exposure.
2. Use a staged rollout with explicit error-rate monitoring and a rollback threshold.
3. Confirm that engagement gains persist beyond the initial 28-day period.
4. Treat platform results as exploratory until they are replicated or tested under a planned multiple-comparison approach.

## Limitations

All records and effects are synthetic. The analysis demonstrates experiment design and interpretation; it does not measure a real product change or justify a real company decision.
