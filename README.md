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
| **Per-tool strategy** | Independent thresholds and preview sizes for terminal, web_extract, skill_view, browser, patch, and more |
| **Dashboard tab** | Real-time overview: raw vs compressed tokens, per-tool savings, recent call details, top rankings |
| **i18n** | English and Simplified Chinese UI — auto-detects browser locale |
| **No core changes** | Pure plugin hooks (`post_tool_call` + `transform_tool_result`), zero Hermes source modification |
| **LLM summarization** | Configurable and disabled by default — whitelist-only, never for terminal/patch/code |


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
       ├─ large? (> threshold) → preview_store: head + tail + metadata
       │                          full original → disk (.txt)
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
      min_chars: 8000
      preview_head_chars: 1000    # keep command context
      preview_tail_chars: 7000    # preserve output/errors
    skill_view:
      min_chars: 8000
      preview_head_chars: 2500
      preview_tail_chars: 2500
    patch:
      min_chars: 16000            # diffs need more context
      preview_head_chars: 5000
      preview_tail_chars: 5000
    default:
      min_chars: 12000
      preview_head_chars: 3000
      preview_tail_chars: 3000
```

See `config.example.yaml` for the full reference.

---

## Dashboard

The plugin adds a **Tool Result Tokens** tab in your Hermes Dashboard (`localhost:9119`):

- **Metric cards:** raw tokens, compressed tokens, saved tokens, compressed calls count
- **Top rankings:** most token-hungry tools, most saved calls, low savings tools, most called tools
- **By-tool table:** per-tool breakdown with calls, tokens, savings rate, avg duration
- **Compression policy:** live view of configured per-tool thresholds (mode, min_chars, head, tail)
- **Recent calls:** per-call log with tool, session, call ID, raw→compressed comparison, stored path
- **Language:** auto-detects browser locale — English and Simplified Chinese

---

## How it works

The plugin registers two hooks into Hermes's existing plugin system (no core changes):

1. **`post_tool_call`** — fires after each tool execution. Records the raw tool result (chars, token estimate, duration) to a local SQLite database.

2. **`transform_tool_result`** — fires before the result enters the model context. If the result exceeds the threshold, it:
   - Stores the full original text to disk (`~/.hermes/tool-result-optimizer/results/`)
   - Returns a compact JSON wrapper with head/tail preview + metadata
   - The model can `read_file` the original if needed

The compressed result looks like:

```json
{
  "tool_result_optimized": true,
  "original_chars": 54321,
  "original_tokens_estimate": 13580,
  "compression_mode": "preview_store",
  "stored_path": "/home/user/.hermes/tool-result-optimizer/results/20260525-193001-web_extract-call_abc.txt",
  "preview": {
    "head": "First 3000 chars...",
    "tail": "...Last 3000 chars"
  }
}
```

---

## Roadmap

| Phase | Status | What |
|-------|--------|------|
| P0 | ✅ | Telemetry + deterministic compression + dashboard summary |
| P1 | ✅ | Diagnosis panel (top N, per-tool details) + compression policy display |
| P1.5 | ✅ | Dashboard i18n (简体中文 + English) |
| P2-1 | 📋 Planned | LLM summary scaffolding (config, safety routing, eligibility) |
| P2-2 | ⏳ | Optional LLM summarization for whitelist tools (web, browser, skill_view) |

---

## License

MIT
