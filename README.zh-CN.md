# Hermes Tool Result Optimizer

<p align="center">
  <a href="README.md"><img src="https://img.shields.io/badge/Lang-English-lightgrey?style=for-the-badge" alt="English"></a>
  <a href="https://github.com/xing006/hermes-tool-result-optimizer/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License: MIT"></a>
  <a href="https://github.com/xing006/hermes-tool-result-optimizer"><img src="https://img.shields.io/badge/GitHub-hermes--tool--result--optimizer-181717?style=for-the-badge&logo=github" alt="GitHub"></a>
</p>

**Hermes Agent 插件，观测并压缩大型工具结果，在进入模型上下文前大幅减少 token 消耗** —— 不修改任何 Hermes 核心代码。

---

## 特性

| 能力 | 说明 |
|------|------|
| **全量遥测** | 每次工具调用记录原始长度、耗时、预估 token 数 |
| **确定性压缩** | 基于阈值的首尾预览 + 原文入盘，不丢信息 |
| **按工具独立策略** | terminal / web_extract / skill_view / browser / patch 各有不同的阈值和裁剪长度 |
| **terminal_evidence** | 终端输出证据保留压缩——保留 exit code、错误行、stdout/stderr 尾部、告警行和最终摘要 |
| **patch_diff_evidence** | Diff hunk 感知压缩——按 `@@ ... @@` 边界裁剪，优先保留风险 hunk（token/auth/config 变更），计数每文件省略的 hunk 数 |
| **Dashboard 趋势图** | SVG 折线+柱状图展示原始 vs 压缩后 token 随时间变化——今日按小时、3/10/30 日按天聚合 |
| **Dashboard 证据列** | 每行显示压缩模式药丸、terminal 状态/exit_code、patch 文件数/hunks/风险标记 |
| **Dashboard 面板** | 实时总览：原始 vs 压缩后 token、按工具节省排行、调用明细 |
| **国际化** | 简体中文 + English，自动检测浏览器语言 |
| **零核心改动** | 纯插件钩子（`post_tool_call` + `transform_tool_result`），不动一行 Hermes 源码 |
| |

## 架构

```
Agent 工具调用
       │
       ▼
post_tool_call (钩子) ────► 记录原始大小/耗时/tokens 到 SQLite
       │
       ▼
transform_tool_result (钩子)
       │
       ├─ terminal (> 40K) → terminal_evidence: exit code、错误行、尾部、摘要
       │                      原文落盘 (.txt)
       ├─ patch (> 40K) → patch_diff_evidence: hunk 感知 diff、风险标记
       │                   原文落盘 (.txt)
       ├─ preview_store (超过阈值) → head + tail + 元信息
       │                            原文落盘 (.txt)
       │
       └─ 小结果 → 原样通过
       │
       ▼
模型收到精简 JSON 包装（或原始结果）
       │
       ▼
Dashboard (9119 端口) ──► /api/plugins/tool-result-optimizer/summary ──► SQLite
                       ──► /api/plugins/tool-result-optimizer/policy  ──► 配置
```

---

## 安装

### 1. 放入 Hermes 插件目录

```bash
# Windows (MSYS/bash)
cp -r hermes-tool-result-optimizer $HERMES_HOME/plugins/tool-result-optimizer
```

或用符号链接保持项目目录作为主版本：

```bash
ln -s /path/to/hermes-tool-result-optimizer $HERMES_HOME/plugins/tool-result-optimizer
```

### 2. 在 Hermes 配置中启用

在 `config.yaml`（你的 Hermes profile 下）加入：

```yaml
plugins:
  enabled:
    - tool-result-optimizer
```

### 3. 重启 Hermes

```bash
hermes reset          # 重新加载插件
hermes dashboard --stop && hermes dashboard --port 9119  # 重载 dashboard
```

---

## 配置项

所有配置放在 `config.yaml` 的 `tool_result_optimizer` 下：

| 键 | 默认值 | 说明 |
|------|---------|------|
| `enabled` | `true` | 总开关 |
| `compression.enabled` | `true` | 启用首尾预览压缩 |
| `compression.min_chars` | `12000` | 触发压缩的字符数阈值 |
| `compression.mode` | `preview_store` | 压缩模式（当前仅 preview_store） |
| `storage.retention_days` | `14` | 原文文件保留天数 |

按工具覆盖：

```yaml
tool_result_optimizer:
  tools:
    terminal:
      mode: terminal_evidence
      success_min_chars: 40000          # 成功输出超过 40K 字符时压缩
      failure_min_chars: 80000           # 失败输出超过 80K 字符时压缩
      stdout_head_chars: 1000
      stdout_tail_chars: 4000
      stderr_tail_chars: 8000
    patch:
      mode: patch_diff_evidence
      success_min_chars: 40000           # diff 超过 40K 字符时压缩
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

完整参考见 `config.example.yaml`。

---

## Dashboard 面板

插件在 Hermes Dashboard（`localhost:9119`）中添加 **Token优化看板** 页签：

- **Token 趋势图：** SVG 折线+柱状图展示原始 vs 压缩后 token 随时间变化——今日按小时、3/10/30 日按天聚合，hover 显示详情
- **指标卡片：** 原始 tokens、压缩后 tokens、节省 tokens、已压缩调用数
- **排行诊断：** 最耗 token 的工具、节省最多的调用、压缩率偏低的工具、调用次数最多的工具
- **按压缩模式汇总：** 按 `preview_store` / `terminal_evidence` / `patch_diff_evidence` / `raw` 分组
- **按工具汇总表：** 每个工具的模式、调用次数、tokens、节省率、平均耗时
- **压缩策略：** 实时展示当前每个工具的阈值配置（模式、min_chars、头尾保留）
- **最近调用明细：** 每次调用的时间、工具名、会话 ID、调用 ID、压缩模式药丸、证据列（terminal 状态/exit_code、patch 文件数/hunks/风险标记）、原始→压缩对比、原文路径
- **时间范围：** 今日 / 3日 / 10日 / 30日——自然日对齐（非滚动窗口）
- **语言：** 自动检测浏览器语言——简体中文和 English

---

## 工作原理

插件利用 Hermes 已有的插件系统注册两个钩子（零核心代码修改）：

1. **`post_tool_call`** —— 每次工具执行后触发。记录原始结果大小（字符数、估算 tokens、耗时）到本地 SQLite 数据库。

2. **`transform_tool_result`** —— 结果进入模型上下文前触发。如果结果超过阈值：
   - 原文完整存入磁盘（`~/.hermes/tool-result-optimizer/results/`）
   - 返回精简 JSON 包装，包含首尾预览和元信息
   - 模型可通过 `read_file` 读取原文

压缩后的 terminal 输出示例：

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

## 路线图

| 阶段 | 状态 | 内容 |
|------|------|------|
| P0 | ✅ | 遥测 + 确定性压缩 + dashboard 总览 |
| P1 | ✅ | 诊断面板（排行、按工具详情）+ 压缩策略展示 |
| P1.5 | ✅ | Dashboard 国际化（简体中文 + English） |
| P2 | ✅ | terminal_evidence + patch_diff_evidence 压缩模式 |
| P2.5 | ✅ | Dashboard 趋势图、按模式分组、证据列、自然日时间过滤 |


## 许可证

MIT
