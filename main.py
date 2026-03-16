import os
import time
import base64
from astrbot.api import logger
from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter, AstrMessageEvent

COOLDOWN = 8    # 每群8秒防刷屏

# 填写你实际MP3语音路径（改为你的实际路径！）
VOICE_PATH = r"D:\split\split.mp3"

@register(
    "astrbot_plugin_xterfusion",
    "sakikosunchaser",
    "本地mp3关键词base64语音插件终极版",
    "v2.0.0",
    "https://github.com/sakikosunchaser/astrbot_plugin_xterfusion",
)
class XterFusionPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.last_group_send = {}

    def _is_trigger(self, message: str):
        # 定义关键词触发逻辑，例如只要消息里包含 "only feels like" 就播
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

    # 发送 base64 语音
    try:
        logger.info(f"[xterfusion] 正在发送本地base64语音: {VOICE_PATH}")
        with open(VOICE_PATH, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        cq = f"[CQ:record,file=base64://{b64}]"
        if hasattr(event, "raw_result"):
            yield event.raw_result(cq)
        elif hasattr(event, "plain_result"):
            yield event.plain_result(cq)
    except Exception as e:
        logger.error(f"[xterfusion] base64语音发送失败: {e}")
        if hasattr(event, "plain_result"):
            yield event.plain_result("语音文件base64发送失败！请检查路径和文件。")
