(function () {
  "use strict";
  const SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK) return;
  const React = SDK.React;
  const h = React.createElement;
  const hooks = SDK.hooks;
  const fetchJSON = SDK.fetchJSON;
  const Button = SDK.components && SDK.components.Button;
  const useI18n = SDK.useI18n;

  const I18N = {
    en: {
      title: "Tool Result Tokens",
      subtitle: "Diagnostics for raw vs compressed tool result token estimates.",
      refresh: "Refresh",
      rawTokens: "Raw tokens",
      compressedTokens: "Compressed tokens",
      savedTokens: "Saved tokens",
      compressedCalls: "Compressed calls",
      savedSuffix: "saved",
      avgPrefix: "avg",
      topRankings: "Top rankings",
      mostTokenHungryTools: "Most token-hungry tools",
      mostSavedCalls: "Most saved calls",
      lowSavingsTools: "Low savings tools",
      mostCalledTools: "Most called tools",
      byTool: "By tool",
      compressionPolicy: "Compression policy",
      recentCalls: "Recent calls",
      loading: "Loading...",
      tool: "Tool",
      calls: "Calls",
      raw: "Raw",
      compressed: "Compressed",
      saved: "Saved",
      rate: "Rate",
      compressedCallsCol: "Compressed calls",
      avgMs: "Avg ms",
      mode: "Mode",
      minChars: "Min chars",
      head: "Head",
      tail: "Tail",
      time: "Time",
      session: "Session",
      call: "Call",
      chars: "Chars",
      stored: "Stored",
      enabled: "enabled",
      telemetry: "telemetry",
      compression: "compression",
      storage: "storage",
      retention: "retention",
      compressedMode: "compressed",
      rawMode: "raw",
      timeRange: "Time range",
      rangeToday: "Today",
      range3d: "3 days",
      range10d: "10 days",
      range30d: "30 days",
      showing: "Showing",
      prev: "← Prev",
      next: "Next →",
      db: "DB",
      byMode: "By compression mode",
      evidence: "Evidence",
      tokenTrend: "Token trend",
      rawLine: "Raw",
      compressedLine: "Compressed",
      savedBar: "Saved",
      noTrend: "No data for trend",
      bucket: "Bucket",
      callsLabel: "Calls"
    },
    "zh-CN": {
      title: "Token优化看板",
      subtitle: "查看工具结果压缩前后的 token 估算、节省量和异常点。",
      refresh: "刷新",
      rawTokens: "原始 tokens",
      compressedTokens: "压缩后 tokens",
      savedTokens: "节省 tokens",
      compressedCalls: "已压缩调用",
      savedSuffix: "已节省",
      avgPrefix: "平均",
      topRankings: "排行诊断",
      mostTokenHungryTools: "最耗 token 的工具",
      mostSavedCalls: "节省最多的调用",
      lowSavingsTools: "压缩率偏低的工具",
      mostCalledTools: "调用次数最多的工具",
      byTool: "按工具汇总",
      compressionPolicy: "压缩策略",
      recentCalls: "最近调用明细",
      loading: "加载中...",
      tool: "工具",
      calls: "调用次数",
      raw: "原始",
      compressed: "压缩后",
      saved: "节省",
      rate: "节省率",
      compressedCallsCol: "压缩次数",
      avgMs: "平均耗时 ms",
      mode: "模式",
      minChars: "最小字符数",
      head: "头部保留",
      tail: "尾部保留",
      time: "时间",
      session: "会话",
      call: "调用",
      chars: "字符数",
      stored: "原文路径",
      enabled: "启用",
      telemetry: "遥测",
      compression: "压缩",
      storage: "存储",
      retention: "保留",
      compressedMode: "已压缩",
      rawMode: "原始",
      timeRange: "时间范围",
      rangeToday: "今日",
      range3d: "3日",
      range10d: "10日",
      range30d: "30日",
      showing: "显示",
      prev: "← 上一页",
      next: "下一页 →",
      db: "数据库",
      byMode: "按压缩模式汇总",
      evidence: "证据",
      tokenTrend: "Token 趋势",
      rawLine: "原始",
      compressedLine: "压缩后",
      savedBar: "节省",
      noTrend: "暂无趋势数据",
      bucket: "时间段",
      callsLabel: "调用次数"
    }
  };

  function detectLocale(ctx) {
    const raw = String((ctx && ctx.locale) || window.__HERMES_LOCALE__ || navigator.language || "en");
    return raw.toLowerCase().startsWith("zh") ? "zh-CN" : "en";
  }
  function makeTranslator(locale) {
    const pack = I18N[locale] || I18N.en;
    return function t(key) {
      return pack[key] || I18N.en[key] || key;
    };
  }
  function fmt(n) {
    n = Number(n || 0);
    return n.toLocaleString();
  }
  function pct(saved, raw) {
    raw = Number(raw || 0); saved = Number(saved || 0);
    if (!raw) return "0%";
    return ((saved / raw) * 100).toFixed(1) + "%";
  }
  function time(ts) {
    if (!ts) return "";
    return new Date(ts * 1000).toLocaleString();
  }
  function shortId(s) {
    s = String(s || "");
    if (s.length <= 12) return s;
    return s.slice(0, 6) + "…" + s.slice(-4);
  }
  function evidenceText(r) {
    const mode = String(r.compression_mode || (r.changed ? "compressed" : "raw"));
    if (mode === "terminal_evidence") {
      const bits = [];
      if (r.terminal_status) bits.push("status=" + r.terminal_status);
      if (r.terminal_exit_code !== null && r.terminal_exit_code !== undefined && r.terminal_exit_code !== "") bits.push("exit=" + r.terminal_exit_code);
      return bits.join(" · ");
    }
    if (mode === "patch_diff_evidence") {
      const bits = [];
      if (r.patch_files_changed !== null && r.patch_files_changed !== undefined) bits.push("files=" + r.patch_files_changed);
      if (r.patch_hunks_omitted !== null && r.patch_hunks_omitted !== undefined) bits.push("omitted=" + r.patch_hunks_omitted);
      if (r.patch_syntax_check) bits.push("syntax=" + r.patch_syntax_check);
      if (r.patch_risk_markers) bits.push("risk=" + r.patch_risk_markers);
      return bits.join(" · ");
    }
    return "";
  }
  function TokenTrendChart(props) {
    var rows = props.rows, t = props.t;
    var useState = hooks.useState;
    var tipSt = useState(null);
    var tip = tipSt[0], setTip = tipSt[1];
    if (!rows || rows.length === 0) {
      return h("div", { className: "tro-chart-card" }, h("div", { className: "tro-chart-empty" }, t("noTrend")));
    }
    var W = 680, H = 200, ML = 56, MR = 12, MT = 8, MB = 44;
    var PW = W - ML - MR, PH = H - MT - MB;
    var maxVal = 0;
    rows.forEach(function (r) { maxVal = Math.max(maxVal, r.raw_tokens, r.compressed_tokens + r.saved_tokens); });
    maxVal = Math.ceil(maxVal * 1.1) || 1;
    function ys(v) { return MT + PH - (v / maxVal) * PH; }
    var step = PW / Math.max(rows.length - 1, 1);
    function xp(i) { return ML + i * step - (i * step === 0 ? 0 : 0); }
    function abbrev(n) { n = Number(n); if (n >= 1000000) return (n / 1000000).toFixed(1) + "M"; if (n >= 1000) return (n / 1000).toFixed(1) + "K"; return n.toLocaleString(); }
    var rawPts = rows.map(function (r, i) { return xp(i) + "," + ys(r.raw_tokens); }).join(" ");
    var compPts = rows.map(function (r, i) { return xp(i) + "," + ys(r.compressed_tokens); }).join(" ");
    var ticks = [];
    for (var ti = 0; ti <= 4; ti++) { var v = Math.round((maxVal / 4) * ti); ticks.push({ v: v, y: ys(v) }); }
    var labelStep = Math.max(1, Math.floor(rows.length / 8));
    var xLabels = rows.filter(function (_, i) { return i % labelStep === 0 || i === rows.length - 1; });
    var barW = Math.max(4, Math.min(16, step * 0.5));
    function onMove(e) {
      var svg = e.currentTarget;
      var rect = svg.getBoundingClientRect();
      var mx = e.clientX - rect.left - ML;
      var idx = Math.round(mx / step);
      if (idx < 0) idx = 0;
      if (idx >= rows.length) idx = rows.length - 1;
      setTip({ idx: idx, x: e.clientX - rect.left, y: e.clientY - rect.top - 12 });
    }
    function onLeave() { setTip(null); }
    var tipEl = null;
    if (tip !== null && rows[tip.idx]) {
      var r = rows[tip.idx];
      tipEl = h("div", { className: "tro-chart-tooltip", style: { left: Math.min(Math.max(tip.x - 80, 0), W - 160) + "px", top: Math.max(tip.y - 70, 0) + "px" } },
        h("div", { className: "tro-tt-row" }, h("span", null, t("bucket") + ":"), h("span", { className: "tro-tt-val" }, r.bucket)),
        h("div", { className: "tro-tt-row" }, h("span", null, t("callsLabel") + ":"), h("span", { className: "tro-tt-val" }, r.calls)),
        h("div", { className: "tro-tt-row" }, h("span", { style: { color: "var(--color-blue-400)" } }, "\u25CF " + t("rawLine") + ":"), h("span", { className: "tro-tt-val" }, abbrev(r.raw_tokens))),
        h("div", { className: "tro-tt-row" }, h("span", { style: { color: "var(--color-emerald-400)" } }, "\u25CF " + t("compressedLine") + ":"), h("span", { className: "tro-tt-val" }, abbrev(r.compressed_tokens))),
        h("div", { className: "tro-tt-row" }, h("span", { style: { color: "var(--color-success)" } }, "\u25A0 " + t("savedBar") + ":"), h("span", { className: "tro-tt-val" }, abbrev(r.saved_tokens) + " (" + r.savings_rate + "%)"))
      );
    }
    var bars = rows.map(function (r, i) {
      return h("rect", { key: "bar" + i, x: xp(i) - barW / 2, y: ys(r.saved_tokens), width: barW, height: PH - ys(r.saved_tokens) + MT, fill: "var(--color-success)", opacity: 0.2, rx: 1 });
    });
    return h("div", { className: "tro-chart-card" },
      h("div", { className: "tro-chart-head" },
        h("span", { className: "tro-chart-title" }, t("tokenTrend")),
        h("div", { className: "tro-chart-legend" },
          h("span", { className: "tro-legend-item", style: { color: "var(--color-blue-400)" } }, "\u2501 " + t("rawLine")),
          h("span", { className: "tro-legend-item", style: { color: "var(--color-emerald-400)" } }, "\u2501 " + t("compressedLine")),
          h("span", { className: "tro-legend-item", style: { color: "var(--color-success)" } }, "\u25A0 " + t("savedBar"))
        )
      ),
      h("div", { className: "tro-chart-svg-wrap" },
        h("svg", { className: "tro-chart-svg", viewBox: "0 0 " + W + " " + H, preserveAspectRatio: "xMidYMid meet", onMouseMove: onMove, onMouseLeave: onLeave },
          ticks.map(function (tick) {
            return h("g", { key: "tick" + tick.v },
              h("line", { x1: ML, y1: tick.y, x2: W - MR, y2: tick.y, stroke: "var(--color-border)", strokeWidth: 1 }),
              h("text", { x: ML - 4, y: tick.y + 4, textAnchor: "end", fill: "var(--color-muted-foreground)", fontSize: 11 }, abbrev(tick.v))
            );
          }),
          h("polyline", { points: rawPts, fill: "none", stroke: "var(--color-blue-400)", strokeWidth: 2, strokeLinejoin: "round" }),
          h("polyline", { points: compPts, fill: "none", stroke: "var(--color-emerald-400)", strokeWidth: 2, strokeLinejoin: "round" }),
          h("g", null, bars),
          xLabels.map(function (r) {
            var i = rows.indexOf(r);
            return h("text", { key: "xl" + i, x: xp(i), y: H - 8, textAnchor: "middle", fill: "var(--color-muted-foreground)", fontSize: 10 }, r.bucket.replace("2026-", "").replace("2025-", "").replace("2027-", ""));
          }),
          h("rect", { x: ML, y: MT, width: PW, height: PH, fill: "transparent", stroke: "none", pointerEvents: "all" })
        ),
        tipEl
      )
    );
  }
  function box(title, value, sub) {
    return h("div", { className: "tro-metric" },
      h("div", { className: "tro-metric-title" }, title),
      h("div", { className: "tro-metric-value" }, value),
      sub ? h("div", { className: "tro-metric-sub" }, sub) : null
    );
  }
  function tdText(value, className, title) {
    return h("td", { className: className || "", title: title || String(value || "") }, value || "");
  }
  function rankTable(title, rows, columns) {
    return h("div", { className: "tro-rank-card" },
      h("h3", null, title),
      h("table", { className: "tro-table tro-rank-table" },
        h("thead", null, h("tr", null, columns.map(function (c) { return h("th", { key: c.key }, c.label); }))),
        h("tbody", null, (rows || []).map(function (r, i) {
          return h("tr", { key: r.id || r.tool_name || i }, columns.map(function (c) {
            return h("td", { key: c.key }, c.render ? c.render(r) : r[c.key]);
          }));
        }))
      )
    );
  }

  function ToolResultOptimizer() {
    const useState = hooks.useState;
    const useEffect = hooks.useEffect;
    const i18nCtx = typeof useI18n === "function" ? useI18n() : null;
    const t = makeTranslator(detectLocale(i18nCtx));
    const st = useState(null);
    const data = st[0], setData = st[1];
    const policySt = useState(null);
    const policy = policySt[0], setPolicy = policySt[1];
    const errSt = useState("");
    const err = errSt[0], setErr = errSt[1];
    const offSt = useState(0);
    const recentOff = offSt[0], setRecentOff = offSt[1];
    const daysSt = useState(1);
    const days = daysSt[0], setDays = daysSt[1];

    function setRange(nextDays) {
      setDays(nextDays);
      setRecentOff(0);
    }

    function load() {
      setErr("");
      const params = "?limit=20&days=" + days + (recentOff > 0 ? "&offset=" + recentOff : "");
      Promise.all([
        fetchJSON("/api/plugins/tool-result-optimizer/summary" + params),
        fetchJSON("/api/plugins/tool-result-optimizer/policy")
      ]).then(function (parts) {
        setData(parts[0]);
        setPolicy(parts[1]);
      }).catch(function (e) { setErr(String(e)); });
    }
    useEffect(function () { load(); }, [recentOff, days]);

    const totals = data && data.totals ? data.totals : {};
    const byTool = data && data.by_tool ? data.by_tool : [];
    const byMode = data && data.by_mode ? data.by_mode : [];
    const recent = data && data.recent ? data.recent : [];
    const rankings = data && data.rankings ? data.rankings : {};
    const policyTools = policy && policy.tools ? policy.tools : [];
    const ranges = [
      { value: 1, label: t("rangeToday") },
      { value: 3, label: t("range3d") },
      { value: 10, label: t("range10d") },
      { value: 30, label: t("range30d") }
    ];

    return h("div", { className: "tro-page" },
      h("div", { className: "tro-header" },
        h("div", null,
          h("h1", null, t("title")),
          h("p", null, t("subtitle"))
        ),
        h("div", { className: "tro-header-actions" },
          h("div", { className: "tro-range-filter", role: "group", "aria-label": t("timeRange") },
            h("span", { className: "tro-range-label" }, t("timeRange")),
            ranges.map(function (r) {
              return h("button", {
                key: r.value,
                className: "tro-range-btn" + (days === r.value ? " active" : ""),
                onClick: function () { setRange(r.value); }
              }, r.label);
            })
          ),
          Button ? h(Button, { onClick: load }, t("refresh")) : h("button", { className: "tro-btn", onClick: load }, t("refresh"))
        )
      ),
      err ? h("div", { className: "tro-error" }, err) : null,
      h("div", { className: "tro-grid" },
        box(t("rawTokens"), fmt(totals.raw_tokens)),
        box(t("compressedTokens"), fmt(totals.compressed_tokens)),
        box(t("savedTokens"), fmt(totals.saved_tokens), pct(totals.saved_tokens, totals.raw_tokens) + " " + t("savedSuffix")),
        box(t("compressedCalls"), fmt(totals.compressed_calls) + " / " + fmt(totals.calls), t("avgPrefix") + " " + Number(totals.avg_duration_ms || 0).toFixed(0) + " ms")
      ),

      h(TokenTrendChart, { rows: data && data.trend ? data.trend : [], t: t }),

      h("h2", null, t("topRankings")),
      h("div", { className: "tro-rank-grid" },
        rankTable(t("mostTokenHungryTools"), rankings.top_raw_tools, [
          { key: "tool_name", label: t("tool") },
          { key: "calls", label: t("calls"), render: function (r) { return fmt(r.calls); } },
          { key: "raw_tokens", label: t("raw"), render: function (r) { return fmt(r.raw_tokens); } },
          { key: "saved_tokens", label: t("saved"), render: function (r) { return fmt(r.saved_tokens); } }
        ]),
        rankTable(t("mostSavedCalls"), rankings.top_saved_calls, [
          { key: "tool_name", label: t("tool") },
          { key: "raw_tokens", label: t("raw"), render: function (r) { return fmt(r.raw_tokens); } },
          { key: "saved_tokens", label: t("saved"), render: function (r) { return fmt(r.saved_tokens); } },
          { key: "savings_rate", label: t("rate"), render: function (r) { return Number(r.savings_rate || 0).toFixed(1) + "%"; } }
        ]),
        rankTable(t("lowSavingsTools"), rankings.low_savings_tools, [
          { key: "tool_name", label: t("tool") },
          { key: "calls", label: t("calls"), render: function (r) { return fmt(r.calls); } },
          { key: "raw_tokens", label: t("raw"), render: function (r) { return fmt(r.raw_tokens); } },
          { key: "savings_rate", label: t("rate"), render: function (r) { return Number(r.savings_rate || 0).toFixed(1) + "%"; } }
        ]),
        rankTable(t("mostCalledTools"), rankings.top_called_tools, [
          { key: "tool_name", label: t("tool") },
          { key: "calls", label: t("calls"), render: function (r) { return fmt(r.calls); } },
          { key: "raw_tokens", label: t("raw"), render: function (r) { return fmt(r.raw_tokens); } },
          { key: "saved_tokens", label: t("saved"), render: function (r) { return fmt(r.saved_tokens); } }
        ])
      ),

      h("h2", null, t("byTool")),
      h("table", { className: "tro-table" },
        h("thead", null, h("tr", null,
          [t("tool"), t("mode"), t("calls"), t("raw"), t("compressed"), t("saved"), t("rate"), t("compressedCallsCol"), t("avgMs")].map(function (x) { return h("th", { key: x }, x); })
        )),
        h("tbody", null, byTool.map(function (r) {
          return h("tr", { key: r.tool_name + ':' + (r.compression_mode || '') },
            h("td", null, r.tool_name),
            h("td", null, h("span", { className: "tro-mode-pill" }, r.compression_mode || "raw")),
            h("td", null, fmt(r.calls)),
            h("td", null, fmt(r.raw_tokens)),
            h("td", null, fmt(r.compressed_tokens)),
            h("td", null, fmt(r.saved_tokens)),
            h("td", null, pct(r.saved_tokens, r.raw_tokens)),
            h("td", null, fmt(r.compressed_calls)),
            h("td", null, Number(r.avg_duration_ms || 0).toFixed(0))
          );
        }))
      ),

      h("h2", null, t("byMode")),
      h("table", { className: "tro-table" },
        h("thead", null, h("tr", null,
          [t("mode"), t("calls"), t("raw"), t("compressed"), t("saved"), t("rate"), t("compressedCallsCol")].map(function (x) { return h("th", { key: x }, x); })
        )),
        h("tbody", null, byMode.map(function (r) {
          return h("tr", { key: r.compression_mode },
            h("td", null, h("span", { className: "tro-mode-pill" }, r.compression_mode || "raw")),
            h("td", null, fmt(r.calls)),
            h("td", null, fmt(r.raw_tokens)),
            h("td", null, fmt(r.compressed_tokens)),
            h("td", null, fmt(r.saved_tokens)),
            h("td", null, pct(r.saved_tokens, r.raw_tokens)),
            h("td", null, fmt(r.compressed_calls))
          );
        }))
      ),

      h("h2", null, t("compressionPolicy")),
      h("div", { className: "tro-policy-summary" },
        policy ? [
          t("enabled") + "=" + policy.enabled,
          t("telemetry") + "=" + policy.telemetry_enabled,
          t("compression") + "=" + policy.compression_enabled,
          t("storage") + "=" + policy.storage_enabled,
          t("retention") + "=" + policy.retention_days + "d"
        ].join("  ·  ") : t("loading")
      ),
      h("table", { className: "tro-table" },
        h("thead", null, h("tr", null,
          [t("tool"), t("mode"), t("minChars"), t("head"), t("tail")].map(function (x) { return h("th", { key: x }, x); })
        )),
        h("tbody", null, policyTools.map(function (r) {
          return h("tr", { key: r.tool_name },
            h("td", null, r.tool_name),
            h("td", null, r.mode),
            h("td", null, fmt(r.min_chars)),
            h("td", null, fmt(r.preview_head_chars)),
            h("td", null, fmt(r.preview_tail_chars))
          );
        }))
      ),

      h("h2", null, t("recentCalls")),
      h("div", { className: "tro-table-head" },
        h("span", { className: "tro-muted" }, t("showing") + " " + recent.length + " / " + (data && data.recent_total || 0)),
        h("div", { className: "tro-page-actions" },
          h("button", {
            className: "tro-btn tro-page-btn",
            disabled: recentOff <= 0,
            onClick: function () { setRecentOff(Math.max(0, recentOff - 20)); }
          }, t("prev")),
          h("span", { className: "tro-page-num" }, (Math.floor(recentOff / 20) + 1) + " / " + Math.max(1, Math.ceil((data && data.recent_total || 0) / 20))),
          h("button", {
            className: "tro-btn tro-page-btn",
            disabled: recentOff + 20 >= (data && data.recent_total || 0),
            onClick: function () { setRecentOff(recentOff + 20); }
          }, t("next"))
        )
      ),
      h("table", { className: "tro-table" },
        h("thead", null, h("tr", null,
          [t("time"), t("tool"), t("session"), t("call"), t("mode"), t("evidence"), t("raw"), t("compressed"), t("saved"), t("rate"), t("chars"), t("stored")].map(function (x) { return h("th", { key: x }, x); })
        )),
        h("tbody", null, recent.map(function (r) {
          return h("tr", { key: r.id },
            h("td", null, time(r.ts)),
            h("td", null, r.tool_name),
            tdText(shortId(r.session_id), "tro-mono", r.session_id),
            tdText(shortId(r.tool_call_id), "tro-mono", r.tool_call_id),
            h("td", null, h("span", { className: "tro-mode-pill" }, r.compression_mode || (r.changed ? t("compressedMode") : t("rawMode")))),
            tdText(evidenceText(r), "tro-evidence", evidenceText(r)),
            h("td", null, fmt(r.raw_tokens)),
            h("td", null, fmt(r.compressed_tokens)),
            h("td", null, fmt(r.saved_tokens)),
            h("td", null, Number(r.savings_rate || 0).toFixed(1) + "%"),
            h("td", null, fmt(r.raw_chars) + " → " + fmt(r.compressed_chars)),
            h("td", { className: "tro-path", title: r.stored_path || "" }, r.stored_path || "")
          );
        }))
      ),
      data && data.db_path ? h("p", { className: "tro-muted" }, t("db") + ": " + data.db_path) : null
    );
  }

  if (window.__HERMES_PLUGINS__ && typeof window.__HERMES_PLUGINS__.register === "function") {
    window.__HERMES_PLUGINS__.register("tool-result-optimizer", ToolResultOptimizer);
  }
})();
