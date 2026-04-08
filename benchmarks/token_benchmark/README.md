# Token Benchmark

Measures Claude Code token savings when using AI Memory MCP vs without it.

## Quick Start

```bash
# 1. Start the benchmark stack (isolated volumes)
docker compose -f docker-compose.yaml -f docker-compose.benchmark.yaml up -d --build

# 2. Run the benchmark
cd benchmarks/token_benchmark
./runner.sh

# 3. Or run specific tasks
./runner.sh --tasks T01,T02,T03

# 4. Skip seeding if data already loaded
./runner.sh --skip-seed
```

## How It Works

1. **Seed**: Loads 15 projects (~375 memories) into a clean AI Memory instance
2. **Execute**: For each of 15 tasks, you run the prompt in Claude Code twice:
   - Once **with** MCP connected (AI Memory available)
   - Once **without** MCP (`.mcp.json` disabled)
3. **Extract**: Parses token usage from Claude Code session logs (`~/.claude/projects/`)
4. **Report**: Generates comparison report with savings metrics

## Dataset

- **15 projects**: 8 energy/industrial + 7 software
- **~375 memories**: 20-25 per project (architecture, general, decisions, errors, sessions)
- **15 bridges**: Cross-project connections
- **35 relations**: Manual semantic links between memories

## Tasks (15)

| Category | Count | Examples |
|----------|-------|---------|
| Onboarding | 3 | Project overview, resume work, understand domain |
| Cross-project | 3 | Shared patterns, bridge discovery, tech reuse |
| Debugging | 3 | Known errors, cross-project error patterns |
| Decisions | 2 | Decision archaeology, pattern consistency |
| Consolidation | 2 | Portfolio status, knowledge gaps |
| Working memory | 2 | Task tracking, session continuity |

## Metrics

- **Token savings %**: Input, output, and total tokens with vs without MCP
- **Turn reduction %**: Fewer model round-trips needed
- **Cost estimate**: Projected USD savings based on Anthropic pricing
- **Per-category breakdown**: Which task types benefit most

## Files

| File | Purpose |
|------|---------|
| `catalog.py` | 15 projects with memories, bridges, relations |
| `tasks.py` | 15 benchmark tasks with prompts |
| `seed_benchmark.py` | Seeds dataset into AI Memory |
| `runner.sh` | Interactive benchmark orchestrator |
| `extract_tokens.py` | Parses Claude Code JSONL logs |
| `report.py` | Generates markdown + CSV reports |

## Isolated Environment

The benchmark uses separate Docker volumes via `docker-compose.benchmark.yaml`:
```bash
docker compose -f docker-compose.yaml -f docker-compose.benchmark.yaml up -d
```
This keeps benchmark data separate from your development data.

## Manual Scripts

```bash
# Seed only
python seed_benchmark.py --api-key YOUR_KEY

# Extract tokens from a completed run
python extract_tokens.py --run-dir results/20260408-120000

# Generate report from extracted data
python report.py --run-dir results/20260408-120000
```
