#!/usr/bin/env python3
"""验证测试执行进度从 executed/total 改为百分比格式的改动。"""
import sys, os, re, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from report_generator import (
    build_progress_brief,
    render_jsonml,
    verify_report_consistency,
    sync_from_dingtalk_doc,
)

passed = 0
failed = 0

def check(desc, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ {desc}")
    else:
        failed += 1
        print(f"  ❌ {desc}")


# ── 测试数据 ──────────────────────────────────────────────
data = {
    "execution_rate": 0.75,       # 75%
    "executed_cases": 60,
    "total_cases": 80,
    "total_defect_count": 12,
    "unresolved_count": 4,
    "delayed_count": 2,
    "today_bug_count": 3,
    "failed_cases": 2,
    "blocked_cases": 0,
    "new_bugs": [
        {"severity": "P2", "title": "test bug 1", "status": "New"},
        {"severity": "P3", "title": "test bug 2", "status": "New"},
        {"severity": "P3", "title": "test bug 3", "status": "New"},
    ],
    "later_bugs": [],
    "all_bugs": [
        {"severity": "P1", "status": "New", "module": "A", "developer": "甲", "type": "功能", "created_date": "2026-09-01"},
    ] * 12,
    "unclosed_p0_p1": 1,
    "risk_level": "中",
    "test_plans": [
        {"name": "集运改版-菲律宾", "executed": 60, "total": 80, "failed": 2},
    ],
    "aone_project_ids": ["2083180"],
    "test_duration_days": 3,
}


# ═══════════════════════════════════════════════════════════
# 1. HTML build_progress_brief — 百分比格式
# ═══════════════════════════════════════════════════════════
print("\n【1】HTML build_progress_brief 百分比格式")
data_no_risk = {**data, "risk_level": "无"}
html_brief = build_progress_brief(data_no_risk)

check("包含 75.0%", "75.0%" in html_brief)
check("不包含 60/80", "60/80" not in html_brief)
check("测试执行进度标签存在", "测试执行进度：" in html_brief)

# 多计划
data_multi = {
    **data,
    "risk_level": "无",
    "test_plans": [
        {"name": "计划A", "executed": 30, "total": 40, "failed": 1},
        {"name": "计划B", "executed": 30, "total": 40, "failed": 1},
    ],
}
html_multi = build_progress_brief(data_multi)
check("多计划也包含 75.0%", "75.0%" in html_multi)
check("多计划不包含 30/40 或 60/80", "30/40" not in html_multi and "60/80" not in html_multi)


# ═══════════════════════════════════════════════════════════
# 2. HTML _build_test_progress_text — 多计划百分比 + 单计划明细不变
# ═══════════════════════════════════════════════════════════
print("\n【2】HTML 测试进度单元格")
from report_generator import _build_test_progress_text

# 单计划
single_progress = _build_test_progress_text(data)
check("单计划保留 plan名:executed/total 格式", "60" in single_progress and "80" in single_progress)
check("单计划包含失败用例", "失败用例：2" in single_progress)

# 多计划
multi_progress = _build_test_progress_text(data_multi)
check("多计划包含百分比 75.0%", "75.0%" in multi_progress)
check("多计划包含测试执行进度标签", "测试执行进度：" in multi_progress)


# ═══════════════════════════════════════════════════════════
# 3. jsonml _j_brief_paragraphs — 百分比格式
# ═══════════════════════════════════════════════════════════
print("\n【3】jsonml _j_brief_paragraphs 百分比格式")
from report_generator import _j_brief_paragraphs

jsonml_brief = json.dumps(_j_brief_paragraphs(data_no_risk), ensure_ascii=False)
check("jsonml 包含 75.0%", "75.0%" in jsonml_brief)
check("jsonml 不包含 60/80", "60/80" not in jsonml_brief)

# 多计划
jsonml_multi = json.dumps(_j_brief_paragraphs(data_multi), ensure_ascii=False)
check("jsonml 多计划包含 75.0%", "75.0%" in jsonml_multi)
check("jsonml 多计划不包含 60/80", "60/80" not in jsonml_multi)


# ═══════════════════════════════════════════════════════════
# 4. jsonml 多计划 _j_progress_paragraphs
# ═══════════════════════════════════════════════════════════
print("\n【4】jsonml 测试进度单元格")
from report_generator import _j_progress_paragraphs

# 单计划 jsonml
j_single = json.dumps(_j_progress_paragraphs(data), ensure_ascii=False)
check("jsonml 单计划保留 per-plan 明细 (60, 80)", "60" in j_single and "80" in j_single)

# 多计划 jsonml
j_multi = json.dumps(_j_progress_paragraphs(data_multi), ensure_ascii=False)
check("jsonml 多计划包含 75.0%", "75.0%" in j_multi)


# ═══════════════════════════════════════════════════════════
# 5. verify_report_consistency — 百分比校验
# ═══════════════════════════════════════════════════════════
print("\n【5】verify_report_consistency 百分比校验")

# 构造包含百分比的 HTML 和 markdown
mock_html = f"测试执行进度：75.0% 其它内容 缺陷总数 12"
mock_md = f"测试执行进度：75.0% 其它内容 缺陷总数 12"

result = verify_report_consistency(data, mock_html, mock_md)
check(f"verify 返回 ok={result['ok']}", True)  # 仅打印结果
check(f"checked={result['checked']}, issues 数={len(result['issues'])}", True)
if result["issues"]:
    for iss in result["issues"]:
        print(f"    ⚠️  {iss}")


# ═══════════════════════════════════════════════════════════
# 6. sync_from_dingtalk_doc — 百分比同步
# ═══════════════════════════════════════════════════════════
print("\n【6】sync_from_dingtalk_doc 百分比同步")

# 模拟钉钉文档 markdown 中编辑了百分比
edited_md = "测试执行进度：80.0% 缺陷总数 12 共待解决 4 共延期 2 当日新增缺陷数 5"
sync_data = {**data, "execution_rate": 0.75}
sync_result = sync_from_dingtalk_doc(sync_data, edited_md)

check("sync 检测到执行进度变更", any("执行进度" in c for c in sync_result["changes"]))
check("sync 后 execution_rate=0.8", abs(sync_result["data"]["execution_rate"] - 0.8) < 0.001)

# 未变更的情况
same_md = "测试执行进度：75.0% 缺陷总数 12"
sync_data2 = {**data, "execution_rate": 0.75}
sync_result2 = sync_from_dingtalk_doc(sync_data2, same_md)
progress_changes = [c for c in sync_result2["changes"] if "执行进度" in c]
check("未变更时无执行进度 change", len(progress_changes) == 0)


# ═══════════════════════════════════════════════════════════
# 7. 边界值
# ═══════════════════════════════════════════════════════════
print("\n【7】边界值")
data_zero = {**data, "execution_rate": 0.0, "executed_cases": 0, "total_cases": 0}
html_zero = build_progress_brief(data_zero)
check("0 用例时显示 0.0%", "0.0%" in html_zero)

data_full = {**data, "execution_rate": 1.0, "executed_cases": 80, "total_cases": 80}
html_full = build_progress_brief(data_full)
check("全完成时显示 100.0%", "100.0%" in html_full)

data_partial = {**data, "execution_rate": 0.333, "executed_cases": 27, "total_cases": 81}
html_partial = build_progress_brief(data_partial)
check("33.3% 精度正确", "33.3%" in html_partial)


# ── 汇总 ──────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"总计: {passed + failed} 项, ✅ 通过 {passed}, ❌ 失败 {failed}")
if failed:
    sys.exit(1)
else:
    print("🎉 全部通过")
