from __future__ import annotations
import os
from pathlib import Path
import time

from astrbot.api import logger
from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter

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
    "群聊关键词触发语音-超兼容精简",
    "v1.3.1",
    "https://github.com/sakikosunchaser/astrbot_plugin_xterfusion",
)
class XterFusionPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        # 缓存语音根目录
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

    @filter.regex(KEYWORD, ignore_case=True)
    async def g_voice(self, event):
        # 用新三国写法直接取event.raw_event
        e = getattr(event, "raw_event", None)
        # logger.error(f"[xterfusion] event.raw_event: {e!r}")
        if not isinstance(e, dict) or e.get("message_type") != "group":
            # logger.error("[xterfusion] not group, ignore")
            return
        gid = e["group_id"]
        now = time.time()
        if now - self.last_group_send.get(gid, 0) < 8:
            # logger.error(f"[xterfusion] cooldown for group {gid}, ignore")
            return
        self.last_group_send[gid] = now
        msg = getattr(event, "message_str", "")
        logger.error(f"[xterfusion] triggered! gid={gid} msg={msg!r}")
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
