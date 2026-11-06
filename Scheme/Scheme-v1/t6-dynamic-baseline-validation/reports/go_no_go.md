# Phase-A go/no-go decision

## Decision: MAJOR WEAKENING

The current standalone Delta-Aware idea does **not** receive CONTINUE.
Target-conditioned Function Reachability reaches the same complete-case
performance as frozen Delta-Aware at the lowest budget:

- Silent Recall: 17/17 = 100% versus Delta-Aware 20/20 = 100%.
- N4 FPR: 0/18 = 0% versus Delta-Aware 0/19 = 0%.
- Median measured latency: 18.548 s for corpus replay versus 27.889 s for the
  Delta model call.
- Five-minute repeatability: 100% Recall and 0% FPR in all three repeats.

This satisfies the preregistered low-budget accuracy/cost branch among
evaluable cases and materially weakens the necessity of Delta-Aware as an
independent detector.

## Why this is not an unconditional KILL

- Function Reachability is evaluable for 35/39 cases (89.74%), while
  Delta-Aware returns a valid decision for 39/39.
- Its ITT Recall is 17/20 = 85%, 15 percentage points below Delta-Aware.
- Three cases are BUILD_UNAVAILABLE and one positive is a non-function
  configuration target.
- The baseline is supplied the exact audited target symbol.  Every selected
  target remains unreached through 15 minutes, so the perfect separation is
  driven by S0-absent/S1-present versus S0-present/S1-present source ancestry.
  This is optimistic and closely aligned with the construction of the Phase-A
  labels.
- Input/target preparation cost is not measured comparably, and the sample is
  the reused diagnostic set, not an independent confirmation set.

Those limitations preserve a possible role for Delta-Aware as a fallback or
prefilter.  They do not rescue the current standalone positioning.

## What the other dynamic baselines say

Ordinary coverage monitoring does not replace the idea:

- Build-Only has 0% Recall.
- Overall Coverage Delta has 16.67% complete-case Recall.
- Changed-Code Coverage reaches 61.11% Recall but incurs 50% N4 FPR.
- Absolute S1 coverage is near random by ROC AUC, and its post-hoc F1-best
  threshold simply predicts every executable case positive.

Thus the negative decision is specifically caused by temporal target
reachability/attribution, not by degradation-style aggregate coverage.

## Phase-B gate

`task-6.md` permits Phase B only after a Phase-A CONTINUE.  Because this result
is MAJOR WEAKENING, no Phase-B data were selected or executed.  Running it
anyway would violate the experiment's gate.

The defensible research direction, if pursued separately, is a hybrid in which
automatic changed-target extraction and dynamic temporal validation are the
primary mechanism, with Delta-Aware evaluated only as a low-cost prefilter or
fallback for dynamic-unavailable/non-function cases.  That is a new claim and
is not retroactively tested here.
