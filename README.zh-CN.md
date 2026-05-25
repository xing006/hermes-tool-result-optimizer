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
| **Dashboard 面板** | 实时总览：原始 vs 压缩后 token、按工具节省排行、调用明细 |
| **国际化** | 简体中文 + English，自动检测浏览器语言 |
| **零核心改动** | 纯插件钩子（`post_tool_call` + `transform_tool_result`），不动一行 Hermes 源码 |
| **LLM 摘要（可选）** | 默认关闭，白名单控制，不会对 terminal / patch / 代码输出做摘要 |


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
       ├─ 超过阈值? → preview_store: head + tail + 元信息
       │                原文落盘 (.txt)
       │
       └─ 小结果? → 原样通过
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
      min_chars: 8000
      preview_head_chars: 1000    # 保留命令上下文
      preview_tail_chars: 7000    # 保留输出和错误
    skill_view:
      min_chars: 8000
      preview_head_chars: 2500
      preview_tail_chars: 2500
    patch:
      min_chars: 16000            # diff 需要更多上下文
      preview_head_chars: 5000
      preview_tail_chars: 5000
    default:
      min_chars: 12000
      preview_head_chars: 3000
      preview_tail_chars: 3000
```

完整参考见 `config.example.yaml`。

---

## Dashboard 面板

插件在 Hermes Dashboard（`localhost:9119`）中添加 **Tool Result Tokens** 页签：

- **指标卡片：** 原始 tokens、压缩后 tokens、节省 tokens、已压缩调用数
- **排行诊断：** 最耗 token 的工具、节省最多的调用、压缩率偏低的工具、调用次数最多的工具
- **按工具汇总表：** 每个工具的调用次数、tokens、节省率、平均耗时
- **压缩策略：** 实时展示当前每个工具的阈值配置（模式、min_chars、头尾保留）
- **最近调用明细：** 每次调用的时间、工具名、会话 ID、调用 ID、原始→压缩对比、原文路径
- **语言：** 自动检测浏览器语言——简体中文和 English

---

## 工作原理

插件利用 Hermes 已有的插件系统注册两个钩子（零核心代码修改）：

1. **`post_tool_call`** —— 每次工具执行后触发。记录原始结果大小（字符数、估算 tokens、耗时）到本地 SQLite 数据库。

2. **`transform_tool_result`** —— 结果进入模型上下文前触发。如果结果超过阈值：
   - 原文完整存入磁盘（`~/.hermes/tool-result-optimizer/results/`）
   - 返回精简 JSON 包装，包含首尾预览和元信息
   - 模型可通过 `read_file` 读取原文

压缩后的结果示例：

```json
{
  "tool_result_optimized": true,
  "original_chars": 54321,
  "original_tokens_estimate": 13580,
  "compression_mode": "preview_store",
  "stored_path": "/home/user/.hermes/tool-result-optimizer/results/20260525-193001-web_extract-call_abc.txt",
  "preview": {
    "head": "开头 3000 字符...",
    "tail": "...末尾 3000 字符"
  }
}
```

---

## 路线图

| 阶段 | 状态 | 内容 |
|------|------|------|
| P0 | ✅ | 遥测 + 确定性压缩 + dashboard 总览 |
| P1 | ✅ | 诊断面板（排行、按工具详情）+ 压缩策略展示 |
| P1.5 | ✅ | Dashboard 国际化（简体中文 + English） |
| P2-1 | 📋 已计划 | LLM 摘要脚手架（配置、安全路由、准入逻辑） |
| P2-2 | ⏳ | 可选 LLM 摘要（白名单工具：web、browser、skill_view） |

---

## 许可证

MIT
