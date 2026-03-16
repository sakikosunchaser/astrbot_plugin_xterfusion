from __future__ import annotations
import os
import time
import json
import base64
from pathlib import Path

from astrbot.api import logger
from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter, AstrMessageEvent

AUDIO_DIR = Path(os.path.dirname(__file__))
RULES_FILE = AUDIO_DIR / "rules.json"

@register(
    "astrbot_plugin_xterfusion",
    "sakikosunchaser",
    "关键词命中单条语音-本地mp3-base64兼容",
    "v1.7.0",
    "https://github.com/sakikosunchaser/astrbot_plugin_xterfusion",
)
class XterFusionPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.last_group_send = {}
        self.rules = self._load_rules()

    def _load_rules(self):
        try:
            with open(RULES_FILE, "r", encoding="utf-8") as f:
                rules = json.load(f)
            logger.info(f"[xterfusion] 加载关键词条目 {len(rules)} 条")
            return rules
        except Exception as e:
            logger.error(f"[xterfusion] 读取 rules.json 失败: {e}")
            return []

    def _find_audio(self, msg: str):
        # 优先找最长匹配（避免 foo, foobar, foo 匹配冲突）
        matches = [
            rule for rule in self.rules
            if rule.get("keyword") and rule["keyword"] in msg
        ]
        if not matches:
            return None
        # 按关键词长度降序排，取第一条
        matches.sort(key=lambda r: len(r["keyword"]), reverse=True)
        audio_file = matches[0]["audio"]
        audio_path = AUDIO_DIR / audio_file
        if audio_path.exists():
            return audio_path
        else:
            logger.error(f"[xterfusion] 音频不存在: {audio_path}")
            return None

@filter.event_message_type(filter.EventMessageType.ALL)
async def xterfusion_on_message(self: XterFusionPlugin, event: AstrMessageEvent):
    msg = event.message_str or ""
    msg_obj = getattr(event, "message_obj", None)
    group_id = getattr(msg_obj, "group_id", None) if msg_obj else None
    if not group_id:
        return  # 只允许群聊
    # 查找是否有命中的关键词
    aud = self._find_audio(msg)
    if not aud:
        return
    # 防刷屏
    now = time.time()
    if now - self.last_group_send.get(group_id, 0) < 8:
        logger.error(f"[xterfusion] cooldown for group {group_id}, ignore")
        return
    self.last_group_send[group_id] = now

    # 优先 base64 发送
    try:
        with open(aud, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        cq_base64 = f"[CQ:record,file=base64://{b64}]"
        logger.error(f"[xterfusion] send record base64 CQ ({aud})")
        if hasattr(event, "raw_result"):
            yield event.raw_result(cq_base64)
            return
        elif hasattr(event, "plain_result"):
            yield event.plain_result(cq_base64)
            return
    except Exception as e:
        logger.error(f"[xterfusion] base64语音生成失败: {e}")

    # 如 base64 异常/失败，则退回 file 路径
    cq_file = f"[CQ:record,file=file:///{aud.resolve()}]"
    logger.error(f"[xterfusion] send record file CQ: {cq_file}")
    if hasattr(event, "raw_result"):
        yield event.raw_result(cq_file)
    elif hasattr(event, "plain_result"):
        yield event.plain_result(cq_file)
