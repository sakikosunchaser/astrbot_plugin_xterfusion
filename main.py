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
except Exception:  # pragma: no cover
    httpx = None


@register(
    "astrbot_plugin_xterfusion",
    "sakikosunchaser",
    "检测到关键词 only feels like 就发送 split.mp3 语音（NapCat / aiocqhttp）",
    "1.2.0",
    "https://github.com/sakikosunchaser/astrbot_plugin_xterfusion",
)
class XterFusionPlugin(Star):
    def __init__(self, context: Context, config: Optional[dict] = None):
        super().__init__(context)
        self.config = config or {}

        # 触发关键词
        self.keyword = self.config.get("keyword", "only feels like")
        self.ignore_case = bool(self.config.get("ignore_case", True))

        # 防刷屏冷却（秒）
        self.cooldown_seconds = int(self.config.get("cooldown_seconds", 10))

        # 是否只在群聊触发
        self.group_only = bool(self.config.get("group_only", True))

        # split.mp3 raw 下载地址（仓库 main 分支根目录 split.mp3）
        self.audio_raw_url = self.config.get(
            "audio_raw_url",
            "https://raw.githubusercontent.com/sakikosunchaser/astrbot_plugin_xterfusion/main/split.mp3",
        ).strip()

        # 缓存目录：优先使用 ASTRBOT_DATA_DIR（若未设置则用 data/）
        base_data_dir = Path(os.getenv("ASTRBOT_DATA_DIR", "data"))
        self.cache_dir = base_data_dir / "plugins_data" / "xterfusion"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.audio_path = self.cache_dir / "split.mp3"

        # 冷却记录（按群/私聊 session）
        self._last_trigger_ts: dict[str, float] = {}

        flags = re.IGNORECASE if self.ignore_case else 0
        self._pattern = re.compile(re.escape(self.keyword), flags=flags)

        logger.info(
            f"[xterfusion] loaded. keyword={self.keyword!r}, ignore_case={self.ignore_case}, "
            f"group_only={self.group_only}, cooldown={self.cooldown_seconds}s, "
            f"audio_raw_url={self.audio_raw_url}, cache={self.audio_path}"
        )

    @filter.on_message()
    async def on_message(self, event: AstrMessageEvent):
        # 1) 群聊限制
        if self.group_only and not event.is_group_message():
            return

        # 2) 匹配关键词
        text = (event.message_str or "").strip()
        if not text or not self._pattern.search(text):
            return

        # 3) 冷却
        session_key = self._session_key(event)
        now = time.time()
        last = self._last_trigger_ts.get(session_key, 0.0)
        if now - last < self.cooldown_seconds:
            return
        self._last_trigger_ts[session_key] = now

        # 4) 确保音频已缓存
        try:
            await self._ensure_audio_cached()
        except Exception as e:
            logger.error(f"[xterfusion] ensure_audio_cached failed: {e}")
            yield event.plain_result("语音资源准备失败（下载或缓存失败），请检查网络/配置。")
            return

        # 5) 发送语音（CQ:record）
        audio_abs = str(self.audio_path.resolve())
        logger.info(f"[xterfusion] trigger -> send record: {audio_abs}")

        # 兼容尝试 1：file=file:///abs/path
        cq1 = f"[CQ:record,file=file:///{audio_abs}]"
        try:
            yield event.raw_result(cq1)
            return
        except Exception as e:
            logger.warning(f"[xterfusion] send record style1 failed: {e}")

        # 兼容尝试 2：file=/abs/path
        cq2 = f"[CQ:record,file={audio_abs}]"
        yield event.raw_result(cq2)

    def _session_key(self, event: AstrMessageEvent) -> str:
        if event.is_group_message():
            return f"g:{event.get_group_id()}"
        return f"p:{event.get_sender_id()}"

    async def _ensure_audio_cached(self):
        if self.audio_path.exists() and self.audio_path.stat().st_size > 0:
            return

        if not self.audio_raw_url:
            raise RuntimeError("audio_raw_url is empty.")

        if httpx is None:
            raise RuntimeError(
                "httpx not installed. Add httpx to plugin requirements or install it in AstrBot env."
            )

        logger.info(f"[xterfusion] downloading split.mp3 from {self.audio_raw_url}")
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            r = await client.get(self.audio_raw_url)
            r.raise_for_status()
            data = r.content

        tmp = self.audio_path.with_suffix(".mp3.tmp")
        tmp.write_bytes(data)
        tmp.replace(self.audio_path)
