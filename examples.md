# 阿拉丁 + ione 每日测试风险日报 — 使用示例

## 示例 1：完整配置

```yaml
# config.yaml
# 数据访问不使用任何 Token / API Key：
#   阿拉丁 / AAT 走 builtin_browser 已登录 tab，Aone 走 coop MCP 连接器，钉钉走 DWS 连接器。
sources:
  aat_via_browser: true
  aone_via_coop: true
  dingtalk_via_dws: true

matching:
  strategy: slice
  min_similarity: 0.6
  slice:
    cn_gram: 2
    require_all_ascii: true
    min_cn_hits: 1
  max_candidates: 5

risk_rules:
  windows:
    - days_max: 1
      execution_rate: 0.95
      pass_rate: 0.95
      unclosed_p0_p1: 0
      base_level: high
    - days_max: 3
      execution_rate: 0.80
      pass_rate: 0.90
      unclosed_p0_p1: 2
      base_level: medium
    - days_max: 7
      execution_rate: 0.60
      pass_rate: 0.85
      unclosed_p0_p1: 5
      base_level: low
    - days_max: 9999
      execution_rate: 0.30
      pass_rate: 0.80
      unclosed_p0_p1: 10
      base_level: info

report:
  title: "测试日报"
  timezone: "Asia/Shanghai"
  fallback_to_file: true
  output_dir: "./outputs"

schedule:
  default_time: "09:00"
  default_consecutive_days: 5
```

## 示例 2：模糊匹配与分两步顺序多选确认

用户触发：

> 生成「会员积分兑换」的测试日报

Agent 全局模糊搜索后，**先确认 Aone 项目（多选）**：

```
【第一步 · Aone 项目】以下为「会员积分兑换」模糊匹配到的全部 Aone 项目，请多选（如 1,2）：
1. 会员积分兑换项目（ID: 2158868，负责人：张三）
2. 会员积分兑换优化（ID: 2158869，负责人：李四）
（可关联 ione 需求：I-2001【会员积分兑换】功能缺陷 / I-2002 会员积分兑换-退款场景）
```

用户确认：

> 1,2

Agent 接着在 **AAT 测试计划列表页**（`https://aat.alibaba-inc.com/page/jointList?tabKey=tp&tid=26`）用「测试计划名称」做模糊搜索、翻页到底读取全部命中行，**再确认阿拉丁测试计划（多选）**：

```
【第二步 · 阿拉丁测试计划】以下为「会员积分兑换」在阿拉丁列表页模糊匹配到的全部测试计划，请多选（如 1,2）：
1. 会员积分兑换功能测试（ID: TP-1001，测试周期：2026-07-10~2026-07-15，状态：测试执行）
2. 会员积分兑换优化验证（ID: TP-1002，测试周期：2026-07-20~2026-08-01，状态：TC编辑中）
```

> ⚠️ 搜索测试计划必须走**列表页** `jointList?tabKey=tp`，禁止用**详情页** `jointDetail?...id=<planId>`（详情页只展示单个计划、永远只返回 1 条，是「只搜到一个」的根因）。

用户确认：

> 1,2

Agent 后续流程：

1. 记录（均为列表）`aone_project_ids = [2158868, 2158869]`、`ione_req_ids = [I-2001]`、`aladdin_test_plan_ids = [TP-1001, TP-1002]`。
2. 分别拉取每个测试计划的用例执行进度并汇总。
3. 分别拉取每个 Aone 项目的缺陷数据，按 `bug_id` 合并去重；每条缺陷用其 `aone_project_id` 生成详情页超链接。
4. 计算风险并生成报告。

## 示例 3：钉钉群列表与多选

生成日报后，Agent 拉取钉钉群列表并展示：

```
请选择要发送日报的钉钉群（可多选）：
☑ 测试质量群（chat_001）
☑ 会员积分兑换项目群（chat_002）
□ 研发团队大群（chat_003）
```

用户确认选择「测试质量群」和「会员积分兑换项目群」。

如果 DWS 未授权，Agent 会提示：

```
未检测到 DingTalk Workspace 授权，请先在 QoderWork 设置 → 连接器 → DingTalk Workspace 中完成授权，然后重新触发。
```

## 示例 4：发送方式选择

Agent 询问发送方式：

```
请选择日报发送方式：
1. 立即发送
2. 固定时间每天发送
3. 连续多日发送
```

用户选择「固定时间每天发送」并指定时间：

> 每天早上 9 点发送

Agent 创建 cron 任务：

```json
{
  "name": "daily-test-risk-report-member-points",
  "schedule": {
    "kind": "cron",
    "expr": "0 9 * * *",
    "tz": "Asia/Shanghai"
  },
  "payload": {
    "kind": "agentTurn",
    "message": "执行 aladdin-ione-daily-test-report Skill：需求「会员积分兑换」（A-1001 / I-2001），发送到钉钉群 chat_001,chat_002。"
  }
}
```

用户选择「连续多日发送」：

> 从今天开始连续 5 天，每天 9 点发送

Agent 创建 5 个一次性定时任务，或创建一个带剩余天数计数器的任务。

## 示例 5：日报输出

日报的版式必须严格参照本 Skill 内置的 HTML 模板 [`assets/report-template.html`](assets/report-template.html)：5 列表格、3 个蓝色横幅（■ 整体概述 / ■ 缺陷情况 / ■ 问题记录）、项目进度行用 rowspan 合并（风险等级 / 风险说明 / 测试进度，共 3 行，不含「今日进展」）、缺陷按 new / later 分组且每条缺陷标题为指向 Aone 详情页的超链接。

归档到钉钉文档时，将该 HTML 版式等价转换为钉钉 jsonml 表格（钉钉不渲染 HTML `<table>`），通过 `dws doc update --content-format jsonml --fix-jsonml` 写入。缺陷标题超链接的 jsonml 结构见 SKILL.md「缺陷列表格式规范（强制）」。

## 示例 6：匹配无结果时的处理

用户输入：

> 生成「积分商城」的测试日报

Agent 返回：

```
阿拉丁平台候选：无
ione 平台候选：无

未在阿拉丁或 ione 平台找到与「积分商城」匹配的需求。
可能原因：
- 需求名称与平台录入不一致（如平台中名为「会员积分兑换」）
- 该需求尚未录入两个平台

请重新输入更完整或不同的需求名称：
```

## 示例 7：数据源不可用时的降级输出

当某个数据源暂时取不到数时，报告在对应单元格标注数据来源异常，避免误导决策。例如在「测试进度」单元格填「数据来源异常（AAT 页面登录态失效）」、「缺陷情况」横幅下填「数据来源异常（coop 未返回缺陷数据）」，并在风险说明中注明「无法获取完整数据，无法评估风险，请在已登录的浏览器 tab 中重新登录 AAT / 确认 coop 连接后重新生成日报」。版式仍沿用内置 HTML 模板转换的 jsonml 表格。
