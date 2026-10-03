# Phase 10 performance baseline

## Method and environment

Measured 2026-09-13 on Windows 11 10.0.26200, Python 3.14.6, Node 24.18.0,
using `tests/performance/benchmark.py`. Synthetic files are deterministic,
side-effect-free, generated below ignored `tests/test-output/benchmarks`, and
removed after the run. Small and medium used three runs, dense/definition/partial
used two, and the large case used one due to its cost. There was no discarded
warm-up, so worst values include cold interpreter/filesystem effects. Times are
wall-clock milliseconds; memory is Python `tracemalloc` peak and excludes native
SQLite/Node allocations.

Graph construction currently includes symbol indexing and relationship resolution,
so those stages could not be measured independently without changing production
semantics. API response encoding/loopback transfer and browser paint were not
reliably isolated; database and frontend preparation measurements are reported
instead.

## Backend results

| Fixture | Runs | Files | Nodes | Edges | Scan median/worst | Parse median/worst | Resolve+graph median/worst | Validate median/worst | Serialize median/worst | SQLite write/read median | Peak MiB | JSON MiB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Small | 3 | 21 | 164 | 202 | 12/14 | 137/558 | 113/180 | 13/14 | 54/65 | 35/30 | 2.23 | 0.264 |
| Medium | 3 | 303 | 2,410 | 3,008 | 99/107 | 1,693/5,189 | 1,690/1,880 | 174/197 | 796/815 | 298/230 | 15.67 | 3.931 |
| Large | 1 | 1,515 | 12,046 | 15,044 | 518 | 25,534 | 11,721 | 1,361 | 5,465 | 2,187/1,835 | 80.88 | 19.672 |
| Dense cycle | 2 | 41 | 324 | 763 | 21/26 | 529/739 | 536/543 | 41/44 | 216/227 | 112/77 | 4.15 | 1.045 |
| Many definitions | 2 | 11 | 1,054 | 1,072 | 11/14 | 473/581 | 701/743 | 72/77 | 329/346 | 169/132 | 6.02 | 1.410 |
| Partial | 2 | 32 | 245 | 303 | 21/22 | 319/420 | 218/224 | 22/22 | 96/97 | 8/3 | 2.28 | 0.396 |

The 1,500-file measurement shows parsing and graph construction dominate cold
work; deterministic JSON also becomes material above 10,000 nodes. A repeated
sample analysis through the spawned-job integration returned the same stored graph
as a real cache hit without launching analysis work. Exact end-user cold/warm
latency varies with spawn, polling (750 ms default), filesystem cache, and machine.

## Frontend preparation

Node-based pure-module timing used three runs per deterministic graph. For 100
nodes normalization was 1.29–2.12 ms and layout 0.15–0.98 ms; for 1,000 nodes,
2.72–11.06 ms and 2.21–2.93 ms; for 5,000 nodes, 21.91–30.11 ms and
20.99–22.57 ms. These exclude React reconciliation, React Flow rendering, browser
paint, accessibility-tree construction, and device GPU cost. The existing canvas
warning therefore remains necessary despite inexpensive pure transforms.

## Unreliably measured items

Cancellation was functionally observed reaching `cancelled` but not statistically
timed. Peak whole-process/native memory, HTTP compression, browser initial paint,
API response time under concurrent load, database lock contention, disk-full
behavior, and formal p95/p99 latency require dedicated Phase 11/operational rigs.
