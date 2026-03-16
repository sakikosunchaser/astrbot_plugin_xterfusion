import os
import json
import time
import random
from pathlib import Path
from astrbot.api import logger
from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter, AstrMessageEvent

AUDIO_DIR = Path(os.path.dirname(__file__))        # 音频、main.py、rules.json 同目录
RULES_FILE = AUDIO_DIR / "rules.json"
COOLDOWN = 8    # 每群8秒防刷屏

@register(
    "astrbot_plugin_xterfusion",
    "sakikosunchaser",
    "本地mp3关键词单条语音-仿新三国风格",
    "v1.8.0",
    "https://github.com/sakikosunchaser/astrbot_plugin_xterfusion",
)
class XterFusionPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.rules = self._load_rules()
        self.last_group_send = {}

    def _load_rules(self):
        try:
            with open(RULES_FILE, "r", encoding="utf-8") as f:
                rules = json.load(f)
            logger.info(f"[xterfusion] 成功加载关键词规则: {len(rules)} 条")
            return rules
        except Exception as e:
            logger.error(f"[xterfusion] 加载 rules.json 失败: {e}")
            return []

    def _match_audios(self, message: str):
        results = []
        for rule in self.rules:
            keyword = rule.get("keyword", "")
            audio = rule.get("audio", "")
            if keyword and keyword in message:
                audio_path = AUDIO_DIR / audio
                if audio_path.exists():
                    results.append(audio_path)
                else:
                    logger.warning(f"[xterfusion] 缺失音频: {audio_path}")
        return results

@filter.event_message_type(filter.EventMessageType.ALL)
async def xterfusion_on_message(self: XterFusionPlugin, event: AstrMessageEvent):
    msg = event.message_str or ""
    msg_obj = getattr(event, "message_obj", None)
    group_id = getattr(msg_obj, "group_id", None) if msg_obj else None
    if not group_id:
        return  # 只响应该插件仅限群聊
    # 防刷
    now = time.time()
    if now - self.last_group_send.get(group_id, 0) < COOLDOWN:
        return
    # 匹配关键词
    matched = self._match_audios(msg)
    if not matched:
        return
    self.last_group_send[group_id] = now
    # 只发首个/随机一个音频（完全仿新三国）
    audio_path = random.choice(matched)
    logger.info(f"[xterfusion] 命中，发送语音: {audio_path}")
    cq = f"[CQ:record,file=file:///{audio_path.resolve()}]"
    if hasattr(event, "raw_result"):
        yield event.raw_result(cq)
    elif hasattr(event, "plain_result"):
        yield event.plain_result(cq)
