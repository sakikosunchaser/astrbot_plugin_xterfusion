import os
import json
import random
import time
from pathlib import Path
from astrbot.api import logger
from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter, AstrMessageEvent
import astrbot.api.message_components as Comp

# 配置目录（你只需保证所有mp3放这个文件夹）
BASE_DIR = Path(os.path.dirname(__file__))
AUDIO_DIR = BASE_DIR / "data" / "sound"
RULES_FILE = BASE_DIR / "rules.json"
COOLDOWN = 8   # 每群8秒防刷屏

@register(
    "astrbot_plugin_xterfusion",
    "sakikosunchaser",
    "新三国风格本地磁盘mp3关键词发语音",
    "v2.0.0",
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
                # mp3 放在 data/sound 文件夹，防路径拼写问题
                audio_path = AUDIO_DIR / audio
                if audio_path.exists():
                    results.append({"keyword": keyword, "audio_path": str(audio_path)})
                else:
                    logger.warning(f"[xterfusion] 缺失音频: {audio_path}")
        return results

@filter.event_message_type(filter.EventMessageType.ALL)
async def xterfusion_on_message(self: XterFusionPlugin, event: AstrMessageEvent):
    msg = event.message_str or ""
    msg_obj = getattr(event, "message_obj", None)
    group_id = getattr(msg_obj, "group_id", None) if msg_obj else None
    if not group_id:
        return
    now = time.time()
    if now - self.last_group_send.get(group_id, 0) < COOLDOWN:
        return
    matched = self._match_audios(msg)
    if not matched:
        return
    self.last_group_send[group_id] = now
    # 随机选一个音频（与新三国一致）
    audio_info = random.choice(matched)
    audio_path = audio_info["audio_path"]
    logger.info(f"[xterfusion] 命中「{audio_info['keyword']}」，发送语音: {audio_path}")

    try:
        yield event.chain_result([
            Comp.Record(file=audio_path, url=audio_path)
        ])
    except Exception as e:
        logger.error(f"[xterfusion] 发语音失败: {e}")
        if hasattr(event, "plain_result"):
            yield event.plain_result("语音文件发送失败，请检查文件路径和权限。")
