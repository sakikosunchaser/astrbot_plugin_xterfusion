from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any, Optional

from astrbot.api import logger
from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register

try:
    import httpx
except Exception:
    httpx = None

logger.error("[xterfusion] imported main OK (aiocqhttp event compat version)")


def _get_raw_dict(event: Any) -> dict:
    """
    兼容不同 event 封装：尽量拿到 OneBot 原始事件 dict
    """
    for attr in ("raw_event", "event", "data", "raw", "payload"):
        d = getattr(event, attr, None)
        if isinstance(d, dict):
            return d
    return {}


def _is_group_message(event: Any) -> bool:
    d = _get_raw_dict(event)
    mt = d.get("message_type")
    if mt == "group":
        return True
    # 兜底：有 group_id 也认为是群消息
    return "group_id" in d


def _get_group_id(event: Any) -> Optional[int]:
    d = _get_raw_dict(event)
    gid = d.get("group_id")
    try:
        return int(gid) if gid is not None else None
    except Exception:
        return None


def _get_message_str(event: Any) -> str:
    # v4.19.5 aiocqhttp 一般有 message_str；没有则从 raw_event.message 提取
    s = getattr(event, "message_str", None)
    if isinstance(s, str):
        return s
    d = _get_raw_dict(event)
    msg = d.get("message")
    if isinstance(msg, str):
        return msg
    return ""


@register(
    "astrbot_plugin_xterfusion",
    "sakikosunchaser",
    "群聊检测 only feels like -> 发送 split.mp3 语音（NapCat / aiocqhttp）",
    "v1.2.2",
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
        logger.error(f"[xterfusion] cached audio ok, size={self.audio_path.stat().st_size}")

    async def _trigger(self, event: Any):
        is_group = _is_group_message(event)
        if self.group_only and not is_group:
            logger.error("[xterfusion] matched in private, ignored due to group_only")
            return

        gid = _get_group_id(event)
        gid_key = str(gid) if gid is not None else "private"

        now = time.time()
        last = self._last_trigger_ts_by_group.get(gid_key, 0.0)
        if now - last < self.cooldown_seconds:
            logger.error(f"[xterfusion] cooldown hit gid={gid_key}")
            return
        self._last_trigger_ts_by_group[gid_key] = now

        try:
            await self._ensure_audio_cached()
        except Exception as e:
            logger.error(f"[xterfusion] ensure_audio_cached failed: {e}")
            # event.plain_result 在 AiocqhttpMessageEvent 上一般是有的
            if hasattr(event, "plain_result"):
                yield event.plain_result("语音资源准备失败（下载/缓存失败）。")
            return

        audio_abs = str(self.audio_path.resolve())
        cq1 = f"[CQ:record,file=file:///{audio_abs}]"
        cq2 = f"[CQ:record,file={audio_abs}]"

        logger.error(f"[xterfusion] sending record. audio_abs={audio_abs} cq1={cq1}")

        if hasattr(event, "raw_result"):
            try:
                yield event.raw_result(cq1)
                return
            except Exception as e:
                logger.error(f"[xterfusion] send style1 failed: {e}")
            yield event.raw_result(cq2)
            return

        if hasattr(event, "plain_result"):
            yield event.plain_result(cq1)


@filter.regex(r"(?i)only feels like")
async def xterfusion_regex_entry(self: XterFusionPlugin, event: Any):
    text = _get_message_str(event).strip()
    logger.error(f"[xterfusion] regex hit, text={text!r}, raw_keys={list(_get_raw_dict(event).keys())}")

    if not text or not self._pattern.search(text):
        return

    async for r in self._trigger(event):
        yield r
