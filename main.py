from __future__ import annotations

import os
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register

try:
    import httpx
except Exception:
    httpx = None

VOICE_URL = "https://raw.githubusercontent.com/sakikosunchaser/astrbot_plugin_xterfusion/main/split.mp3"
KEYWORD = "only feels like"
VOICE_CACHE_FILENAME = "split.mp3"


def _is_group_event(event) -> (bool, int | None):
    # 仿 xinsanguo_voice 的事件兼容
    e = getattr(event, "raw_event", None) or getattr(event, "event", None) or getattr(event, "data", None) or {}
    t = e.get("message_type")
    if t == "group" and "group_id" in e:
        return True, e["group_id"]
    return False, None


@register(
    "astrbot_plugin_xterfusion",
    "sakikosunchaser",
    "群聊关键词触发语音-简单版",
    "v1.3.0",
    VOICE_URL,
)
class XterFusionPlugin(Star):
    _cache_dir: Path
    _audio_path: Path

    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self._last_send = {}
        self._cache_dir = Path(os.getenv("ASTRBOT_DATA_DIR", "data")) / "plugins_data" / "xterfusion"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._audio_path = self._cache_dir / VOICE_CACHE_FILENAME
        logger.error("[xterfusion] Plugin loaded, path: %s", self._audio_path)

    async def _ensure_voice(self):
        if self._audio_path.exists() and self._audio_path.stat().st_size > 0:
            return
        if httpx is None:
            raise RuntimeError("httpx not installed")
        logger.error("[xterfusion] download mp3 from: %s", VOICE_URL)
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(VOICE_URL)
            r.raise_for_status()
            self._audio_path.write_bytes(r.content)
            logger.error("[xterfusion] voice cached: %s", self._audio_path)

    @filter.regex(KEYWORD, ignore_case=True)
    async def group_voice(self, event):
        is_group, gid = _is_group_event(event)
        msg = getattr(event, "message_str", "")
        logger.error(f"[xterfusion] check: is_group={is_group} gid={gid} msg={msg!r}")
        if not is_group:
            return  # 忽略私聊
        last = self._last_send.get(gid, 0)
        import time
        if time.time() - last < 8:  # 防刷屏
            logger.error(f"[xterfusion] cooldown; skip for {gid}")
            return
        try:
            await self._ensure_voice()
        except Exception as e:
            logger.error(f"[xterfusion] download failed: {e}")
            if hasattr(event, "plain_result"):
                yield event.plain_result("下载语音失败")
            return
        self._last_send[gid] = time.time()
        voice_file = str(self._audio_path.resolve())
        cq = f"[CQ:record,file=file:///{voice_file}]"
        logger.error(f"[xterfusion] send record: {cq}")
        if hasattr(event, "raw_result"):
            yield event.raw_result(cq)
        elif hasattr(event, "plain_result"):
            yield event.plain_result(cq)
