import os
import json
import time
import random
from pathlib import Path
from astrbot.api import logger
from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter, AstrMessageEvent

COOLDOWN = 8    # 每群8秒防刷屏

# Windows 本地绝对路径
CQ_PATH = r"C:\Users\22849\Downloads\split.mp3"

@register(
    "astrbot_plugin_xterfusion",
    "sakikosunchaser",
    "本地绝对路径mp3关键词单条语音- Win修正版",
    "v1.8.3",
    "https://github.com/sakikosunchaser/astrbot_plugin_xterfusion",
)
class XterFusionPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.last_group_send = {}

    def _is_trigger(self, message: str):
        # 你自定义关键词，这里假设包含"only feels like"
        return "only feels like" in message

@filter.event_message_type(filter.EventMessageType.ALL)
async def xterfusion_on_message(self: XterFusionPlugin, event: AstrMessageEvent):
    msg = event.message_str or ""
    msg_obj = getattr(event, "message_obj", None)
    group_id = getattr(msg_obj, "group_id", None) if msg_obj else None
    if not group_id:
        return
    now = time.time()
    if now - self.last_group_send.get(group_id, 0) < COOLDOWN:
        return
    if not self._is_trigger(msg):
        return
    self.last_group_send[group_id] = now

    # 修正路径格式，适配Windows
    cq_path = CQ_PATH.replace("\\", "/")   # C:/Users/22849/Downloads/split.mp3
    cq = f"[CQ:record,file=file:///{cq_path}]"
    logger.info(f"[xterfusion] send record file CQ: {cq}")
    if hasattr(event, "raw_result"):
        yield event.raw_result(cq)
    elif hasattr(event, "plain_result"):
        yield event.plain_result(cq)
