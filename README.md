# MicroArena — Multi-Venue Market Making and Optimal Execution

MicroArena is a self-contained, Python-standard-library-only research environment for designing, testing, and analyzing multi-venue electronic market-making strategies. It evaluates passive spread capture net of adverse selection, inventory drift, cancellation latency, venue outages, quote rejections, aggressive taker hedging, and transaction fees.

## Project Overview

- **Market Dataset (`data/`)**: 2,400 five-second ticks across three synthetic instruments (`ALPHA`, `BETA`, `GAMMA`) and two trading venues (`NORTH`, `SOUTH`), totaling **14,400 quote and trade-flow snapshots** alongside reference mid-prices (`reference_marks.csv`).
- **Event-Driven Simulator (`src/microarena/engine.py`)**: Discrete-tick execution engine featuring order acknowledgment delays, asynchronous cancellation races, partial fills, queue-ahead depletion, cash-and-inventory accounting, maker rebates, taker fees, terminal inventory liquidation, and hard risk/message limits.
- **Strategies (`src/microarena/`)**:
  - `baseline.py`: Reference symmetric top-of-book market maker (`NaiveSymmetricMaker`) with basic inventory skew and hedging.
  - `strategy.py`: Template entry point (`CandidateStrategy`) for implementing custom quoting and hedging logic.
- **Stress Scenarios (`src/microarena/scenarios.py`)**: 15 deterministic configurations (`base` plus 14 adverse regimes covering fee spikes, spread widening, depth depletion, order/cancel latency increases, single-venue outages, flow shocks, toxic flow, and mark gaps).
- **Research & Diagnostics (`src/microarena/research.py`)**: Utilities for EWMA smoothing, rolling volatility, book/flow imbalance, queue fill estimation, post-fill markout tables, PnL reconciliation, diagonal inventory VaR, moving-block bootstrap, order-to-fill ratios, and venue attribution.
- **Test Suite (`tests/`)**: 80 unit and integration tests covering data validation, simulator mechanics, risk constraints, stress configurations, research diagnostics, and ledger integrity.

## Directory Structure

```text
latency_market_making_8h/
├── README.md                  # Project documentation, commands, and test instructions
├── PROJECT_MANIFEST.json      # Dataset hashes and project configuration metadata
├── data/                      # Market stream CSV, reference marks CSV, and data manifest
├── docs/                      # Strategy API specification and market data dictionary
├── scripts/                   # CLI scripts for auditing, running simulations, and testing
├── src/microarena/            # Core simulator, strategies, metrics, scenarios, and research tools
└── tests/                     # Unit tests and synthetic test fixture generator
```

## Requirements

- **Python 3.10+**
- Zero third-party dependencies (uses the Python standard library only)
- No network access required

## Script Commands

Run all commands from the `latency_market_making_8h/` root directory:

### 1. Audit Dataset Integrity
Verifies SHA-256 file hashes, panel completeness (2,400 ticks × 6 symbol-venue pairs), and price ordering:
```bash
python scripts/audit_data.py
```

### 2. Run Baseline Simulations
Executes `NaiveSymmetricMaker` across four reference cases (`base`, `fees_3x`, `combined_crisis`, `north_down`) and writes equity, fills, orders, violations, and summary metrics to `outputs/baseline*`:
```bash
python scripts/run_baseline.py
```

### 3. Run Candidate or Baseline Strategy on a Single Scenario
Runs a selected strategy (`candidate` or `baseline`) on any scenario defined in `src/microarena/scenarios.py`:
```bash
# macOS / Linux
PYTHONPATH=src python -m microarena.runner --data data --strategy candidate --scenario base --out outputs/candidate

# Windows PowerShell
$env:PYTHONPATH = "src"
python -m microarena.runner --data data --strategy candidate --scenario base --out outputs/candidate
```

### 4. Run Full 15-Scenario Stress Suite
Evaluates either `candidate` or `baseline` across all 15 deterministic scenarios and saves aggregated metrics to `outputs/<strategy>_stress/stress_results.json`:
```bash
python scripts/run_stress.py --strategy baseline
python scripts/run_stress.py --strategy candidate
```

### 5. Analyze Run Diagnostics
Computes post-run toxicity markouts (1-, 5-, and 20-tick horizons), order/fill message efficiency, venue attribution, moving-block bootstrap PnL confidence intervals, and equity reconciliation:
```bash
python scripts/analyze_run.py --run outputs/baseline
```

### 6. Study Milestone Ledger (Optional)
Tracks staged research milestones, code revisions, test executions, and final evaluation runs in `outputs/study_ledger.jsonl`:
```bash
python scripts/study.py start
python scripts/study.py status
```

## Running Tests

Execute the full 80-test unit and integration suite via the helper script or Python's `unittest` runner:

```bash
python scripts/run_unit_tests.py
```

Or directly with `unittest`:

```bash
# macOS / Linux
PYTHONPATH=src python -m unittest discover -s tests -v

# Windows PowerShell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

## Further Documentation

- [`docs/STRATEGY_API.md`](docs/STRATEGY_API.md): `CandidateStrategy.on_tick(ctx)` interface, `Context` fields, per-tick execution lifecycle, and accounting rules.
- [`docs/MARKET_DATA.md`](docs/MARKET_DATA.md): Column definitions for `market_stream.csv` and `reference_marks.csv`, stress scenario parameters, and train/validation/test split boundaries (`0–1199` train, `1200–1799` validation, `1800–2399` test).
