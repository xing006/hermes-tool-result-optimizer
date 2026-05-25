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
      db: "DB"
    },
    "zh-CN": {
      title: "工具结果 Token",
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
      db: "数据库"
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

    const recentSt = useState(0);
    const recentOff = recentSt[0], setRecentOff = recentSt[1];

    function load() {
      setErr("");
      Promise.all([
        fetchJSON("/api/plugins/tool-result-optimizer/summary?limit=20&offset=" + recentOff),
        fetchJSON("/api/plugins/tool-result-optimizer/policy")
      ]).then(function (parts) {
        setData(parts[0]);
        setPolicy(parts[1]);
      }).catch(function (e) { setErr(String(e)); });
    }
    useEffect(function () { load(); }, [recentOff]);

    const totals = data && data.totals ? data.totals : {};
    const byTool = data && data.by_tool ? data.by_tool : [];
    const recent = data && data.recent ? data.recent : [];
    const rankings = data && data.rankings ? data.rankings : {};
    const policyTools = policy && policy.tools ? policy.tools : [];

    return h("div", { className: "tro-page" },
      h("div", { className: "tro-header" },
        h("div", null,
          h("h1", null, t("title")),
          h("p", null, t("subtitle"))
        ),
        Button ? h(Button, { onClick: load }, t("refresh")) : h("button", { onClick: load }, t("refresh"))
      ),
      err ? h("div", { className: "tro-error" }, err) : null,
      h("div", { className: "tro-grid" },
        box(t("rawTokens"), fmt(totals.raw_tokens)),
        box(t("compressedTokens"), fmt(totals.compressed_tokens)),
        box(t("savedTokens"), fmt(totals.saved_tokens), pct(totals.saved_tokens, totals.raw_tokens) + " " + t("savedSuffix")),
        box(t("compressedCalls"), fmt(totals.compressed_calls) + " / " + fmt(totals.calls), t("avgPrefix") + " " + Number(totals.avg_duration_ms || 0).toFixed(0) + " ms")
      ),

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
          [t("tool"), t("calls"), t("raw"), t("compressed"), t("saved"), t("rate"), t("compressedCallsCol"), t("avgMs")].map(function (x) { return h("th", { key: x }, x); })
        )),
        h("tbody", null, byTool.map(function (r) {
          return h("tr", { key: r.tool_name },
            h("td", null, r.tool_name),
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
      h("div", { style: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px", marginBottom: "8px" } },
        h("span", { className: "tro-muted" }, "Showing " + recent.length + " / " + (data && data.recent_total || 0)),
        h("div", { style: { display: "flex", gap: "6px", alignItems: "center" } },
          h("button", {
            style: { padding: "4px 10px", fontSize: "12px", cursor: "pointer", background: "transparent", border: "1px solid var(--color-border)", color: "var(--color-midground)", borderRadius: "4px" },
            disabled: recentOff <= 0,
            onClick: function () { setRecentOff(Math.max(0, recentOff - 20)); }
          }, "\u2190 Prev"),
          h("span", { style: { fontSize: "12px", fontFamily: "monospace" } }, (Math.floor(recentOff / 20) + 1) + " / " + Math.max(1, Math.ceil((data && data.recent_total || 0) / 20))),
          h("button", {
            style: { padding: "4px 10px", fontSize: "12px", cursor: "pointer", background: "transparent", border: "1px solid var(--color-border)", color: "var(--color-midground)", borderRadius: "4px" },
            disabled: recentOff + 20 >= (data && data.recent_total || 0),
            onClick: function () { setRecentOff(recentOff + 20); }
          }, "Next \u2192")
        )
      ),
      h("table", { className: "tro-table" },
        h("thead", null, h("tr", null,
          [t("time"), t("tool"), t("session"), t("call"), t("mode"), t("raw"), t("compressed"), t("saved"), t("rate"), t("chars"), t("stored")].map(function (x) { return h("th", { key: x }, x); })
        )),
        h("tbody", null, recent.map(function (r) {
          return h("tr", { key: r.id },
            h("td", null, time(r.ts)),
            h("td", null, r.tool_name),
            tdText(shortId(r.session_id), "tro-mono", r.session_id),
            tdText(shortId(r.tool_call_id), "tro-mono", r.tool_call_id),
            h("td", null, r.changed ? t("compressedMode") : t("rawMode")),
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
