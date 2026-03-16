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

logger.error("[xterfusion] imported main OK (regex hook version)")


@register(
    "astrbot_plugin_xterfusion",
    "sakikosunchaser",
    "群聊检测 only feels like -> 发送 split.mp3 语音（NapCat / aiocqhttp）",
    "v1.2.1",
    "https://github.com/sakikosunchaser/astrbot_plugin_xterfusion",
)
class XterFusionPlugin(Star):
    def __init__(self, context: Context, config: Optional[dict] = None):
        super().__init__(context)
        self.config = config or {}

        # 关键词 & 行为
        self.keyword = self.config.get("keyword", "only feels like")
        self.ignore_case = bool(self.config.get("ignore_case", True))
        self.cooldown_seconds = int(self.config.get("cooldown_seconds", 10))
        self.group_only = bool(self.config.get("group_only", True))

        # 音频 raw
        self.audio_raw_url = self.config.get(
            "audio_raw_url",
            "https://raw.githubusercontent.com/sakikosunchaser/astrbot_plugin_xterfusion/main/split.mp3",
        ).strip()

        # 缓存路径
        base_data_dir = Path(os.getenv("ASTRBOT_DATA_DIR", "data"))
        self.cache_dir = base_data_dir / "plugins_data" / "xterfusion"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.audio_path = self.cache_dir / "split.mp3"

        flags = re.IGNORECASE if self.ignore_case else 0
        self._pattern = re.compile(re.escape(self.keyword), flags=flags)

        self._last_trigger_ts_by_group: dict[str, float] = {}

        logger.error(
            f"[xterfusion] init OK. keyword={self.keyword!r}, ignore_case={self.ignore_case}, "
            f"group_only={self.group_only}, cooldown={self.cooldown_seconds}s, "
            f"raw={self.audio_raw_url}, cache={self.audio_path}"
        )

    async def _ensure_audio_cached(self):
        if self.audio_path.exists() and self.audio_path.stat().st_size > 0:
            return

        if httpx is None:
            raise RuntimeError("httpx not installed. Please add requirements.txt: httpx>=0.27.0")

        logger.error(f"[xterfusion] downloading split.mp3 from {self.audio_raw_url}")
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            r = await client.get(self.audio_raw_url)
            r.raise_for_status()
            data = r.content

        tmp = self.audio_path.with_suffix(".mp3.tmp")
        tmp.write_bytes(data)
        tmp.replace(self.audio_path)
        logger.error(f"[xterfusion] cached audio: {self.audio_path} size={self.audio_path.stat().st_size}")

    async def _trigger(self, event: AstrMessageEvent):
        # 只群聊（避免 send_private_msg ApiNotAvailable）
        if self.group_only and not event.is_group_message():
            logger.error("[xterfusion] matched in non-group message, ignored due to group_only")
            return

        gid = str(event.get_group_id()) if event.is_group_message() else "private"
        now = time.time()
        last = self._last_trigger_ts_by_group.get(gid, 0.0)
        if now - last < self.cooldown_seconds:
            logger.error(f"[xterfusion] cooldown hit gid={gid}")
            return
        self._last_trigger_ts_by_group[gid] = now

        try:
            await self._ensure_audio_cached()
        except Exception as e:
            logger.error(f"[xterfusion] ensure_audio_cached failed: {e}")
            yield event.plain_result("语音资源准备失败（下载/缓存失败）。")
            return

        audio_abs = str(self.audio_path.resolve())
        cq1 = f"[CQ:record,file=file:///{audio_abs}]"
        cq2 = f"[CQ:record,file={audio_abs}]"

        logger.error(f"[xterfusion] sending record. audio_abs={audio_abs}")

        if hasattr(event, "raw_result"):
            try:
                yield event.raw_result(cq1)
                return
            except Exception as e:
                logger.error(f"[xterfusion] send style1 failed: {e}")
            yield event.raw_result(cq2)
            return

        yield event.plain_result(cq1)


# 这里用 filter.regex 订阅：只要消息文本里出现关键词就触发
# 由于你开启 ignore_case，因此 regex 用 (?i) 做不区分大小写
@filter.regex(r"(?i)only feels like")
async def xterfusion_regex_entry(self: XterFusionPlugin, event: AstrMessageEvent):
    # 额外防御：再次确认一下 message_str 里确实包含关键词
    text = (event.message_str or "").strip()
    logger.error(f"[xterfusion] regex hit, text={text!r}")
    if not self._pattern.search(text):
        return
    async for r in self._trigger(event):
        yield r
