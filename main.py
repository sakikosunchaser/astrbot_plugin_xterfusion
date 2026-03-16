from __future__ import annotations
import os
import time
import base64
from pathlib import Path

from astrbot.api import logger
from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter, AstrMessageEvent

KEYWORD = "only feels like"
VOICE_CACHE_FILENAME = "split.mp3"

@register(
    "astrbot_plugin_xterfusion",
    "sakikosunchaser",
    "群聊等值匹配关键词base64+文件语音插件",
    "v1.6.0",
    "https://github.com/sakikosunchaser/astrbot_plugin_xterfusion",
)
class XterFusionPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.last_group_send = {}
        # split.mp3 和 main.py 必须在同一目录
        self.voice_path = Path(os.path.dirname(__file__)) / VOICE_CACHE_FILENAME

@filter.event_message_type(filter.EventMessageType.ALL)
async def xterfusion_on_message(self: XterFusionPlugin, event: AstrMessageEvent):
    # 消息必须完全等于 only feels like（可忽略前后空格）
    msg = event.message_str.strip() if hasattr(event, "message_str") else ""
    msg_obj = getattr(event, "message_obj", None)
    group_id = getattr(msg_obj, "group_id", None) if msg_obj else None
    logger.error(f"[xterfusion] xterfusion_on_message: group_id={group_id}, msg={msg!r}")
    if not group_id:
        return  # 只允许群聊
    if msg.lower() != KEYWORD:
        return  # 只允许完全等于关键词的消息触发
    now = time.time()
    if now - self.last_group_send.get(group_id, 0) < 8:
        logger.error(f"[xterfusion] cooldown for group {group_id}, ignore")
        return
    self.last_group_send[group_id] = now

    if not self.voice_path.exists():
        logger.error(f"[xterfusion] split.mp3 本地不存在！{self.voice_path}")
        if hasattr(event, "plain_result"):
            yield event.plain_result("split.mp3 文件丢失！")
        return

    # 优先使用 base64 方式
    try:
        with open(self.voice_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        cq_base64 = f"[CQ:record,file=base64://{b64}]"
        logger.error(f"[xterfusion] send record base64 CQ")
        if hasattr(event, "raw_result"):
            yield event.raw_result(cq_base64)
            return
        elif hasattr(event, "plain_result"):
            yield event.plain_result(cq_base64)
            return
    except Exception as e:
        logger.error(f"[xterfusion] base64语音生成失败: {e}")

    # 如果 base64 不可用，退回 file 方式
    cq_file = f"[CQ:record,file=file:///{self.voice_path.resolve()}]"
    logger.error(f"[xterfusion] send record file CQ: {cq_file}")
    if hasattr(event, "raw_result"):
        yield event.raw_result(cq_file)
    elif hasattr(event, "plain_result"):
        yield event.plain_result(cq_file)
