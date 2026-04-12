# Heartbeat Test Mode Fixes — Design Spec

## Problem

4 of 8 heartbeat checks consistently fail in test mode (AI_MEMORY_TEST_MODE=true), making the heartbeat monitor unable to distinguish real regressions from known limitations. The 4 failing checks: `stability_increased`, `cold_memory_decayed`, `contradiction_resolved`, `cross_project_myelin`.

## Root Causes

### stability_increased
The heartbeat injects memories but never accesses them via search. `register_memory_access()` only fires on search hits, which increments `stability_score`. No search = no stability increase.

### cold_memory_decayed
`prune_cold_memories()` in REM requires `created_at < NOW() - INTERVAL '21 days'`. Memories are created seconds before deep sleep runs, so they never meet the age threshold.

### contradiction_resolved
The test-mode heuristic returns `b_wins`, which lowers mem_b's stability — this works correctly. But the check looks for `contradicts`/`derived_from` relations between the pair. The auto-linker creates a `supports` relation (hash embeddings see both as similar), and `b_wins` doesn't change relation types.

### cross_project_myelin
`strengthen_cross_project_myelin()` requires `last_accessed_at > NOW() - 24h` on both endpoints. Cross-project memories are injected but never searched, so `last_accessed_at` is NULL.

## Solution

### 1. Search after inject (monitor.py)

After injecting batch 1 (cluster) and batch 3 (cross-project), perform `POST /api/search/structured` queries that touch those memories. This sets `last_accessed_at` and increments `stability_score` via `register_memory_access()`.

### 2. Advance test clock before deep sleep (monitor.py)

Before triggering deep sleep, call `POST /api/test/clock` to advance time by 30 days. This makes cold memories eligible for `prune_cold_memories()` (age > 21 days). After verification, reset the clock to null.

**Guard:** Only manipulate the clock when `HEARTBEAT_MODE` suggests test environment or when the API confirms `test_mode=true`.

### 3. Improve contradiction_resolved check (checks.py)

In addition to looking for `contradicts`/`derived_from` relations, also check if mem_b (contra_1, the newer memory) has significantly lower `stability_score` than mem_a (contra_0). A ratio < 0.5 is the signature of `b_wins` resolution.

### 4. New client methods (client.py)

Add `set_test_clock(when: str | None)` and `structured_search(**kwargs)` to HeartbeatClient.

## Files Modified

- `heartbeat-monitor/client.py` — +2 methods
- `heartbeat-monitor/monitor.py` — search after inject, clock advance/reset
- `heartbeat-monitor/checks.py` — contradiction_resolved check improved

No changes to api-server or reflection-worker.

## Expected Outcome

All 8 checks pass in test mode after these changes. Pass rate goes from 50% to 100% in accelerated mode.
