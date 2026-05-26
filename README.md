# Hermes Tool Result Optimizer

<p align="center">
  <a href="README.zh-CN.md"><img src="https://img.shields.io/badge/Lang-中文-red?style=for-the-badge" alt="中文"></a>
  <a href="https://github.com/xing006/hermes-tool-result-optimizer/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License: MIT"></a>
  <a href="https://github.com/xing006/hermes-tool-result-optimizer"><img src="https://img.shields.io/badge/GitHub-hermes--tool--result--optimizer-181717?style=for-the-badge&logo=github" alt="GitHub"></a>
</p>

**Hermes Agent plugin that observes and compresses large tool results before they enter the model context** — cuts token waste without touching a single line of Hermes core.

---

## Features

| Capability | Description |
|------------|-------------|
| **Telementry** | Records raw tool result size, duration, and token estimate for every call |
| **Deterministic compression** | Threshold-based head/tail preview with original stored to disk — no information lost |
| **Per-tool strategy** | Independent thresholds per tool; **terminal_evidence** (preserves exit code, error lines, stdout/stderr tail, final summary) for terminal, **patch_diff_evidence** (hunk-aware diff with risk markers) for patch, preview_store for reading tools |
| **Dashboard** | Real-time overview with token trend chart, per-tool/mode breakdown, compression policy display, and recent calls detail |
| **No core changes** | Pure plugin hooks (`post_tool_call` + `transform_tool_result`), zero Hermes source modification |


## Architecture

```
Agent tool call
       │
       ▼
post_tool_call (hook) ─────► record raw size/time/tokens into SQLite
       │
       ▼
transform_tool_result (hook)
       │
       ├─ terminal? (> 40K) → terminal_evidence: exit code, error lines, tail, summary
       │                       full original → disk (.txt)
       ├─ patch? (> 40K) → patch_diff_evidence: hunk-aware diff, risk markers
       │                    full original → disk (.txt)
       ├─ preview_store (> threshold) → head + tail + metadata
       │                                full original → disk (.txt)
       │
       └─ small? → pass through unchanged
       │
       ▼
Model receives compact JSON wrapper (or raw result)
       │
       ▼
Dashboard (port 9119) ──► /api/plugins/tool-result-optimizer/summary ──► SQLite
                       ──► /api/plugins/tool-result-optimizer/policy  ──► Config
```

---

## Installation

### 1. Place in Hermes plugin directory

```bash
# Windows (MSYS/bash)
cp -r hermes-tool-result-optimizer $HERMES_HOME/plugins/tool-result-optimizer
```

Or create a symlink to keep the project directory as the source of truth:

```bash
ln -s /path/to/hermes-tool-result-optimizer $HERMES_HOME/plugins/tool-result-optimizer
```

### 2. Enable in Hermes config

Add to `config.yaml` (under your Hermes profile):

```yaml
plugins:
  enabled:
    - tool-result-optimizer
```

### 3. Restart Hermes

```bash
hermes reset          # reload plugins
hermes dashboard --stop && hermes dashboard --port 9119  # reload dashboard
```

---

## Configuration

All settings are in `config.yaml` under `tool_result_optimizer`:

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `true` | Master switch |
| `compression.enabled` | `true` | Enable head/tail preview compression |
| `compression.min_chars` | `12000` | Threshold in characters |
| `compression.mode` | `preview_store` | Compression mode (`preview_store`) |
| `storage.retention_days` | `14` | Original result file retention |

Per-tool overrides:

```yaml
tool_result_optimizer:
  tools:
    terminal:
      mode: terminal_evidence
      success_min_chars: 40000          # compress successful output > 40K chars
      failure_min_chars: 80000           # compress failed output > 80K chars
      stdout_head_chars: 1000
      stdout_tail_chars: 4000
      stderr_tail_chars: 8000
    patch:
      mode: patch_diff_evidence
      success_min_chars: 40000           # compress diffs > 40K chars
      first_hunks_per_file: 2
      last_hunks_per_file: 1
      max_hunks_per_file: 8
      max_hunk_chars: 12000
    skill_view:
      min_chars: 8000
      preview_head_chars: 2500
      preview_tail_chars: 2500
    default:
      min_chars: 12000
      mode: preview_store
      preview_head_chars: 3000
      preview_tail_chars: 3000
```

See `config.example.yaml` for the full reference.

---

## Dashboard

The plugin adds a **Tool Result Tokens** tab in your Hermes Dashboard (`localhost:9119`):

- **Token trend chart:** SVG line+bar chart showing raw vs compressed tokens over time — hourly buckets for Today, daily for 3/10/30 days. Hover for tooltip with bucket, calls, raw/compressed/saved tokens, and savings rate.
- **Metric cards:** raw tokens, compressed tokens, saved tokens, compressed calls count
- **Top rankings:** most token-hungry tools, most saved calls, low savings tools, most called tools
- **By compression mode table:** grouped by `preview_store` / `terminal_evidence` / `patch_diff_evidence` / `raw`
- **By-tool table:** per-tool breakdown with mode, calls, tokens, savings rate, avg duration
- **Compression policy:** live view of configured per-tool thresholds (mode, min_chars, head, tail)
- **Recent calls:** per-call log with tool, session, call ID, compression mode pill, evidence column (terminal status/exit_code, patch files/hunks/risk markers), raw→compressed comparison, stored path
- **Time range:** Today / 3 days / 10 days / 30 days — calendar-day aligned (not rolling window)
- **Language:** auto-detects browser locale — English and Simplified Chinese

---

## How it works

The plugin registers two hooks into Hermes's existing plugin system (no core changes):

1. **`post_tool_call`** — fires after each tool execution. Records the raw tool result (chars, token estimate, duration) to a local SQLite database.

2. **`transform_tool_result`** — fires before the result enters the model context. If the result exceeds the threshold, it:
   - Stores the full original text to disk (`~/.hermes/tool-result-optimizer/results/`)
   - Returns a compact JSON wrapper with head/tail preview + metadata
   - The model can `read_file` the original if needed

The compressed result for a terminal command looks like:

```json
{
  "tool_result_optimized": true,
  "tool_name": "terminal",
  "compression_mode": "terminal_evidence",
  "original_chars": 84210,
  "stored_path": "/home/user/.hermes/tool-result-optimizer/results/20260525-193001-terminal-call_abc.txt",
  "evidence": {
    "status": "failed",
    "exit_code": 1,
    "stdout_head": "...",
    "stdout_tail": "...",
    "stderr_tail": "...",
    "error_lines": ["AssertionError: ..."],
    "warning_lines": ["DeprecationWarning: ..."],
    "final_lines": ["FAILED test_foo"]
  },
  "note": "Original terminal output was compressed before entering model context. Use read_file on stored_path if exact output is needed."
}
```

---

## Roadmap

| Phase | Status | What |
|-------|--------|------|
| P0 | ✅ | Telemetry + deterministic compression + dashboard summary |
|| P1 | ✅ | Diagnosis panel (top N, per-tool details) + compression policy display |
| P1.5 | ✅ | Dashboard i18n (简体中文 + English) |
| P2 | ✅ | terminal_evidence + patch_diff_evidence compression modes |
| P2.5 | ✅ | Dashboard trend chart, by_mode grouping, evidence columns, calendar-day time filter |


## License

MIT
