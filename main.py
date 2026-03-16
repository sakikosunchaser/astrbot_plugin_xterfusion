#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aiocqhttp 插件：当收到精确等于 "only feels like" 的消息时，发送本地 split.MP3 作为语音（record）。

行为：
- 优先使用环境变量 MP3_PATH / KEYWORD / LISTEN_SCOPE（环境变量优先）。
- 否则使用 config.yaml 中的配置（若存在）。
- 默认 MP3 路径为与本脚本同目录下的 split.MP3（相对路径 ./split.MP3 -> 解析为绝对路径）。
- 在群内触发则回群，在私聊触发则回私聊。

安装依赖参考 requirements.txt。
"""
import os
import logging
import yaml
from aiocqhttp import CQHttp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("split_voice_trigger")

# 默认 config 文件路径（同目录下的 config.yaml）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")

def load_config():
    # defaults
    cfg = {
        "keyword": "only feels like",
        # default to split.MP3 in same directory as this script
        "mp3_path": os.path.join(BASE_DIR, "split.MP3"),
        "listen_scope": "both",  # both / group / private
    }

    # override from environment
    if os.environ.get("KEYWORD"):
        cfg["keyword"] = os.environ["KEYWORD"]
    if os.environ.get("MP3_PATH"):
        cfg["mp3_path"] = os.environ["MP3_PATH"]
    if os.environ.get("LISTEN_SCOPE"):
        cfg["listen_scope"] = os.environ["LISTEN_SCOPE"]

    # override from yaml if present (lowest priority compared to env)
    if os.path.exists(DEFAULT_CONFIG_PATH):
        try:
            with open(DEFAULT_CONFIG_PATH, "r", encoding="utf-8") as f:
                y = yaml.safe_load(f) or {}
            if "keyword" in y:
                cfg["keyword"] = y["keyword"]
            if "mp3_path" in y:
                cfg["mp3_path"] = y["mp3_path"]
            if "listen_scope" in y:
                cfg["listen_scope"] = y["listen_scope"]
        except Exception as e:
            logger.warning("读取 config.yaml 失败：%s", e)

    # normalize mp3_path: expanduser, make absolute if relative
    mp3 = cfg["mp3_path"]
    mp3 = os.path.expanduser(mp3)
    if not os.path.isabs(mp3):
        mp3 = os.path.abspath(os.path.join(BASE_DIR, mp3))
    cfg["mp3_path"] = mp3

    return cfg

config = load_config()
KEYWORD = config["keyword"].strip()
MP3_PATH = config["mp3_path"]
LISTEN_SCOPE = config.get("listen_scope", "both").lower()

logger.info("配置：KEYWORD=%r, MP3_PATH=%r, LISTEN_SCOPE=%r", KEYWORD, MP3_PATH, LISTEN_SCOPE)

# 如果需要通过 HTTP API 主动调用 go-cqhttp，请设置环境变量 CQHTTP_API（如 http://127.0.0.1:5700）
api_root = os.environ.get("CQHTTP_API")
bot = CQHttp(api_root=api_root) if api_root else CQHttp()

def message_to_text(ctx):
    # 尝试获取文本消息内容，支持 raw_message 或 message segments
    if not ctx:
        return ""
    if "raw_message" in ctx and isinstance(ctx["raw_message"], str):
        return ctx["raw_message"]
    if "message" in ctx:
        m = ctx["message"]
        if isinstance(m, str):
            return m
        if isinstance(m, list):
            parts = []
            for seg in m:
                if isinstance(seg, dict) and seg.get("type") == "text":
                    parts.append(seg.get("text", ""))
                elif isinstance(seg, str):
                    parts.append(seg)
            return "".join(parts)
    return ""

def should_listen_for(scope, ctx):
    if scope == "both":
        return True
    if scope == "group" and "group_id" in ctx:
        return True
    if scope == "private" and "user_id" in ctx and "group_id" not in ctx:
        return True
    return False

@bot.on_message()
async def on_message(ctx):
    try:
        if not should_listen_for(LISTEN_SCOPE, ctx):
            return

        text = message_to_text(ctx)
        if text is None:
            return

        # 精确匹配：去除首尾空白后完全等于 KEYWORD
        if text.strip() != KEYWORD:
            return

        # 检查本地文件存在（用户选择 A：与 go-cqhttp 在同一主机）
        if not os.path.exists(MP3_PATH):
            logger.error("MP3 文件不存在：%s", MP3_PATH)
            # 可选择回复提示
            if "group_id" in ctx:
                await bot.send_group_msg(group_id=ctx["group_id"], message="语音文件未找到（管理员错误配置）。")
            else:
                await bot.send_private_msg(user_id=ctx.get("user_id"), message="语音文件未找到（管理员错误配置）。")
            return

        # 发送 CQ 码 record 段，file 字段使用本地绝对路径
        # go-cqhttp 会在服务器端读取该文件并发送语音
        cq_record = f"[CQ:record,file={MP3_PATH}]"
        if "group_id" in ctx:
            await bot.send_group_msg(group_id=ctx["group_id"], message=cq_record)
            logger.info("在群 %s 触发，发送语音 %s", ctx["group_id"], MP3_PATH)
        else:
            await bot.send_private_msg(user_id=ctx.get("user_id"), message=cq_record)
            logger.info("在私聊 %s 触发，发送语音 %s", ctx.get("user_id"), MP3_PATH)

    except Exception as e:
        logger.exception("处理消息时发生错误：%s", e)

if __name__ == "__main__":
    # 作为独立服务启动，默认 host 0.0.0.0 port 5701（与 go-cqhttp 的回调地址对应）
    host = os.environ.get("PLUGIN_HOST", "0.0.0.0")
    port = int(os.environ.get("PLUGIN_PORT", 5701))
    logger.info("启动插件监听 %s:%s（api_root=%r）", host, port, api_root)
    bot.run(host=host, port=port)
