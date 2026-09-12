# False-positive analysis

## Gap-Only

Gap-Only produced 22 false positives among 50 valid negatives (44% FPR):

- 18/33 source-only controls;
- 4/17 source/harness co-evolution hard negatives;
- by negative taxonomy: N3=9, N1=8, N5=3, N6=2.

The dominant pattern is failure to attribute a visible gap to the current
commit. On side-subsystem controls, Gap-Only often notices that the displayed
H0 targets another codec/subsystem and reports a genuine repository-level gap,
even though the production change did not create it. On internal refactors and
error-handling changes, it frequently treats an uncalled private helper,
boundary branch, or configuration distinction as requiring a harness update
without checking whether H0 already reaches the behavior through the existing
public path.

The hard-negative FPR (23.53%) is materially lower than the source-only-control
FPR (54.55%) but remains too high for triage. This confirms that the overall
44% is not solely an artifact of easy side-subsystem controls.

## Evolution-Aware

Evolution-Aware produced 0/50 FP overall and 0/17 on hard negatives. It set
`gap_exists=true` on a number of cases but then correctly set
`commit_induced=NO`, which is exactly the intended attribution behavior.

The measured FP reduction is 100%. This is a strong signal that evolution
attribution matters, but it should not be generalized without qualification:
there are no preregistered N4 existing-gap negatives, 33/50 negatives are
source-only controls, and 46/50 valid negatives are Wuffs cases.

## Existing-gap diagnostic

Formal `existing_gap_fp` is `NOT_ESTIMABLE` because N4 has denominator zero.
After reveal, N223 and N231 were invalidated because their decoder gaps already
existed at S0+H0. Gap-Only flagged both while Evolution-Aware rejected both.
That observation is consistent with the attribution hypothesis, but it is
post-hoc and is not reported as a formal N4 rate.
