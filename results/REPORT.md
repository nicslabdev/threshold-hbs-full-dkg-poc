# MPC Benchmark Report — `sha256_full_column.mpc`

Analysis of the 30 logs in `results/` (`linear_n{1,2,4,8,16,32}_r{1..5}.log`):
6 configurations × 5 repetitions each. Fixed across all runs: `N_STEPS=16`,
`NUM_PARTIES=3`, protocol `semi-bin-party.x` (semi-honest, dishonest-majority,
GF(2)/binary-circuit MPC with OT-based Beaver triples), all three party
containers on a single Docker host (`mpc-net` bridge network). The swept
parameter is `N_COLUMNS` (the "`n`" in the filenames) — the number of
independent CRV columns generated sequentially in one MPC execution.

Per column, step 0 is a plain reveal (no MPC computation); steps 1–15 each
run one secure SHA‑256 evaluation. So `N_COLUMNS=n` means **15n secure
SHA‑256 evaluations** in total.

## Terminology: two different "rounds"

The logs contain two unrelated counters both called "rounds" — worth
separating clearly since they differ by a fixed factor and are easy to
conflate:

- **VM rounds** (`"X virtual machine rounds"`): a *static, protocol-level*
  count from the compiled bytecode — the number of sequential
  synchronization steps the circuit's Beaver-triple evaluation requires
  (essentially its multiplicative depth, summed over all columns). It is
  identical across all 3 parties and all 5 repetitions of a config — it's a
  property of the compiled program, not of the network or the run.
- **Communication rounds** (`"~Y rounds"` in `Data sent = ... in ~Y rounds`):
  the actual count of network round-trips each party's process performs.
  Reported **per party** and asymmetric: party 0 (the coordinator,
  `COORDINATOR_HOST`) talks to both peers, so its count is ~2× that of
  party 1 or party 2. Concretely, per config: `comm_rounds(p0) ≈ 4 ×
  vm_rounds` and `comm_rounds(p1) ≈ comm_rounds(p2) ≈ 2 × vm_rounds`. This is
  real network I/O; VM rounds is not.

Everywhere below, "VM rounds" and "communication rounds" are kept separate.

## Per-configuration summary (mean ± stdev over 5 runs)

Static/protocol counters below are **exactly identical across all 5 runs and
all 3 parties** for a given `n` (deterministic — not averages). Only `Time`
is a true wall-clock measurement and varies run to run.

| n (columns) | bit opens | bit triples (AND gates) | VM rounds | Global data sent (MB) | Time (s), mean ± stdev | Time min–max (s) |
|---:|---:|---:|---:|---:|---:|---:|
| 1  | 512    | 338,595    | 24,122  | 19.351  | 1.785 ± 0.235  | 1.562 – 2.066 |
| 2  | 1,024  | 677,190    | 48,242  | 35.522  | 3.924 ± 0.064  | 3.835 – 4.019 |
| 4  | 2,048  | 1,354,380  | 96,482  | 71.018  | 7.978 ± 1.018  | 6.130 – 8.980 |
| 8  | 4,096  | 2,708,760  | 192,962 | 138.856 | 16.794 ± 0.127 | 16.592 – 16.958 |
| 16 | 8,192  | 5,417,520  | 385,922 | 274.532 | 31.705 ± 1.163 | 30.012 – 32.958 |
| 32 | 16,384 | 10,835,040 | 771,842 | 549.038 | 75.978 ± 1.852 | 73.427 – 78.927 |

`bit inputs` (not tabulated) = `256 × n_steps × n_columns` per player =
`4096 × n`, trivially derivable and not independently informative.

### Per-party communication (mean, MB / communication rounds)

| n | Data sent — p0 (coordinator) | Data sent — p1 | Data sent — p2 | Comm rounds — p0 | Comm rounds — p1 | Comm rounds — p2 |
|---:|---:|---:|---:|---:|---:|---:|
| 1  | 6.517   | 6.417   | 6.417   | 96,602    | 48,349    | 48,338    |
| 2  | 11.974  | 11.774  | 11.774  | 193,172   | 96,669    | 96,648    |
| 4  | 23.939  | 23.539  | 23.539  | 386,330   | 193,325   | 193,282   |
| 8  | 46.819  | 46.019  | 46.019  | 772,628   | 386,621   | 386,536   |
| 16 | 92.577  | 90.978  | 90.978  | 1,545,224 | 773,213   | 773,044   |
| 32 | 185.145 | 181.946 | 181.946 | 3,090,434 | 1,546,413 | 1,546,074 |

`Global data sent` = `data_sent(p0) + data_sent(p1) + data_sent(p2)` exactly,
confirmed in every single run — it is a simple sum, not an independent
measurement.

## Scaling laws found (exact, not fits)

These held exactly across every one of the 30 runs, so they can be used to
predict cost at any `N_COLUMNS` without running MP-SPDZ:

- **AND-gate triples**: `bit_triples = 338,595 × n` exactly. `338,595 = 15 ×
  22,573`, i.e. one fixed-size Bristol-Fashion SHA‑256 circuit (22,573 AND
  gates) per hashed step, no shared cost between columns.
- **VM rounds**: `vm_rounds = 24,120 × n + 2`. `24,120 = 15 × 1,608` (SHA‑256
  circuit depth per hashed step). The **`+2` is paid once per run, not once
  per column** — columns share a 2-round setup cost instead of each paying
  it independently. This is the one place where the "sequential columns in
  a single execution" design measurably saves rounds versus running each
  column as a separate MPC job (which would cost `2n` instead of `2`).
- **bit opens**: `512 × n` exactly (`32 × n_steps` per column).
- **p0 vs. p1/p2 data-sent gap**: `data_sent(p0) − data_sent(p1) = 0.1 × n`
  MB exactly (100 KB of extra coordinator traffic per column — plausible
  per-column synchronization/relay overhead specific to being
  `COORDINATOR_HOST`).

## Derived metrics

**Cost per secure SHA‑256 evaluation** (divide by `15n`): constant by
construction for the deterministic counters —
- 22,573 triples, 1,608 VM rounds, ~34.1 KB global data per hash — regardless
  of `n`.

**Marginal cost per additional column**, from consecutive configs
(`Δglobal_data / Δn`):

| Interval | MB / column | 
|---|---:|
| 1→2   | 16.17 |
| 2→4   | 17.75 |
| 4→8   | 16.96 |
| 8→16  | 16.96 |
| 16→32 | 17.16 |

Converges to **~17.1 MB/column** once the small fixed per-run overhead
(≈2 MB, visible mainly at `n=1` where `global_data/n = 19.35` vs. the ~17.1
steady state) is amortized away.

**Throughput and per-hash wall-clock time** — this is where the picture
changes. Unlike the protocol counters above, `Time` does **not** scale
cleanly, and per-hash time actually *increases* with `n` instead of
improving from overhead amortization:

| n | Time/column (s) | Time/hash (s) | Columns/s | Hashes/s |
|---:|---:|---:|---:|---:|
| 1  | 1.785 | 0.1190 | 0.560 | 8.40 |
| 2  | 1.962 | 0.1308 | 0.510 | 7.65 |
| 4  | 1.995 | 0.1330 | 0.501 | 7.52 |
| 8  | 2.099 | 0.1400 | 0.476 | 7.15 |
| 16 | 1.982 | 0.1321 | 0.504 | 7.57 |
| 32 | 2.374 | 0.1583 | 0.421 | 6.32 |

Per-hash time rises from 0.119 s (`n=1`) to 0.158 s (`n=32`) — a ~33%
slowdown, not the improvement you'd expect if the only overhead were fixed
per-run setup. This means real wall-clock time is **not purely a function of
the deterministic protocol cost**: it also reflects the shared-host
environment (3 containers on one machine competing for CPU as compile size
and working-set grow with `n`). `stdev` supports this too — it's small and
tight at `n=1,2,8` (≤0.13 s) but much larger at `n=4,16,32` (1.0–1.9 s),
i.e. host-load noise, not protocol variance (triples/data/VM-rounds have
zero variance across runs; only wall time does). **Treat the deterministic
counters (triples, VM rounds, bytes) as the reliable cost model, and wall
time as a noisy, host-dependent measurement** — useful for a rough sense of
scale, not for precise extrapolation or cross-machine comparison.

## Extrapolation to `N_COLUMNS = 67`

No run in `results/` goes past `n=32`, so everything below is
extrapolated — `n=67` is nearly 2× beyond the largest measured point
(`n=32`), so treat this as an estimate, not a measurement. Two kinds of
quantities need two different treatments:

- **Deterministic counters** (opens, triples, VM rounds): plug `n=67` into
  the *exact* formulas from the previous section — no fitting involved,
  no error.
- **Communication (MB, comm rounds)**: these are also deterministic
  per-config (zero variance across the 5 runs) but not *exactly* linear —
  they carry a small fixed per-run offset on top of a per-column marginal
  cost. Fit `y = a + b·n` by least squares over the 6 known configs
  (`n=1,2,4,8,16,32`); fit quality is excellent (R² ≥ 0.999991), so the
  n=67 prediction should be accurate to a fraction of a percent.
- **Wall-clock time**: genuinely noisy (real variance across the 5 runs,
  driven by host contention, not the protocol) and its growth rate isn't
  perfectly linear in the data (per-hash time crept from 0.119 s at n=1 to
  0.158 s at n=32). This is the one number that needs a real regression fit
  with an honestly reported uncertainty band, not just a formula.

### Deterministic counters (exact)

| Metric | Formula | Value at n=67 |
|---|---|---|
| bit inputs / player | `4096 × n` | 274,432 |
| bit opens | `512 × n` | 34,304 |
| bit triples (AND gates) | `338,595 × n` | 22,685,865 |
| VM rounds | `24,120 × n + 2` | 1,616,042 |

### Communication — least-squares linear fit (near-exact, R² ≈ 0.99999)

| Metric | Fit | Predicted at n=67 |
|---|---|---|
| Global data sent | `1.99 + 17.086 × n` MB | **1146.7 MB** (≈ 1.12 GB) |
| Data sent — party 0 (coordinator) | `0.66 + 5.762 × n` MB | 386.7 MB |
| Data sent — party 1 | `0.66 + 5.662 × n` MB | 380.0 MB |
| Data sent — party 2 | `0.66 + 5.662 × n` MB | 380.0 MB |
| Comm rounds — party 0 | `25.2 + 96,575.2 × n` | ≈ 6,470,565 |
| Comm rounds — party 1 | `23.0 + 48,324.6 × n` | ≈ 3,237,774 |
| Comm rounds — party 2 | `22.7 + 48,314.1 × n` | ≈ 3,237,065 |

(Sanity check: 386.7 + 380.0 + 380.0 = 1146.7 MB, matching the independent
global-data fit — consistent, as it should be since `Global = p0+p1+p2`
held exactly in every run.)

### Wall-clock time — regression fit, not exact

Two models fit to the 6 config means (or equivalently all 30 individual
run times for the linear case — same fit):

| Model | Fit | R² | Predicted time(67) |
|---|---|---|---|
| Linear | `time = -1.805 + 2.365 × n` | 0.9935 | **156.6 s** (~2.6 min) |
| Quadratic | `time = 0.713 + 1.661×n + 0.0214×n²` | 0.9991 | 208.2 s (~3.5 min) |

Both fit the observed data well, but they diverge by ~33% once
extrapolated to n=67 — expected, since the quadratic term is small within
the measured range (n≤32) but dominates increasingly beyond it, and 3
parameters fit to 6 noisy points is easy to overfit. The residual scatter
around the *linear* fit gives a rough 1-sigma band of **[154, 159] s** and
2-sigma of **[152, 161] s** purely from run-to-run noise — but that band
does **not** cover the model-choice uncertainty above.

**Recommendation:** use **~155–160 s** as the point estimate (linear fit,
the more conservative and better-motivated model, since the deterministic
work — triples, rounds, bytes — is exactly linear in `n`), but don't
treat it as tighter than ±25%; the quadratic fit is a plausible upper
bound if host contention keeps worsening with size as it did between
n=16 and n=32.

### A real n=67 attempt already exists — and it crashed

Earlier project history (commit `c3fd4cb`, file `results/n16_c67_run1.log`,
since removed from the working tree but recoverable via `git show
c3fd4cb:results/n16_c67_run1.log`) contains an actual attempted run at
`N_COLUMNS=67`. Its printed counters match the exact formulas above
perfectly (34,304 bit opens; 22,685,865 triples; 1,616,042 VM rounds —
confirms the formulas independently), but **the run never finished**: one
party appears to have been OOM-killed during compilation, and the other
two are left in the log endlessly retrying
`getaddrinfo ... 'Name or service not known' for party0`. This matches the
exact failure mode the README already warns about ("Raising `N_COLUMNS`
too far will OOM-kill one of the containers during the compile step").
So the time/data predictions above assume the run *completes* on the
target host — on the machine that produced the original data, a bare
`N_COLUMNS=67` run previously did not, and would likely need more memory
headroom (or splitting into smaller batches of columns) before the
number above is achievable in practice.

## What this data cannot tell you

- **Online vs. offline phase split.** MP-SPDZ states benchmarks "are
  including preprocessing (offline phase)" — `Time` is a single blended
  number. Splitting it needs `-v` or per-phase counters, not present here.
- **Compile time**, separately from execution time — not logged at this
  granularity for these files (the `linear_*` logs only capture the
  `semi-bin-party.x` run, not the `compile.py` step).
- **CPU/memory usage** — not reported by MP-SPDZ at all.
- **Realistic network conditions.** All three parties share one Docker
  bridge network on one host: no bandwidth cap, near-zero RTT. Bytes sent
  and round counts are hardware-independent and portable; wall-clock time
  is specific to this box and not representative of a real distributed
  deployment.

## Appendix: raw per-run values

### Wall-clock time (s), all 3 parties per run (near-identical within a run)

| n | r1 | r2 | r3 | r4 | r5 |
|---:|---:|---:|---:|---:|---:|
| 1  | 1.562 | 1.652 | 1.590 | 2.065 | 2.056 |
| 2  | 4.019 | 3.959 | 3.912 | 3.892 | 3.836 |
| 4  | 6.130 | 7.924 | 8.980 | 8.510 | 8.347 |
| 8  | 16.785 | 16.874 | 16.760 | 16.592 | 16.956 |
| 16 | 32.769 | 32.958 | 30.864 | 31.920 | 30.013 |
| 32 | 75.492 | 75.490 | 73.428 | 76.553 | 78.927 |

(Values are the mean of the 3 parties' individually-logged `Time =` lines
for that run; parties agree to within a few ms per run.)

### Global data sent (MB) — identical across all 5 runs per config

| n | Global data sent (MB) |
|---:|---:|
| 1  | 19.351 |
| 2  | 35.522 |
| 4  | 71.018 |
| 8  | 138.856 |
| 16 | 274.532 |
| 32 | 549.038 |
