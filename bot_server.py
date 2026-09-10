#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
集运PC版日报机器人 - DingTalk Stream 后端服务

接收群内 @机器人 消息并回复，支持关键词触发日报生成。
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import requests as _requests
import dingtalk_stream
from dingtalk_stream import AckMessage

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
APP_KEY = "dingb5yy64wwdaxjaxeh"
APP_SECRET = "qs7wFjDJlOq2v9JTeEq6hQNZqProSqhQhNy0vMQ4DUMgheZuLh7zvc9mTLsra4sS"

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "robot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("daily-report-bot")


def _load_group_webhooks() -> dict:
    """Load openConversationId -> webhook_url mapping from groups_config.json."""
    config_path = Path(__file__).parent / "groups_config.json"
    mapping = {}
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            for g in cfg.get("groups", []):
                conv_id = g.get("group_chatId", "")
                wh = g.get("webhook_url", "")
                if conv_id and wh:
                    mapping[conv_id] = wh
                    logger.info("加载群 webhook: %s -> %s", g.get("group_name", conv_id), wh[:60] + "...")
        except Exception as e:
            logger.error("加载 groups_config.json 失败: %s", e)
    return mapping


GROUP_WEBHOOKS: dict = _load_group_webhooks()


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------
class DailyReportHandler(dingtalk_stream.ChatbotHandler):
    """处理群内 @机器人 消息"""

    def _get_group_webhook(self, msg) -> Optional[str]:
        """If message is from a known group, return its webhook URL."""
        if msg.conversation_type == "2":
            conv_id = msg.conversation_id
            wh = GROUP_WEBHOOKS.get(conv_id)
            if wh:
                return wh
            logger.warning("群消息但无匹配的 webhook: conversation_id=%s, title=%s", conv_id, msg.conversation_title)
        return None

    def reply_text(self, text, incoming_message):
        """Override: use group webhook for group messages, fallback to SDK default."""
        wh = self._get_group_webhook(incoming_message)
        if wh:
            payload = {
                "msgtype": "text",
                "text": {"content": text},
                "at": {"atUserIds": [incoming_message.sender_staff_id]},
            }
            try:
                resp = _requests.post(wh, json=payload, timeout=10)
                resp.raise_for_status()
                logger.info("群 webhook 回复成功: %s", incoming_message.conversation_title)
                return resp.json()
            except Exception as e:
                logger.error("群 webhook 回复失败: %s, 回退 session_webhook", e)
        return super().reply_text(text, incoming_message)

    def reply_markdown(self, title, text, incoming_message):
        """Override: use group webhook for group messages, fallback to SDK default."""
        wh = self._get_group_webhook(incoming_message)
        if wh:
            payload = {
                "msgtype": "markdown",
                "markdown": {"title": title, "text": text},
                "at": {"atUserIds": [incoming_message.sender_staff_id]},
            }
            try:
                resp = _requests.post(wh, json=payload, timeout=10)
                resp.raise_for_status()
                logger.info("群 webhook markdown 回复成功: %s", incoming_message.conversation_title)
                return resp.json()
            except Exception as e:
                logger.error("群 webhook markdown 回复失败: %s, 回退 session_webhook", e)
        return super().reply_markdown(title, text, incoming_message)

    async def process(self, callback: dingtalk_stream.CallbackMessage):
        incoming_message = dingtalk_stream.ChatbotMessage.from_dict(callback.data)
        text = (incoming_message.text.content or "").strip()
        sender = incoming_message.sender_nick or "unknown"
        conversation_type = incoming_message.conversation_type  # "1" = single, "2" = group

        logger.info(
            "收到消息 | 发送者: %s | 会话类型: %s | conversation_id: %s | 群名: %s | 内容: %s",
            sender,
            "群聊" if conversation_type == "2" else "单聊",
            incoming_message.conversation_id,
            incoming_message.conversation_title,
            text,
        )

        # --- 关键词路由 ---
        if any(kw in text for kw in ("日报", "测试日报", "生成日报", "发日报")):
            await self._handle_report_request(incoming_message)
        elif any(kw in text for kw in ("帮助", "help", "功能", "菜单")):
            await self._handle_help(incoming_message)
        elif any(kw in text for kw in ("状态", "进度", "bug", "缺陷")):
            await self._handle_status(incoming_message)
        else:
            await self._handle_default(incoming_message, text)

        return AckMessage.STATUS_OK, "OK"

    # -- 日报请求 --
    async def _handle_report_request(self, msg):
        reply = (
            "收到！正在为你生成集运PC版测试日报，请稍候...\n\n"
            "日报生成后将自动推送到本群。"
        )
        self.reply_text(reply, msg)
        logger.info("已回复日报生成请求")

        # TODO: 后续可在此处调用 QoderWork skill 触发日报生成
        # 目前先回复提示，实际生成仍通过 QoderWork 定时任务或手动触发

    # -- 帮助 --
    async def _handle_help(self, msg):
        help_text = (
            "**日报助手使用指南**\n\n"
            "- **日报** / **生成日报**：触发测试日报生成\n"
            "- **状态** / **进度** / **bug**：查看当前项目状态摘要\n"
            "- **帮助**：显示本菜单\n\n"
            "定时日报每天 19:00 自动推送。"
        )
        self.reply_markdown("使用指南", help_text, msg)

    # -- 状态查询 --
    async def _handle_status(self, msg):
        last_report_path = (
            Path(__file__).parent / "outputs" / ".last_report.cid3VyuIf.json"
        )
        if last_report_path.exists():
            try:
                data = json.loads(last_report_path.read_text(encoding="utf-8"))
                webhook_data = data.get("webhook_data", {})
                reply = (
                    f"**集运PC版最新状态**（{data.get('date', 'N/A')}）\n\n"
                    f"- 风险等级：{webhook_data.get('risk_level', 'N/A')}\n"
                    f"- 缺陷：总计 **{webhook_data.get('total_defects', 'N/A')}** 个"
                    f" | 待解决 **{webhook_data.get('unresolved', 'N/A')}** 个"
                    f" | 当日新增 **{webhook_data.get('today_new', 'N/A')}** 个\n"
                    f"- 测试进度：{webhook_data.get('test_progress', 'N/A')}\n"
                )
                doc_url = webhook_data.get("doc_url", "")
                if doc_url:
                    reply += f"\n[查看完整日报]({doc_url})"
                self.reply_markdown("项目状态", reply, msg)
            except Exception as e:
                self.reply_text(f"读取状态失败: {e}", msg)
        else:
            self.reply_text("暂无最新日报数据，请先发送「日报」生成一份。", msg)

    # -- 默认回复 --
    async def _handle_default(self, msg, text):
        self.reply_text(
            f"你好！我是集运PC版日报助手。\n\n"
            f"发送「帮助」查看可用指令。",
            msg,
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    logger.info("启动日报机器人 Stream 服务...")
    logger.info("AppKey: %s", APP_KEY)

    credential = dingtalk_stream.Credential(APP_KEY, APP_SECRET)
    client = dingtalk_stream.DingTalkStreamClient(credential)
    client.register_callback_handler(
        dingtalk_stream.ChatbotMessage.TOPIC,
        DailyReportHandler(),
    )

    logger.info("Stream 客户端已注册，开始监听...")
    client.start_forever()


if __name__ == "__main__":
    main()
