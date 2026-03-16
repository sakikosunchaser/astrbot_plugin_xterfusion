from __future__ import annotations
import os
import time
from pathlib import Path

from astrbot.api import logger
from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter, AstrMessageEvent

KEYWORD = "only feels like"
VOICE_CACHE_FILENAME = "split.mp3"

@register(
    "astrbot_plugin_xterfusion",
    "sakikosunchaser",
    "群聊关键词本地语音播放插件",
    "v1.5.0",
    "https://github.com/sakikosunchaser/astrbot_plugin_xterfusion",
)
class XterFusionPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.last_group_send = {}
        # 这里假定 split.mp3 和 main.py 同目录
        self.voice_path = Path(os.path.dirname(__file__)) / VOICE_CACHE_FILENAME

@filter.event_message_type(filter.EventMessageType.ALL)
async def xterfusion_on_message(self: XterFusionPlugin, event: AstrMessageEvent):
    msg = event.message_str.strip() if hasattr(event, "message_str") else ""
    msg_obj = getattr(event, "message_obj", None)
    group_id = getattr(msg_obj, "group_id", None) if msg_obj else None
    logger.error(f"[xterfusion] xterfusion_on_message: group_id={group_id}, msg={msg!r}")
    if not group_id:
        return  # 只允许群聊
    if KEYWORD not in msg:
        return

    now = time.time()
    if now - self.last_group_send.get(group_id, 0) < 8:
        logger.error(f"[xterfusion] cooldown for group {group_id}, ignore")
        return
    self.last_group_send[group_id] = now

    # === 本地语音文件判断 ===
    if not self.voice_path.exists():
        logger.error(f"[xterfusion] split.mp3 本地不存在！{self.voice_path}")
        if hasattr(event, "plain_result"):
            yield event.plain_result("split.mp3 文件丢失！")
        return

    cq = f"[CQ:record,file=file:///{self.voice_path.resolve()}]"
    logger.error(f"[xterfusion] send record CQ: {cq}")
    if hasattr(event, "raw_result"):
        yield event.raw_result(cq)
    elif hasattr(event, "plain_result"):
        yield event.plain_result(cq)
