from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Optional

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

try:
    import httpx
except Exception:
    httpx = None


@register(
    "astrbot_plugin_xterfusion",
    "sakikosunchaser",
    "群聊检测 only feels like -> 发送 split.mp3 语音（NapCat / aiocqhttp）",
    "1.2.2",
    "https://github.com/sakikosunchaser/astrbot_plugin_xterfusion",
)
class XterFusionPlugin(Star):
    def __init__(self, context: Context, config: Optional[dict] = None):
        super().__init__(context)
        self.config = config or {}

        self.keyword = self.config.get("keyword", "only feels like")
        self.ignore_case = bool(self.config.get("ignore_case", True))
        self.cooldown_seconds = int(self.config.get("cooldown_seconds", 10))

        self.audio_raw_url = self.config.get(
            "audio_raw_url",
            "https://raw.githubusercontent.com/sakikosunchaser/astrbot_plugin_xterfusion/main/split.mp3",
        ).strip()

        base_data_dir = Path(os.getenv("ASTRBOT_DATA_DIR", "data"))
        self.cache_dir = base_data_dir / "plugins_data" / "xterfusion"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.audio_path = self.cache_dir / "split.mp3"

        flags = re.IGNORECASE if self.ignore_case else 0
        self._pattern = re.compile(re.escape(self.keyword), flags=flags)

        self._last_trigger_ts: dict[str, float] = {}

        logger.info(f"[xterfusion] loaded. cache={self.audio_path}, raw={self.audio_raw_url}")

    async def _handle_group(self, event: AstrMessageEvent):
        # 只处理群聊，避免触发 send_private_msg -> ApiNotAvailable
        if not event.is_group_message():
            return

        text = (event.message_str or "").strip()
        if not text or not self._pattern.search(text):
            return

        gid = str(event.get_group_id())
        now = time.time()
        last = self._last_trigger_ts.get(gid, 0.0)
        if now - last < self.cooldown_seconds:
            return
        self._last_trigger_ts[gid] = now

        try:
            await self._ensure_audio_cached()
        except Exception as e:
            logger.error(f"[xterfusion] download/cache audio failed: {e}")
            yield event.plain_result("语音资源准备失败（下载或缓存失败）。")
            return

        audio_abs = str(self.audio_path.resolve())

        # CQ record 两种写法都试
        cq1 = f"[CQ:record,file=file:///{audio_abs}]"
        cq2 = f"[CQ:record,file={audio_abs}]"

        if hasattr(event, "raw_result"):
            try:
                yield event.raw_result(cq1)
                return
            except Exception as e:
                logger.warning(f"[xterfusion] send style1 failed: {e}")
            yield event.raw_result(cq2)
            return

        # 如果没有 raw_result，至少把 CQ 字符串发出去供你观察
        yield event.plain_result(cq1)

    async def _ensure_audio_cached(self):
        if self.audio_path.exists() and self.audio_path.stat().st_size > 0:
            return
        if httpx is None:
            raise RuntimeError("httpx not installed; add requirements.txt: httpx>=0.27.0")
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            r = await client.get(self.audio_raw_url)
            r.raise_for_status()
            data = r.content
        tmp = self.audio_path.with_suffix(".mp3.tmp")
        tmp.write_bytes(data)
        tmp.replace(self.audio_path)


# v4.19.5 里你没有 filter.on_message，所以这里用“猜测群消息装饰器”的兜底：
_group_dec = None
for _name in ("group_message", "on_group_message", "group", "on_group", "group_msg"):
    _d = getattr(filter, _name, None)
    if callable(_d):
        _group_dec = _d
        break

if _group_dec is None:
    logger.error("[xterfusion] 未找到群消息装饰器：请把 dir(filter) 输出贴我，我给你改成精确写法。")
else:
    @_group_dec()
    async def xterfusion_group_entry(self: XterFusionPlugin, event: AstrMessageEvent):
        async for r in self._handle_group(event):
            yield r
