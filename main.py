from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Callable, Optional

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

try:
    import httpx
except Exception:
    httpx = None

logger.error("[xterfusion] imported astrbot_plugin_xterfusion.main (runtime) OK")


def _pick_group_decorator() -> Optional[Callable]:
    """
    在 v4.19.5 里 filter.on_message 不存在，所以这里从常见名字里挑一个实际存在的群消息装饰器。
    你装好后看日志里打印的 dir(filter)，我也可以再帮你改成“精确名字”。
    """
    candidates = [
        "group_message",
        "on_group_message",
        "group_msg",
        "on_group_msg",
        "group",
        "on_group",
    ]
    for name in candidates:
        dec = getattr(filter, name, None)
        if callable(dec):
            logger.error(f"[xterfusion] using filter decorator: filter.{name}()")
            return dec
    return None


@register(
    "astrbot_plugin_xterfusion",
    "sakikosunchaser",
    "群聊检测 only feels like -> 发送 split.mp3 语音（NapCat / aiocqhttp）",
    "v1.2.0",
    "https://github.com/sakikosunchaser/astrbot_plugin_xterfusion",
)
class XterFusionPlugin(Star):
    def __init__(self, context: Context, config: Optional[dict] = None):
        super().__init__(context)
        self.config = config or {}

        # 打印 filter 可用方法（用于确认到底有哪些装饰器）
        try:
            names = [n for n in dir(filter) if not n.startswith("_")]
            logger.error("[xterfusion] dir(filter) = " + ", ".join(names))
        except Exception as e:
            logger.error(f"[xterfusion] dump dir(filter) failed: {e}")

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

        self._last_trigger_ts_by_group: dict[str, float] = {}

        logger.error(
            f"[xterfusion] init OK. keyword={self.keyword!r}, ignore_case={self.ignore_case}, "
            f"cooldown={self.cooldown_seconds}s, raw={self.audio_raw_url}, cache={self.audio_path}"
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
        logger.error(f"[xterfusion] audio cached: {self.audio_path} ({self.audio_path.stat().st_size} bytes)")

    async def handle_group_message(self, event: AstrMessageEvent):
        # 只处理群消息（避免 send_private_msg ApiNotAvailable）
        if not event.is_group_message():
            return

        gid = str(event.get_group_id())
        text = (event.message_str or "").strip()

        logger.error(f"[xterfusion] incoming group={gid} text={text!r}")

        if not text or not self._pattern.search(text):
            return

        now = time.time()
        last = self._last_trigger_ts_by_group.get(gid, 0.0)
        if now - last < self.cooldown_seconds:
            logger.error(f"[xterfusion] cooldown hit for group={gid}")
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

        logger.error(f"[xterfusion] sending record, audio_abs={audio_abs}")

        if hasattr(event, "raw_result"):
            try:
                yield event.raw_result(cq1)
                return
            except Exception as e:
                logger.error(f"[xterfusion] send style1 failed: {e}")
            yield event.raw_result(cq2)
            return

        # 没 raw_result 就退化
        yield event.plain_result(cq1)


# --- 绑定群消息装饰器（必须在模块 import 时执行） ---
_group_dec = _pick_group_decorator()
if _group_dec is None:
    logger.error("[xterfusion] ERROR: cannot find group message decorator on filter.*")
else:
    @_group_dec()
    async def _xterfusion_group_entry(self: XterFusionPlugin, event: AstrMessageEvent):
        async for r in self.handle_group_message(event):
            yield r
