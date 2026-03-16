from __future__ import annotations
import os
import time
from pathlib import Path

from astrbot.api import logger
from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter, AstrMessageEvent

try:
    import httpx
except Exception:
    httpx = None

KEYWORD = "only feels like"
VOICE_URL = "https://raw.githubusercontent.com/sakikosunchaser/astrbot_plugin_xterfusion/main/split.mp3"
VOICE_CACHE_FILENAME = "split.mp3"

@register(
    "astrbot_plugin_xterfusion",
    "sakikosunchaser",
    "群聊关键词触发语音（仿新三国）",
    "v1.4.0",
    "https://github.com/sakikosunchaser/astrbot_plugin_xterfusion",
)
class XterFusionPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        d = os.getenv("ASTRBOT_DATA_DIR", "data")
        self.cache_path = Path(d) / "plugins_data" / "xterfusion"
        self.cache_path.mkdir(parents=True, exist_ok=True)
        self.voice_path = self.cache_path / VOICE_CACHE_FILENAME
        self.last_group_send = {}

    async def _ensure_voice(self):
        if self.voice_path.exists() and self.voice_path.stat().st_size > 0:
            return
        if httpx is None:
            raise RuntimeError("httpx not installed")
        logger.error("[xterfusion] start download mp3 ...")
        async with httpx.AsyncClient(timeout=20) as cli:
            r = await cli.get(VOICE_URL)
            r.raise_for_status()
            self.voice_path.write_bytes(r.content)
            logger.error("[xterfusion] voice download OK: %s", self.voice_path)

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
    logger.error(f"[xterfusion] READY to send voice!!")
    try:
        await self._ensure_voice()
    except Exception as er:
        logger.error(f"[xterfusion] voice download fail: {er}")
        if hasattr(event, "plain_result"):
            yield event.plain_result("语音下载失败")
        return
    cq = f"[CQ:record,file=file:///{self.voice_path.resolve()}]"
    logger.error(f"[xterfusion] send record CQ: {cq}")
    if hasattr(event, "raw_result"):
        yield event.raw_result(cq)
    elif hasattr(event, "plain_result"):
        yield event.plain_result(cq)
