from __future__ import annotations

from astrbot.api import logger
from astrbot.api.star import Context, Star, register

logger.error("[xterfusion] imported astrbot_plugin_xterfusion.main OK")

@register(
    "astrbot_plugin_xterfusion",
    "sakikosunchaser",
    "debug import test",
    "v1.1.1",
    "https://github.com/sakikosunchaser/astrbot_plugin_xterfusion",
)
class XterFusionPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        logger.error("[xterfusion] XterFusionPlugin __init__ OK")
