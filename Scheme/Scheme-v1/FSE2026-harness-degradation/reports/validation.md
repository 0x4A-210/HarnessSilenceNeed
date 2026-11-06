# Validation report

Validated all 13 positive mappings (the requested 10–20-case audit sample).

- Projects: 10
- Commits in universe: 16155
- Positive degradation commits: 13
- Checks executed: 130
- Failed checks: 0

Each positive was checked for commit existence on current default-branch ancestry, exact UTC author time, first parent, temporal ordering at calendar-day resolution, archived coverage availability, an artifact event section that names the exact commit and cause, all original automatic coverage-drop predicates, before/after metric ordering, and explicit project-aggregate harness scope. Exact build time within an OSS-Fuzz report day is not published; attribution therefore comes from the artifact's two-judge case-study notes rather than an inferred intra-day ordering.

All checks passed.
