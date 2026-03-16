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
except Exception:  # pragma: no cover
    httpx = None


def _pick_filter_decorator() -> tuple[Optional[Callable], Optional[Callable]]:
    """
    AstrBot 不同版本 filter 装饰器名字可能不同。
    返回： (群聊装饰器, 私聊装饰器)；可能为 None。
    """
    # 常见命名候选（按可能性从高到低排）
    group_candidates = [
        "group_message",
        "on_group_message",
        "group",
        "on_group",
        "group_msg",
    ]
    private_candidates = [
        "private_message",
        "on_private_message",
        "private",
        "on_private",
        "private_msg",
    ]

    group_dec = None
    private_dec = None

    for name in group_candidates:
        dec = getattr(filter, name, None)
        if callable(dec):
            group_dec = dec
            break

    for name in private_candidates:
        dec = getattr(filter, name, None)
        if callable(dec):
            private_dec = dec
            break

    return group_dec, private_dec


@register(
    "astrbot_plugin_xterfusion",
    "sakikosunchaser",
    "检测到关键词 only feels like 就发送 split.mp3 语音（NapCat / aiocqhttp）",
    "1.2.1",
    "https://github.com/sakikosunchaser/astrbot_plugin_xterfusion",
)
class XterFusionPlugin(Star):
    def __init__(self, context: Context, config: Optional[dict] = None):
        super().__init__(context)
        self.config = config or {}

        self.keyword = self.config.get("keyword", "only feels like")
        self.ignore_case = bool(self.config.get("ignore_case", True))
        self.cooldown_seconds = int(self.config.get("cooldown_seconds", 10))
        self.group_only = bool(self.config.get("group_only", True))

        self.audio_raw_url = self.config.get(
            "audio_raw_url",
            "https://raw.githubusercontent.com/sakikosunchaser/astrbot_plugin_xterfusion/main/split.mp3",
        ).strip()

        base_data_dir = Path(os.getenv("ASTRBOT_DATA_DIR", "data"))
        self.cache_dir = base_data_dir / "plugins_data" / "xterfusion"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.audio_path = self.cache_dir / "split.mp3"

        self._last_trigger_ts: dict[str, float] = {}

        flags = re.IGNORECASE if self.ignore_case else 0
        self._pattern = re.compile(re.escape(self.keyword), flags=flags)

        # 打印一下 filter 支持哪些方法，方便你看日志确认
        try:
            names = [n for n in dir(filter) if not n.startswith("_")]
            logger.info(f"[xterfusion] filter available: {names}")
        except Exception:
            pass

        logger.info(
            f"[xterfusion] loaded. keyword={self.keyword!r}, ignore_case={self.ignore_case}, "
            f"group_only={self.group_only}, cooldown={self.cooldown_seconds}s, "
            f"audio_raw_url={self.audio_raw_url}, cache={self.audio_path}"
        )

    async def _handle(self, event: AstrMessageEvent):
        # group_only 时，私聊处理函数也会走到这里，所以再判断一次
        if self.group_only and not event.is_group_message():
            return

        text = (event.message_str or "").strip()
        if not text or not self._pattern.search(text):
            return

        session_key = self._session_key(event)
        now = time.time()
        last = self._last_trigger_ts.get(session_key, 0.0)
        if now - last < self.cooldown_seconds:
            return
        self._last_trigger_ts[session_key] = now

        try:
            await self._ensure_audio_cached()
        except Exception as e:
            logger.error(f"[xterfusion] ensure_audio_cached failed: {e}")
            yield event.plain_result("语音资源准备失败（下载或缓存失败），请检查网络/配置）。")
            return

        audio_abs = str(self.audio_path.resolve())

        # CQ 码发送语音（NapCat 常见兼容两种写法）
        cq1 = f"[CQ:record,file=file:///{audio_abs}]"
        cq2 = f"[CQ:record,file={audio_abs}]"

        # AstrBot 不同版本可能没有 raw_result；常见还有 text_result / plain_result
        # 这里优先尝试 raw_result，没有就退化为 plain_result（你至少能看到 CQ 字符串）
        if hasattr(event, "raw_result"):
            try:
                yield event.raw_result(cq1)
                return
            except Exception as e:
                logger.warning(f"[xterfusion] send style1 failed: {e}")
            yield event.raw_result(cq2)
            return

        yield event.plain_result(cq1)

    def _session_key(self, event: AstrMessageEvent) -> str:
        if event.is_group_message():
            return f"g:{event.get_group_id()}"
        return f"p:{event.get_sender_id()}"

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


# -------- 在模块加载时，把处理函数绑定到“存在的”装饰器上 --------
_group_dec, _private_dec = _pick_filter_decorator()

if _group_dec is not None:
    @_group_dec()
    async def _xterfusion_group_handler(self: XterFusionPlugin, event: AstrMessageEvent):
        async for r in self._handle(event):
            yield r
else:
    logger.warning("[xterfusion] no group message decorator found on filter.*")

if _private_dec is not None:
    @_private_dec()
    async def _xterfusion_private_handler(self: XterFusionPlugin, event: AstrMessageEvent):
        async for r in self._handle(event):
            yield r
else:
    logger.warning("[xterfusion] no private message decorator found on filter.*")
