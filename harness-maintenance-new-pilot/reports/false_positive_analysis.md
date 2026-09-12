# False-positive analysis

On the audited subset, Gap-Only produced 28 FP among 40 negatives (70% FPR).
Fifteen were source+harness co-evolution commits without a commit-induced gap,
11 were source-only internal changes with an existing or merely apparent gap,
one was a valid-flow protocol change with no adequacy delta, and one was a
historical build gap.

Evolution-Aware reduced this to one FP (2.5% FPR), C040. Its source commit
removed private chunk-limit declarations and H1 stopped including `common.h`.
The model noticed that S1+H0 had a new undeclared-call failure, but the
three-way probe showed S0+H0 already failed because `common.h` was not valid in
that C++ translation unit. With adequacy already at build failure, the current
commit did not establish a further loss. This is exactly the historical-gap
attribution failure the second stage was intended to prevent.

Twenty-seven negative cases moved from Gap-Only YES to Evolution-Aware NO; none
moved from Gap-Only NO to an Evolution-Aware false positive. The improvement is
therefore attributable to the attribution stage rather than a global tendency
to answer NO.

Five representative Gap-Only FPs are expanded in `case_studies.md`: C005,
C031, C040, C059, and C064.
