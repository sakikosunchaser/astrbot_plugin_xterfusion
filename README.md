# split_voice_trigger - aiocqhttp 插件（触发发送本地 split.MP3 语音）

功能概述
- 当任意群聊或私聊收到内容精确等于 `only feels like`（去除首尾空白）时，
  机器人会发送一条语音消息，内容来自本地的 `split.MP3` 文件。

前置条件
- go-cqhttp（或其他 OneBot 实现）与本插件运行在同一台主机（你选择的 A）。
- 已把仓库 clone 到该主机，且 `split.MP3` 位于插件所在目录（或设置为绝对路径）。
- Python 3.8+，已安装 requirements.txt 中的依赖。

安装与运行
1. 在运行 go-cqhttp 的同一台机器上，clone 你的仓库并进入插件目录：
   ```
   git clone https://github.com/sakikosunchaser/astrbot_plugin_xterfusion.git
   cd astrbot_plugin_xterfusion
   ```

   确保文件 `split.MP3` 与 `split_voice_trigger.py` 在同一目录（或你知道绝对路径）。

2. 安装依赖：
   ```
   pip install -r requirements.txt
   ```

3. 配置（可选）
   - 直接使用默认：插件会使用同目录下的 `split.MP3`。
   - 或者通过环境变量指定绝对路径（优先级高于 config.yaml）：
     - MP3_PATH=/absolute/path/to/split.MP3
     - KEYWORD（可选）：修改匹配词（默认 "only feels like"）
     - LISTEN_SCOPE（可选）：both / group / private
     - CQHTTP_API（可选）：如果你需要 aiocqhttp 使用 go-cqhttp 的 HTTP API 主动发送消息，请设置（例如 http://127.0.0.1:5700）。

   示例（Linux）：
   ```
   export MP3_PATH="/home/qqbot/astrbot_plugin_xterfusion/split.MP3"
   export KEYWORD="only feels like"
   export LISTEN_SCOPE="both"
   export CQHTTP_API="http://127.0.0.1:5700"  # 可选
   ```

4. 在 go-cqhttp 配置回调到插件：
   - 本插件默认在启动时监听 0.0.0.0:5701（可通过 PLUGIN_HOST、PLUGIN_PORT 环境变量修改）。
   - 在 go-cqhttp 的 `reverse` / `http` 回调配置中，将回调地址指向插件（例如 http://127.0.0.1:5701/）。

5. 启动插件：
   ```
   python split_voice_trigger.py
   ```

注意事项
- 因为 go-cqhttp 会在服务器端读取 `file=` 指定的本地路径并发送语音，确保 `MP3_PATH` 指向的文件对运行 go-cqhttp 的用户可读。
- 如果 go-cqhttp 在另一台机器（不是当前选择的 A），请把 `split.MP3` 放到 go-cqhttp 可访问的位置或使用 HTTP URL，并把 MP3_PATH 指向该 URL（那种情形我会给你另一版配置）。
- 如果你希望忽略大小写匹配、仅在群触发、或添加同用户冷却（防刷），告诉我我会帮你修改代码。

示例运行命令（最简单）：
```
# 假设你已在仓库根目录，且 split.MP3 与脚本同目录
python split_voice_trigger.py
```

有问题或想要修改行为（例如：忽略大小写 / 仅群聊 / 添加冷却 / 自动下载 split.MP3），回复我我会直接修改并把新文件发给你。
