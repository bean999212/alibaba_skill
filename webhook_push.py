#!/usr/bin/env python3
"""
Send a daily report summary card to a DingTalk group via webhook robot.

Usage:
  # CLI args mode:
  python webhook_push.py --project "Bonus中文版" --risk "🟡中" --total 50 --unresolved 7 --doc-url "https://..."

  # JSON stdin mode:
  echo '{"project":"Bonus中文版","risk_level":"🟡中",...}' | python webhook_push.py --json
"""
import json, sys, argparse, os, urllib.request, urllib.error
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "webhook_config.json")


def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"ERROR: Config not found: {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return json.load(f)


def send_webhook(webhook_url, title, markdown_text):
    payload = {
        "msgtype": "markdown",
        "markdown": {"title": title, "text": markdown_text}
    }
    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            if result.get("errcode") == 0:
                print(f"OK: {title}")
            else:
                print(f"WARN: {result}", file=sys.stderr)
            return result
    except urllib.error.URLError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return {"errcode": -1, "errmsg": str(e)}


def build_markdown(data):
    project = data.get("project", "项目")
    risk = data.get("risk_level", "⚪无")
    total = data.get("total_defects", "N/A")
    unresolved = data.get("unresolved", "N/A")
    today_new = data.get("today_new", "0")
    progress = data.get("test_progress", "")
    doc_url = data.get("doc_url", "")
    date_str = data.get("date", datetime.now().strftime("%m-%d"))
    prefix = data.get("title_prefix", "测试日报")

    lines = [
        f"### {prefix} - {date_str}",
        f"",
        f"**项目**: {project}",
        f"",
        f"**风险等级**: {risk}",
        f"",
        f"**缺陷概况**: 总计 **{total}** 个 | 待解决 **{unresolved}** 个 | 当日新增 **{today_new}** 个",
    ]

    if progress:
        lines.extend(["", f"**测试进度**: {progress}"])

    if doc_url:
        lines.extend(["", f"> [查看完整日报]({doc_url})"])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Push daily report card to DingTalk group via webhook")
    parser.add_argument("--project", help="Project name")
    parser.add_argument("--risk", help="Risk level, e.g. 🟡中")
    parser.add_argument("--total", help="Total defect count")
    parser.add_argument("--unresolved", help="Unresolved defect count")
    parser.add_argument("--today-new", help="Today's new defect count", default="0")
    parser.add_argument("--progress", help="Test execution progress, e.g. 85%%")
    parser.add_argument("--doc-url", help="URL to full report document")
    parser.add_argument("--date", help="Report date, default MM-DD today")
    parser.add_argument("--json", action="store_true", help="Read full JSON data from stdin")
    parser.add_argument("--preview", action="store_true",
                        help="Preview mode: print markdown card to stdout instead of sending to group")
    parser.add_argument("--preview-json", action="store_true",
                        help="Preview mode: also print the data dict as JSON for agent review/edit")
    args = parser.parse_args()

    config = load_config()

    if not config.get("enabled", True):
        print("Webhook push disabled in config")
        return

    webhook_url = config["webhook_url"]
    prefix = config.get("title_prefix", "测试日报")

    if args.json:
        data = json.load(sys.stdin)
    else:
        data = {
            "project": args.project or "项目",
            "risk_level": args.risk or "⚪无",
            "total_defects": args.total or "N/A",
            "unresolved": args.unresolved or "N/A",
            "today_new": args.today_new or "0",
            "test_progress": args.progress or "",
            "doc_url": args.doc_url or "",
            "date": args.date or datetime.now().strftime("%m-%d"),
            "title_prefix": prefix,
        }

    date_str = data.get("date", datetime.now().strftime("%m-%d"))
    title = f"{prefix} - {date_str}"
    md = build_markdown(data)

    # Preview mode: output for user review, do NOT send to group
    if args.preview or args.preview_json:
        print("=== 推送卡片预览 ===")
        print(md)
        if args.preview_json:
            print("\n=== 数据 JSON ===")
            print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    send_webhook(webhook_url, title, md)


if __name__ == "__main__":
    main()
