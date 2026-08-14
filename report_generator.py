#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阿拉丁 + ione 每日测试风险日报生成器（参考实现）

本脚本读取 assets/report-template.html 模板，按 SKILL.md 规范填充内容，
重点实现：
1. 风险等级为「无」时风险说明改为进度简述。
2. 根据确认的 Aone 项目 ID 与阿拉丁测试计划 ID 拉取数据并生成缺陷链接。

TODO：fetch_aladdin_progress / fetch_ione_defects / fetch_aone_project
需要替换为真实平台接口调用。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = SKILL_DIR / "assets" / "report-template.html"

# Aone 缺陷详情页链接模板；{aone_project_id} 与 {bug_id} 由用户确认与 ione 缺陷映射得到
AONE_BUG_URL_TEMPLATE = "https://aone.alibaba-inc.com/v2/project/{aone_project_id}/bug/{bug_id}"


def load_config(path: Path) -> dict[str, Any]:
    """加载 config.yaml。"""
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover
        raise ImportError("请安装 pyyaml: pip install pyyaml") from exc
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def fetch_aladdin_progress(
    req_id: str, test_plan_id: str, config: dict[str, Any]
) -> dict[str, Any]:
    """TODO：替换为真实阿拉丁接口调用；使用 aladdin_test_plan_id 拉取用例进度。"""
    raise NotImplementedError("请接入真实阿拉丁 API：fetch_aladdin_progress")


def fetch_ione_defects(req_id: str, config: dict[str, Any]) -> dict[str, Any]:
    """TODO：替换为真实 ione 接口调用。"""
    raise NotImplementedError("请接入真实 ione API：fetch_ione_defects")


def fetch_aone_project(project_name: str, config: dict[str, Any]) -> list[dict[str, Any]]:
    """TODO：替换为真实 coop/Aone 接口调用，按项目名称模糊搜索项目。"""
    raise NotImplementedError("请接入真实 Aone API：fetch_aone_project")


def format_percent(value: float) -> str:
    """0.625 -> '62.5%'"""
    return f"{value * 100:.1f}%"


def evaluate_risk(data: dict[str, Any], rules: list[dict[str, Any]]) -> dict[str, Any]:
    """
    根据剩余天数与阈值评估风险等级，并返回未达标原因与阈值。
    返回的 risk_level 为「信息/低/中/高」四档之一；
    若业务上需要「无」，由调用方根据策略覆盖为「无」。
    """
    days = data.get("days_until_release", 9999)
    execution_rate = data.get("execution_rate", 0.0)
    pass_rate = data.get("pass_rate", 1.0)
    unclosed_p0_p1 = data.get("unclosed_p0_p1", 0)

    window = None
    for rule in rules:
        if days <= rule["days_max"]:
            window = rule
            break
    if window is None:
        window = rules[-1]

    score_map = {"no_risk": 0, "low": 1, "medium": 2, "high": 3}
    base_level = window["base_level"]
    score = score_map.get(base_level, 0)

    reasons: list[str] = []
    if execution_rate < window["execution_rate"]:
        reasons.append(
            f"执行率 {format_percent(execution_rate)} 低于阈值 "
            f"{format_percent(window['execution_rate'])}"
        )
        score += 1
    if pass_rate < window["pass_rate"]:
        reasons.append(
            f"通过率 {format_percent(pass_rate)} 低于阈值 "
            f"{format_percent(window['pass_rate'])}"
        )
        score += 1
    if unclosed_p0_p1 > window["unclosed_p0_p1"]:
        reasons.append(
            f"未关闭 P0/P1 缺陷 {unclosed_p0_p1} 个，超出阈值 "
            f"{window['unclosed_p0_p1']} 个"
        )
        score += 1

    score = min(score, 3)
    level_map = {0: "无", 1: "低", 2: "中", 3: "高"}

    return {
        "risk_level": level_map[score],
        "risk_reasons": reasons,
        "threshold_execution_rate": window["execution_rate"],
        "threshold_pass_rate": window["pass_rate"],
        "threshold_unclosed_p0_p1": window["unclosed_p0_p1"],
    }


def _summarize_severities(bugs: list[dict[str, Any]]) -> str:
    """聚合 bug 优先级，例如 'P2优先级 2 个，P3优先级 1 个'。"""
    counts: dict[str, int] = {}
    for bug in bugs:
        sev = bug.get("severity") or "未分级"
        counts[sev] = counts.get(sev, 0) + 1
    return "，".join(f"{k}优先级 {v} 个" for k, v in counts.items())


def _summarize_bug_types(bugs: list[dict[str, Any]]) -> str:
    """聚合缺陷类型与个数，例如 '功能缺陷 5 个，UI 缺陷 3 个'。"""
    counts: dict[str, int] = {}
    for bug in bugs:
        t = bug.get("type") or "未分类"
        counts[t] = counts.get(t, 0) + 1
    if not counts:
        return "无"
    return "，".join(f"{k} {v} 个" for k, v in counts.items())


def _summarize_bug_modules(bugs: list[dict[str, Any]]) -> str:
    """按业务模块聚合缺陷个数，例如 '日本站点 4 个，支付模块 3 个'。"""
    counts: dict[str, int] = {}
    for bug in bugs:
        m = bug.get("module") or "未归类"
        counts[m] = counts.get(m, 0) + 1
    if not counts:
        return "无"
    return "，".join(f"{k} {v} 个" for k, v in counts.items())


def _summarize_bug_developers(bugs: list[dict[str, Any]]) -> str:
    """按开发责任人聚合缺陷个数，例如 '音十 8 个，程君 2 个'。"""
    counts: dict[str, int] = {}
    for bug in bugs:
        dev = bug.get("developer") or "未分配"
        counts[dev] = counts.get(dev, 0) + 1
    if not counts:
        return "无"
    return "，".join(f"{k} {v} 个" for k, v in counts.items())


_HIGH_PRIORITY_SEVERITIES = {"P0", "P1", "严重", "高优先级", "高"}


def _is_high_priority(bug: dict[str, Any]) -> bool:
    """判断缺陷是否属于高优先级（P0/P1/严重/高优先级/高）。"""
    severity = (bug.get("severity") or "").strip()
    priority = (bug.get("priority") or "").strip()
    return severity in _HIGH_PRIORITY_SEVERITIES or priority in _HIGH_PRIORITY_SEVERITIES


def _build_unclosed_defect_analysis(bugs: list[dict[str, Any]]) -> str:
    """
    简约分析未关闭缺陷，聚焦高优先级缺陷。
    返回一段自然语言总结，最多提及前两名负责人。
    """
    if not bugs:
        return "当前无未关闭缺陷。"

    high_priority = [b for b in bugs if _is_high_priority(b)]
    high_count = len(high_priority)

    # 按模块聚合高优先级缺陷
    module_counts: dict[str, int] = {}
    for bug in high_priority:
        m = bug.get("module") or "未归类"
        module_counts[m] = module_counts.get(m, 0) + 1
    top_modules = sorted(module_counts.items(), key=lambda x: (-x[1], x[0]))[:2]

    # 按负责人聚合全部未关闭缺陷，取前两名
    dev_counts = _count_by(bugs, "developer", "未分配")[:2]

    parts: list[str] = []
    if high_count:
        parts.append(f"未关闭缺陷中共有 {high_count} 个高优先级（P0/P1/严重/高优先级）")
        if top_modules:
            module_text = "、".join(f"{m} {c} 个" for m, c in top_modules)
            parts.append(f"，主要集中在 {module_text}")
        parts.append("。")
    else:
        parts.append("未关闭缺陷均为中低优先级。")

    if dev_counts:
        dev_text = "、".join(f"{dev} {cnt} 个" for dev, cnt in dev_counts)
        parts.append(f"当前未关闭缺陷主要涉及负责人：{dev_text}。")

    return "".join(parts)


_CHART_COLORS = [
    "#0060FF", "#00C853", "#FFAB00", "#FF5252",
    "#AA00FF", "#00B8D4", "#FF6D00", "#3F51B5",
]


def _chart_data(items: list[tuple[str, int]]) -> str:
    """将聚合结果序列化为 JavaScript 对象字面量，标签使用 JSON 字符串编码。"""
    labels = [label for label, _ in items]
    values = [value for _, value in items]
    return f"{{ labels: {json.dumps(labels)}, values: {values} }}"


def _suggested_max(items: list[tuple[str, int]]) -> int | None:
    """
    根据数据最大值计算 y 轴建议上限，固定比最大值多 2 个单位，
    保证纵坐标刻度始终高于最高柱形/数据点，避免上方的数值标签被遮挡或裁切。
    返回 None 表示无数据、无需设置。
    """
    values = [value for _, value in items]
    if not values:
        return None
    m = max(values)
    if m <= 0:
        return 2
    return m + 2


def _count_by(bugs: list[dict[str, Any]], key: str, default: str) -> list[tuple[str, int]]:
    """按指定字段聚合缺陷数量，返回按数量降序的 (label, count) 列表。"""
    counts: dict[str, int] = {}
    for bug in bugs:
        value = bug.get(key) or default
        counts[value] = counts.get(value, 0) + 1
    return sorted(counts.items(), key=lambda x: (-x[1], x[0]))


def _metric_span(value: int, level: str) -> str:
    """将数值包装为带颜色样式的 <span>。level 为 danger/warning/success 或 none（无颜色）。"""
    if level == "none":
        return str(value)
    return f'<span class="metric-{level}">{value}</span>'


def _metric_level(value: int, danger: int, warning: int) -> str:
    """根据阈值判断数值的颜色级别。"""
    if value == 0:
        return "success"
    if value >= danger:
        return "danger"
    if value >= warning:
        return "warning"
    return "none"


def _parse_daily_bug_counts(data: dict[str, Any]) -> list[tuple[str, int]]:
    """
    解析每日缺陷数量，返回按日期升序的 (MM-DD, count) 列表。
    支持两种输入：
    1. data['daily_bug_counts'] = [{'date': '2026-07-15', 'count': 3}, ...]
    2. 从 all_bugs 的 'created_date' 字段按天聚合。
    """
    raw = data.get("daily_bug_counts")
    if raw:
        parsed: list[tuple[str, int]] = []
        for item in raw:
            date_str = item.get("date", "")
            count = item.get("count", 0)
            if date_str:
                label = date_str[5:] if len(date_str) >= 10 else date_str
                parsed.append((label, int(count)))
        return sorted(parsed, key=lambda x: x[0])

    # 兜底：按 bug 的 created_date 聚合
    counts: dict[str, int] = {}
    for bug in data.get("new_bugs", []) + data.get("later_bugs", []):
        date_str = bug.get("created_date", "")
        if date_str:
            label = date_str[5:] if len(date_str) >= 10 else date_str
            counts[label] = counts.get(label, 0) + 1
    return sorted(counts.items(), key=lambda x: x[0])


# 汇总区颜色阈值：数值超过危险/警告阈值时分别标红/标黄，否则标绿（含 0 个）
_METRIC_THRESHOLDS = {
    "total": (10, 5),       # (danger, warning)
    "unresolved": (5, 1),
    "delayed": (1, 0),
    "type": (5, 2),
    "module": (4, 2),
    "developer": (4, 2),
}


_DATA_LABEL_PLUGIN = """
const dataLabelPlugin = {
  id: 'dataLabelPlugin',
  afterDatasetsDraw(chart) {
    const ctx = chart.ctx;
    chart.data.datasets.forEach((dataset, i) => {
      const meta = chart.getDatasetMeta(i);
      if (meta.hidden) return;
      meta.data.forEach((element, index) => {
        const value = dataset.data[index];
        if (value === null || value === undefined) return;
        ctx.save();
        ctx.font = '600 11px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif';
        ctx.fillStyle = '#1f1f1f';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';
        const isBar = element.base !== undefined;
        const x = element.x;
        const y = element.y;
        ctx.fillText(value, x, y - (isBar ? 4 : 8));
        ctx.restore();
      });
    });
  }
};
"""


def _colored_count_items(bugs: list[dict[str, Any]], key: str, default: str, level_key: str) -> str:
    """按 key 聚合缺陷数量，并为每个数值按阈值着色。"""
    counts: dict[str, int] = {}
    for bug in bugs:
        value = bug.get(key) or default
        counts[value] = counts.get(value, 0) + 1
    if not counts:
        return "无"
    danger, warning = _METRIC_THRESHOLDS[level_key]
    parts: list[str] = []
    for label, count in sorted(counts.items(), key=lambda x: (-x[1], x[0])):
        level = _metric_level(count, danger, warning)
        parts.append(f"{label} {_metric_span(count, level)} 个")
    return "，".join(parts)


def _build_summary_cell(data: dict[str, Any]) -> str:
    """
    构建「■ 缺陷情况」→「汇总」单元格的完整 HTML 内容。

    内容采用有序列表，每点独占一行：
    1. 缺陷总数 / 待解决 / 延期（关键数值按状态着色）
    2. 缺陷类型分布（文字，数字着色）
    3. 业务模块分布（数据少用文字+着色，数据多→见下方图表）
    4. 开发责任人分布（数据少用文字+着色，数据多→见下方图表）
    5. 未关闭缺陷简约分析
    6. 3 个统计图固定放在本单元格最下方：业务模块分布 → 开发责任人分布 → 每日缺陷走势（满足条件时）
    """
    all_bugs = data.get("all_bugs") or (data.get("new_bugs", []) + data.get("later_bugs", []))
    total_bugs = len(all_bugs)

    new_bugs = data.get("new_bugs", [])
    later_bugs = data.get("later_bugs", [])
    unresolved_count = data.get("unresolved_count", len(new_bugs))
    delayed_count = data.get("delayed_count", len(later_bugs))

    module_counts = _count_by(all_bugs, "module", "未归类")
    developer_counts = _count_by(all_bugs, "developer", "未分配")

    # 数据量判断：缺陷总数 <= 5 或 模块/开发责任人去重后 <= 3 时，用文字描述模块和开发者分布
    use_text_for_distributions = (
        total_bugs <= 5 or len(module_counts) <= 3 or len(developer_counts) <= 3
    )

    # 每日缺陷走势渲染条件：测试时长 > 5 天 且 缺陷总数 > 5
    test_duration_days = data.get("test_duration_days", 0)
    render_trend = test_duration_days > 5 and total_bugs > 5
    daily_counts = _parse_daily_bug_counts(data) if render_trend else []
    render_trend = render_trend and bool(daily_counts)

    # 第 1 点：缺陷总数 / 待解决 / 延期，数值着色
    t_d, t_w = _METRIC_THRESHOLDS["total"]
    u_d, u_w = _METRIC_THRESHOLDS["unresolved"]
    d_d, d_w = _METRIC_THRESHOLDS["delayed"]
    total_html = _metric_span(total_bugs, _metric_level(total_bugs, t_d, t_w))
    unresolved_html = _metric_span(unresolved_count, _metric_level(unresolved_count, u_d, u_w))
    delayed_html = _metric_span(delayed_count, _metric_level(delayed_count, d_d, d_w))
    summary_lines = [
        f"<li>缺陷总数 {total_html} 个，待解决 {unresolved_html} 个，延期 {delayed_html} 个</li>"
    ]

    # 第 2 点：缺陷类型分布
    type_summary = _colored_count_items(all_bugs, "type", "未分类", "type")
    summary_lines.append(f"<li>缺陷类型分布：{type_summary}</li>")

    # 第 3 点：业务模块分布
    if use_text_for_distributions:
        module_summary = _colored_count_items(all_bugs, "module", "未归类", "module")
        summary_lines.append(f"<li>业务模块分布：{module_summary}</li>")
    else:
        summary_lines.append('<li>业务模块分布：见下方图表</li>')

    # 第 4 点：开发责任人分布
    if use_text_for_distributions:
        dev_summary = _colored_count_items(all_bugs, "developer", "未分配", "developer")
        summary_lines.append(f"<li>开发责任人分布：{dev_summary}</li>")
    else:
        summary_lines.append('<li>开发责任人分布：见下方图表</li>')

    # 第 5 点：未关闭缺陷分析
    summary_lines.append(f"<li>未关闭缺陷分析：{_build_unclosed_defect_analysis(all_bugs)}</li>")

    parts = [f'<ol class="summary-list">{ "".join(summary_lines) }</ol>']

    # 图表区域：固定放在汇总单元格最下方
    chart_html_blocks: list[str] = []
    chart_scripts: list[str] = []
    integer_ticks_js = "{ callback: function(value) { return Number.isInteger(value) ? value : ''; } }"

    if not use_text_for_distributions:
        # 业务模块分布柱状图
        module_data_js = _chart_data(module_counts)
        module_colors_js = str(_CHART_COLORS[: len(module_counts)])
        chart_html_blocks.append(
            '<div class="chart-box">'
            '<div class="chart-title">业务模块分布</div>'
            '<canvas id="moduleChart" class="chart-canvas"></canvas>'
            '</div>'
        )
        chart_scripts.append(
            f"""var moduleData = {module_data_js};
  new Chart(document.getElementById('moduleChart'), {{
    type: 'bar',
    data: {{
      labels: moduleData.labels,
      datasets: [{{ data: moduleData.values, backgroundColor: {module_colors_js}, borderWidth: 1 }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      layout: {{ padding: {{ top: 24 }} }},
      plugins: {{ legend: {{ display: false }}, tooltip: {{ callbacks: {{ label: function(ctx) {{ return ctx.parsed.y; }} }} }} }},
      scales: {{
        x: {{ title: {{ display: true, text: '业务模块类型', font: {{ size: 12 }} }}, ticks: {{ font: {{ size: 11 }} }} }},
        y: {{ title: {{ display: true, text: 'bug数量', font: {{ size: 12 }} }}, ticks: {integer_ticks_js}, beginAtZero: true, suggestedMax: {_suggested_max(module_counts)} }}
      }}
    }},
    plugins: [dataLabelPlugin]
  }});"""
        )

        # 开发责任人分布柱状图
        developer_data_js = _chart_data(developer_counts)
        developer_colors_js = str(_CHART_COLORS[: len(developer_counts)])
        chart_html_blocks.append(
            '<div class="chart-box">'
            '<div class="chart-title">开发责任人分布</div>'
            '<canvas id="developerChart" class="chart-canvas"></canvas>'
            '</div>'
        )
        chart_scripts.append(
            f"""var developerData = {developer_data_js};
  new Chart(document.getElementById('developerChart'), {{
    type: 'bar',
    data: {{
      labels: developerData.labels,
      datasets: [{{ data: developerData.values, backgroundColor: {developer_colors_js}, borderWidth: 1 }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      layout: {{ padding: {{ top: 24 }} }},
      plugins: {{ legend: {{ display: false }}, tooltip: {{ callbacks: {{ label: function(ctx) {{ return ctx.parsed.y; }} }} }} }},
      scales: {{
        x: {{ title: {{ display: true, text: '开发花名', font: {{ size: 12 }} }}, ticks: {{ font: {{ size: 11 }} }} }},
        y: {{ title: {{ display: true, text: 'bug数量', font: {{ size: 12 }} }}, ticks: {integer_ticks_js}, beginAtZero: true, suggestedMax: {_suggested_max(developer_counts)} }}
      }}
    }},
    plugins: [dataLabelPlugin]
  }});"""
        )

    if render_trend:
        # 每日缺陷走势折线图
        trend_data_js = _chart_data(daily_counts)
        chart_html_blocks.append(
            '<div class="chart-box">'
            f'<div class="chart-title">每日缺陷走势</div>'
            '<canvas id="trendChart" class="chart-canvas"></canvas>'
            '</div>'
        )
        chart_scripts.append(
            f"""var trendData = {trend_data_js};
  new Chart(document.getElementById('trendChart'), {{
    type: 'line',
    data: {{
      labels: trendData.labels,
      datasets: [{{
        data: trendData.values,
        borderColor: '#0060FF',
        backgroundColor: 'rgba(0, 96, 255, 0.1)',
        borderWidth: 2,
        pointBackgroundColor: '#0060FF',
        pointRadius: 4,
        fill: true,
        tension: 0.3
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      layout: {{ padding: {{ top: 28 }} }},
      plugins: {{ legend: {{ display: false }}, tooltip: {{ callbacks: {{ label: function(ctx) {{ return ctx.parsed.y; }} }} }} }},
      scales: {{
        x: {{ title: {{ display: true, text: '测试日期', font: {{ size: 12 }} }}, ticks: {{ font: {{ size: 11 }} }} }},
        y: {{ title: {{ display: true, text: 'bug数量', font: {{ size: 12 }} }}, ticks: {integer_ticks_js}, beginAtZero: true, suggestedMax: {_suggested_max(daily_counts)} }}
      }}
    }},
    plugins: [dataLabelPlugin]
  }});"""
        )

    if chart_html_blocks:
        charts_grid = '\n'.join(
            f'<div class="chart-row">{block}</div>' for block in chart_html_blocks
        )
        script_body = '\n  '.join([_DATA_LABEL_PLUGIN] + chart_scripts)
        parts.append(
            f'<div class="charts" style="margin-top:12px;">\n{charts_grid}\n</div>\n'
            f'<script>\n(function() {{\n  {script_body}\n}})();\n</script>'
        )

    return '\n'.join(parts)


def build_progress_brief(data: dict[str, Any]) -> str:
    """
    风险等级为「无」时生成「进度简述」。
    包含：测试进度百分比、缺陷总数、执行内容分析、总结简述。
    """
    exec_rate = data.get("execution_rate", 0.0) * 100
    total_defects = data.get("total_defects", 0)
    executed_cases = data.get("executed_cases", 0)
    total_cases = data.get("total_cases", 0)
    failed_cases = data.get("failed_cases", 0)
    blocked_cases = data.get("blocked_cases", 0)
    new_bugs = data.get("new_bugs", [])

    # 测试执行进度标绿色（metric-success）；缺陷总数仅在此处描述一次，后续不再重复
    lines = [
        f'测试执行进度：<span class="metric-success">{exec_rate:.1f}%</span>，缺陷总数：{total_defects}'
    ]

    # 共执行用例数标绿色（metric-success）
    parts = [f'今日共执行 <span class="metric-success">{executed_cases}/{total_cases}</span> 条用例']
    if failed_cases:
        parts.append(f"失败 {failed_cases} 条")
    else:
        parts.append("无失败用例")
    if blocked_cases:
        parts.append(f"阻塞 {blocked_cases} 条")

    if new_bugs:
        parts.append(f"当日新提 {len(new_bugs)} 个 bug，{_summarize_severities(new_bugs)}")
    else:
        parts.append("当日无新增缺陷")

    analysis = "，".join(parts) + "。"
    if data.get("failure_focus"):
        analysis += f"失败主要集中在{data['failure_focus']}。"
    if data.get("new_bug_focus"):
        analysis += f"新增缺陷主要涉及{data['new_bug_focus']}。"

    # 总结句不再重复测试执行进度与缺陷总数（已在首行描述），仅陈述 P0/P1 缺陷情况
    unclosed_p0_p1 = data.get("unclosed_p0_p1", 0)
    if unclosed_p0_p1:
        summary = f"未关闭 P0/P1 缺陷 {unclosed_p0_p1} 个。"
    else:
        summary = "无未关闭 P0/P1 缺陷。"
    lines.append(analysis)
    lines.append(summary)
    return "\n".join(lines)


def build_risk_description(data: dict[str, Any]) -> str:
    """
    风险等级不为「无」时生成「风险说明」。
    仅陈述风险因素与对应数据事实，不给出主观行动建议，不包含测试时间。
    按有序序号分段，每点结束后换行。
    """
    reasons = data.get("risk_reasons", [])

    # 风险说明文字颜色与风险等级文字颜色保持一致（高红/中黄/低绿）
    risk_level = data.get("risk_level", "")
    risk_class_map = {"高": "risk-high", "中": "risk-medium", "低": "risk-low"}
    cls = risk_class_map.get(risk_level)

    def _wrap(text: str) -> str:
        return f'<span class="{cls}">{text}</span>' if cls else text

    lines: list[str] = []
    if reasons:
        for idx, reason in enumerate(reasons, 1):
            lines.append(f"{idx}. {_wrap(f'{reason}。')}")
    else:
        lines.append(f"1. {_wrap('当前存在测试风险。')}")

    return "\n".join(lines)


def _build_test_progress_text(data: dict[str, Any]) -> str:
    """按 SKILL.md 规范生成「测试进度」单元格文本；支持追加文档回退产生的 test_progress_notes。"""
    plans = data.get("test_plans", [])
    notes = (data.get("test_progress_notes") or "").strip()

    if len(plans) == 1:
        p = plans[0]
        executed_span = f'<span class="metric-success">{p["executed"]}/{p["total"]}</span>'
        base = f"{p['name']}：{executed_span}，失败用例：{p.get('failed', 0)}"
    else:
        total = sum(p["total"] for p in plans) or data.get("total_cases", 0)
        executed = sum(p["executed"] for p in plans) or data.get("executed_cases", 0)
        failed = sum(p.get("failed", 0) for p in plans) or data.get("failed_cases", 0)
        if total == 0:
            base = ""
        else:
            rate = executed / total * 100
            rate_span = f'<span class="metric-success">{rate:.1f}%</span>'
            base = f"测试执行进度：{rate_span}，失败用例：{failed}"

    if base and notes:
        return f"{base}<br>文档补充：{notes}"
    if base:
        return base
    if notes:
        return f"数据来自文档：<br>{notes}"
    return "暂无测试计划数据"


def _build_issue_notes(data: dict[str, Any]) -> str:
    """
    构建「■ 问题记录」分区内容。

    优先级：
    1. 若 data 中已提供 group_chat_notes（群消息提炼结果）或 issue_notes，直接使用。
    2. 否则按失败用例聚合生成问题描述。
    3. 若群消息和失败用例均无，则返回「无」。
    """
    existing = (data.get("group_chat_notes") or data.get("issue_notes") or "").strip()
    if existing:
        return existing

    # 尝试从 failed_cases_detail 提取明细
    failed_details = data.get("failed_cases_detail", [])
    if failed_details:
        # 按模块/计划聚类
        groups: dict[str, list[str]] = {}
        for case in failed_details:
            key = case.get("module") or case.get("plan_name") or "未分类"
            groups.setdefault(key, []).append(case.get("title", ""))
        lines: list[str] = []
        for idx, (key, titles) in enumerate(groups.items(), 1):
            lines.append(f"{idx}. {key}存在 {len(titles)} 个失败用例。")
        return "\n".join(lines)

    # 无明细时，按 test_plans / failed_cases 汇总
    plans = data.get("test_plans", [])
    if plans:
        failed_groups: dict[str, int] = {}
        for p in plans:
            name = p.get("name", "未命名计划")
            failed = p.get("failed", 0)
            if failed:
                failed_groups[name] = failed_groups.get(name, 0) + failed
        if failed_groups:
            lines = []
            for idx, (name, count) in enumerate(failed_groups.items(), 1):
                lines.append(f"{idx}. {name} 失败用例 {count} 个。")
            return "\n".join(lines)

    # 单一失败数兜底
    failed = data.get("failed_cases", 0)
    if failed:
        return f"1. 当日共 {failed} 个失败用例。"

    return "无"


def _build_aone_bug_url(aone_project_id: int | None, bug_id: int | str | None) -> str | None:
    """根据 Aone 项目 ID 与 bug ID 构造缺陷详情链接；缺少任一参数时返回 None。"""
    if not aone_project_id or not bug_id:
        return None
    return AONE_BUG_URL_TEMPLATE.format(aone_project_id=aone_project_id, bug_id=bug_id)


def _build_bug_list(bugs: list[dict[str, Any]], default_project_id: int | None = None) -> str:
    """生成 <li> 列表，标题为 Aone 超链接。

    多项目场景下，优先使用每条缺陷自身的 ``aone_project_id`` 拼接链接，
    仅在缺陷未携带项目 ID 时才回退到 ``default_project_id``。
    """
    if not bugs:
        return "<li>无</li>"
    items: list[str] = []
    for idx, bug in enumerate(bugs, 1):
        title = bug.get("title", "")
        bug_project_id = bug.get("aone_project_id") or default_project_id
        url = bug.get("url") or _build_aone_bug_url(
            bug_project_id, bug.get("bug_id") or bug.get("id")
        )
        owner = bug.get("owner", "")
        link = f'<a href="{url}">{title}</a>' if url else title
        items.append(f"<li>{idx}. {link} ｜ @{owner}</li>")
    return "\n              ".join(items)


def _content_to_ol_html(content: str) -> str:
    """将「进度简述 / 风险说明」的多点内容渲染为 HTML 有序列表 <ol>。

    - 按换行拆分为多点，每点独占一个 <li>，由 <ol> 自动编号；
    - 去除各行可能已存在的行首序号（如 "1. "、"2、"、"3)"），避免与 <ol> 编号重复。
    """
    import re

    lines = [line.strip() for line in (content or "").split("\n")]
    items: list[str] = []
    for line in lines:
        if not line:
            continue
        line = re.sub(r"^\s*\d+\s*[.、)）]\s*", "", line)
        items.append(f"<li>{line}</li>")
    if not items:
        return ""
    return f'<ol class="progress-list">{"".join(items)}</ol>'


def render_html(template_html: str, data: dict[str, Any]) -> str:
    """替换模板占位符，生成最终 HTML。"""
    is_no_risk = data.get("risk_level") == "无"
    label = "进度简述" if is_no_risk else "风险说明"
    content = build_progress_brief(data) if is_no_risk else build_risk_description(data)

    project_ids = data.get("aone_project_ids")
    if project_ids:
        default_project_id = project_ids[0]
    else:
        default_project_id = data.get("aone_project_id")

    risk_level = data.get("risk_level", "")
    risk_class_map = {"高": "risk-high", "中": "risk-medium", "低": "risk-low", "无": "risk-none"}
    risk_badge = f'<span class="risk-badge {risk_class_map.get(risk_level, "risk-none")}">{risk_level}</span>'

    placeholders = {
        "{项目名称}": data.get("requirement_name", "项目"),
        "{风险说明标签}": label,
        "{风险等级}": risk_level,
        "{风险等级标识}": risk_badge,
        "{风险说明内容}": _content_to_ol_html(content),
        "{测试进度}": _build_test_progress_text(data),
        "{缺陷情况汇总}": _build_summary_cell(data),
        "{new缺陷列表}": _build_bug_list(data.get("new_bugs", []), default_project_id),
        "{later缺陷列表}": _build_bug_list(data.get("later_bugs", []), default_project_id),
        "{问题记录}": _build_issue_notes(data).replace("\n", "<br>"),
    }

    for key, value in placeholders.items():
        template_html = template_html.replace(key, str(value))
    return template_html


def generate_daily_report(data: dict[str, Any], config: dict[str, Any] | None = None) -> str:
    """生成日报 HTML。"""
    template_html = TEMPLATE_PATH.read_text(encoding="utf-8")
    return render_html(template_html, data)


def _demo_data() -> dict[str, Any]:
    """构造演示数据。"""
    return {
        "requirement_name": "集运三期",
        "aladdin_req_ids": ["A-1001"],
        "ione_req_ids": ["I-2001"],
        "aone_project_ids": [2158868, 2158869],
        "aladdin_test_plan_ids": ["TP-1001", "TP-1002"],
        "days_until_release": 10,
        "total_cases": 80,
        "executed_cases": 50,
        "failed_cases": 2,
        "blocked_cases": 0,
        "execution_rate": 0.625,
        "pass_rate": 0.96,
        "unclosed_p0_p1": 0,
        "total_defects": 12,
        "new_bugs": [
            {"title": "菲律宾税费展示异常", "owner": "张三", "severity": "P2", "bug_id": 1, "aone_project_id": 2158868, "type": "功能缺陷", "module": "菲律宾站点", "developer": "音十"},
            {"title": "支付页面加载超时", "owner": "李四", "severity": "P0", "bug_id": 3, "aone_project_id": 2158868, "type": "性能问题", "module": "支付模块", "developer": "程君"},
            {"title": "下单页按钮样式错位", "owner": "王五", "severity": "P3", "bug_id": 5, "aone_project_id": 2158869, "type": "UI 缺陷", "module": "下单模块", "developer": "程君"},
            {"title": "支付回调金额精度异常", "owner": "赵六", "severity": "P0", "bug_id": 7, "aone_project_id": 2158869, "type": "功能缺陷", "module": "支付模块", "developer": "程君"},
        ],
        "later_bugs": [
            {"title": "日本站点运费计算错误", "owner": "张三", "severity": "P1", "bug_id": 2, "aone_project_id": 2158868, "type": "功能缺陷", "module": "日本站点", "developer": "音十"},
            {"title": "物流状态不同步", "owner": "李四", "severity": "P2", "bug_id": 4, "aone_project_id": 2158868, "type": "功能缺陷", "module": "物流模块", "developer": "阿杰"},
            {"title": "菲律宾地址解析失败", "owner": "王五", "severity": "P1", "bug_id": 6, "aone_project_id": 2158869, "type": "功能缺陷", "module": "菲律宾站点", "developer": "小明"},
            {"title": "下单页文案显示乱码", "owner": "赵六", "severity": "P3", "bug_id": 8, "aone_project_id": 2158869, "type": "UI 缺陷", "module": "下单模块", "developer": "音十"},
            {"title": "退款状态机流转异常", "owner": "张三", "severity": "P1", "bug_id": 9, "aone_project_id": 2158868, "type": "功能缺陷", "module": "退款模块", "developer": "程君"},
            {"title": "日本站点税率配置缺失", "owner": "李四", "severity": "P2", "bug_id": 10, "aone_project_id": 2158868, "type": "配置问题", "module": "日本站点", "developer": "程君"},
            {"title": "下单并发锁竞争", "owner": "王五", "severity": "P1", "bug_id": 11, "aone_project_id": 2158869, "type": "性能问题", "module": "下单模块", "developer": "阿杰"},
            {"title": "支付渠道切换白屏", "owner": "赵六", "severity": "P2", "bug_id": 12, "aone_project_id": 2158869, "type": "UI 缺陷", "module": "支付模块", "developer": "小明"},
        ],
        "failure_focus": "跨境运费计算异常",
        "new_bug_focus": "菲律宾站点税费展示",
        "defect_summary": "共计 12 个，待解决 3 个，延期 0 个",
        "issue_notes": "1. 菲律宾站点税费接口返回字段需与产品确认精度规则，当前测试按四舍五入处理。\n2. 日本站点运费计算依赖的汇率表版本待运营侧最终确认，预计明日同步。\n3. 当日群聊未识别到明显卡点/待确认点。",

        "test_plans": [
            {"name": "集运三期-菲律宾", "total": 40, "executed": 25, "failed": 1},
            {"name": "集运三期-印尼", "total": 40, "executed": 25, "failed": 1}
        ],
        "test_duration_days": 7,
        "daily_bug_counts": [
            {"date": "2026-07-15", "count": 1},
            {"date": "2026-07-16", "count": 3},
            {"date": "2026-07-17", "count": 0},
            {"date": "2026-07-18", "count": 2},
            {"date": "2026-07-19", "count": 4},
            {"date": "2026-07-20", "count": 1},
            {"date": "2026-07-21", "count": 1},
        ],
    }


def _default_risk_rules() -> list[dict[str, Any]]:
    return [
        {"days_max": 1, "execution_rate": 0.95, "pass_rate": 0.95, "unclosed_p0_p1": 0, "base_level": "high"},
        {"days_max": 3, "execution_rate": 0.80, "pass_rate": 0.90, "unclosed_p0_p1": 2, "base_level": "medium"},
        {"days_max": 7, "execution_rate": 0.60, "pass_rate": 0.85, "unclosed_p0_p1": 5, "base_level": "low"},
        {"days_max": 9999, "execution_rate": 0.30, "pass_rate": 0.80, "unclosed_p0_p1": 10, "base_level": "no_risk"},
    ]


def main() -> None:
    rules = _default_risk_rules()
    base_data = _demo_data()

    # 先按阈值计算风险与阈值，再覆盖为「无」以演示进度简述分支；当前缺陷数据量命中「数据多」条件，会渲染图表
    risk_result = evaluate_risk(base_data, rules)
    data = {
        **base_data,
        **risk_result,
        "risk_level": "无",
    }

    html = generate_daily_report(data)
    output_path = SKILL_DIR / "outputs" / "report-demo-no-risk.html"
    output_path.parent.mkdir(exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"已生成示例日报（无风险）: {output_path}")

    # 同时演示非「无」风险分支：调低剩余天数并恶化指标，触发风险 escalation；当前数据量命中「数据多」条件且测试周期大于 5 天，会渲染业务模块/开发责任人/每日走势 3 个图表
    risk_data = {**base_data}
    risk_data.update({
        "days_until_release": 0,
        "execution_rate": 0.50,
        "pass_rate": 0.80,
        "unclosed_p0_p1": 6,
        "failed_cases": 8,
        "total_cases": 80,
        "executed_cases": 40,
        "test_plans": [
            {"name": "集运三期-菲律宾", "total": 80, "executed": 40, "failed": 8}
        ],
    })
    risk_result = evaluate_risk(risk_data, rules)
    data = {**risk_data, **risk_result}
    html_risk = generate_daily_report(data)
    output_path_risk = SKILL_DIR / "outputs" / "report-demo-risk.html"
    output_path_risk.write_text(html_risk, encoding="utf-8")
    print(f"已生成示例日报（有风险）: {output_path_risk}")

    # 演示文档回退分支：无阿拉丁测试计划，仅通过文档获取测试进度与难点说明
    doc_data = {**base_data}
    doc_data.update({
        "days_until_release": 5,
        "execution_rate": 0.0,
        "pass_rate": 1.0,
        "failed_cases": 0,
        "total_cases": 0,
        "executed_cases": 0,
        "test_plans": [],
        "test_progress_notes": "本期覆盖下单、支付、退款核心链路；跨境运费计算涉及多币种转换，数据构造较复杂，耗费测试时间较多。",
    })
    doc_risk_result = evaluate_risk(doc_data, rules)
    data = {**doc_data, **doc_risk_result}
    html_doc = generate_daily_report(data)
    output_path_doc = SKILL_DIR / "outputs" / "report-demo-doc-fallback.html"
    output_path_doc.write_text(html_doc, encoding="utf-8")
    print(f"已生成示例日报（文档回退）: {output_path_doc}")


if __name__ == "__main__":
    main()
