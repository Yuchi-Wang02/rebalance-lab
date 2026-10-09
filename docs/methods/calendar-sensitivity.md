# Calendar-phase sensitivity

The primary experiment compares monthly selection with March/September selection. This supplementary check asks whether that comparison is unusually dependent on the chosen semiannual months. It changes only the slow portfolio's scheduled selection months and reports every permitted phase.

This is a within-study robustness check using shared observations, not independent replication. March/September remains the primary reference even if another schedule produces a more favorable outcome. No schedule is selected for trading from this exercise.

## Prespecified schedules

| Phase | Semiannual signal closes | Role |
|---|---|---|
| 01 / 07 | January and July month-end | Sensitivity |
| 02 / 08 | February and August month-end | Sensitivity |
| 03 / 09 | March and September month-end | Primary reference |
| 04 / 10 | April and October month-end | Sensitivity |
| 05 / 11 | May and November month-end | Sensitivity |
| 06 / 12 | June and December month-end | Sensitivity |

The machine-readable [supplementary specification](../../configs/calendar-sensitivity.v1.json) pins the primary configuration hash, all six phases, both signal pairs and all four cost scenarios. The [primary configuration](../../configs/experiment.v1.json) and its original 16 paths remain unchanged.

Every phase uses the same cash initialization, December 31, 2024 initial signal, 2025 burn-in, December 31, 2025 reporting anchor and October 2, 2026 endpoint. Trades occur at the next supplied session's opening price. Initial formation, forced exits and dividend maintenance remain common exceptions to the scheduled calendar. Normalization at the reporting anchor does not trigger a new trade. A December month-end signal can still execute at the following January open.

## Comparisons and reporting

For each cost assumption (0, 5, 10 and 25 basis points per side):

- Compare the same M12 monthly control with six S12 phase portfolios.
- Compare the same MMIX monthly control with six SMIX phase portfolios.

This produces **8 unique monthly controls, 48 semiannual paths and 48 paired comparison rows**. Each monthly control is computed once and referenced by six rows; it is not six independent observations. The supplementary execution has 56 unique paths in total, including the March/September reference paths.

The private comparison table retains net-return differences in percentage points, both drawdowns and their difference, both turnover measures and additional turnover, and both modeled fees and additional fees. Positive drawdown difference means the monthly portfolio's drawdown is less negative. Review these together with cash exposure and holdings changes. Report the full phase distribution and identify the primary reference; an average or range cannot manufacture independent statistical evidence.

Fee sensitivity uses fully rerun portfolio paths. A hypothetical cost crossover requires further explicitly computed cost scenarios; it cannot be assumed from the website's linear fee illustration because fees can affect later holdings and trades.

## Run the synthetic implementation

From the repository root, with Python 3.12+ and no external dependencies:

```bash
python3 scripts/run_calendar_sensitivity.py --output-dir results/generated/calendar-sensitivity
```

To refresh the public engineering receipt after a reviewed code change:

```bash
python3 scripts/run_calendar_sensitivity.py \
  --output-dir results/generated/calendar-sensitivity \
  --public-summary site/data/calendar-sensitivity-status.json
```

The runner creates a new directory for each execution. It saves separate result JSON/CSV files for each unique path, a `phase_table.json`/`.csv` linking both sides of every comparison, and a manifest identifying the fixture, configurations, code and output hashes. Detailed fictional performance stays in ignored `results/generated/`. The optional public receipt contains only counts, checks, scope and hashes.

Every output is labeled `data_track=synthetic` and `experiment_track=calendar_phase_sensitivity`. The prototype accepts only the fixed phases, rejects a phase override on the primary track and rejects a phase override for monthly controls. Tests check March/September equivalence to the primary engine and preserve the original account timeline.

The fixture uses fictional securities, prices and a weekday calendar with artificial closures. Passing it demonstrates specified software behavior. A market version still requires audited historical membership, capitalization, prices, action settlement and exchange sessions. The current run does not resolve those requirements or answer which schedule performed best in the real market.
