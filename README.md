# RikkaHub 备份解包 (rikka-unpack)

> 把 RikkaHub 的「备份与恢复」导出文件，还原成人类可读的 **Markdown / TXT / PDF**。
> 纯本地解析，数据从不离开你的设备。提供 **网页版（零安装）** 与 **Python 命令行版**。

RikkaHub（[rikkahub/rikkahub](https://github.com/rikkahub/rikkahub)）的
「设置 → 备份与恢复 → 导出为文件」会打出一个 zip，里面是 `rikka_hub.db`（SQLite 数据库）、
`settings.json` 和 `upload/` 附件目录。这个 zip 的设计用途是「导回 RikkaHub」，无法直接阅读。

本工具读取其中的 SQLite 数据库，把每个会话还原成可读文档——
**包括 AI 的思考过程（reasoning）、工具调用、图片与文件引用**。

---

## 在线使用（推荐）

打开 **https://difaandailisi.github.io/rikka-unpack/** ，选择你导出的 `.zip`（或解压后的 `.db`）即可。

- 零安装，手机 / 电脑浏览器均可
- 完全离线运行（sql.js 与 JSZip 已内联进单文件），**聊天数据不会上传到任何服务器**
- 也可以下载仓库里的 `index.html` 单文件，永久离线使用

## Python 命令行版

```bash
python3 rikka_unpack.py 你的备份.zip --out 导出目录 --fmt md,txt,pdf
# 输入可以是 .zip / 解压后的目录 / rikka_hub.db 三种
# --no-reasoning 不导出思考过程；--only 关键字 只导出标题匹配的会话
```

依赖：仅 Python 3 标准库 + `reportlab`（生成 PDF 用，`pip install reportlab`）。
PDF 使用 reportlab 自带的中文 CID 字体（STSong-Light），无需额外字体文件。

## 功能一览

### 网页版（index.html）

| 功能 | 说明 |
|---|---|
| 直读备份 zip | 不用手动解压，选择 RikkaHub 导出的 `.zip` 自动找到 `rikka_hub.db` |
| 支持 .db 直读 | 也可以直接选择解压出来的 `rikka_hub.db` |
| 批量解析 | 一次性解析全部会话，按更新时间排序 |
| 思考过程还原 | `reasoning` 部分以引用块完整保留（可用 `--no-reasoning` 关闭，仅 CLI） |
| 工具调用还原 | 工具名 + 输入 JSON + 工具输出（含嵌套图片/文件）递归还原 |
| 图片 / 视频 / 音频 / 文件 | 网络地址渲染为链接，本地路径与内嵌 base64 如实标注 |
| 分支选择 | 与 RikkaHub 一致，只导出每个消息节点「当前选中」的分支（`select_index`） |
| 下载 MD / TXT | 每个会话一键下载对应格式 |
| 另存 PDF | 调起浏览器打印，保存为 PDF（中文排版） |
| 打包下载全部 | 所有会话的 MD 或 TXT 打包成一个 zip 下载 |
| 零安装 / 离线 | 单文件自包含，不联网、不上传，数据不出设备 |

### Python 命令行版（rikka_unpack.py）

| 功能 | 说明 |
|---|---|
| 三种输入 | `.zip` 备份 / 解压目录 / `rikka_hub.db` 均可 |
| 三种输出 | `.md` / `.txt` / 合并版 `.pdf`（reportlab + 中文字体） |
| 思考过程开关 | 默认导出 reasoning；`--no-reasoning` 关闭 |
| 会话过滤 | `--only 关键字` 只导出标题匹配的会话 |
| 无思考提示 | 若库里没有 reasoning 数据，会提示原因（供应商未回传思考内容） |
| 导出索引 | 生成 `index.txt` 列出全部会话及消息条数 |

## 示例输出

见 [`sample/`](sample/) 目录（用按真实表结构构造的测试库生成）：
一份包含「思考过程 + 正文 + 工具调用 + 图片」的会话导出为 Markdown、TXT 与合并 PDF。

## 数据存储原理（简版）

- 聊天记录存在 `message_node` 表：`conversation_id` + `node_index`（顺序）+ `messages`（JSON）+ `select_index`（选中分支）
- `conversation` 表保存标题、时间、置顶等元数据；其 `nodes` 列在新版中恒为 `"[]"`
- 每条消息 `UIMessage` 含 `role` 与 `parts[]`，`parts` 以 `type` 字段区分
  `text / reasoning / image / video / audio / document / tool / server_tool / tool_call / tool_result`
- 详细的表结构、JSON 格式与扩展指南见 [`AGENTS.md`](AGENTS.md)（写给 AI / 二次开发者）

## 常见问题

**导出的内容里没有思考过程？**
说明当时使用的模型 / 供应商没有把思考内容回传给 RikkaHub（例如部分供应商不返回 reasoning 字段），
备份里本身就没有这条数据，任何工具都无法凭空恢复。

**隐私安全吗？**
安全。网页版全部计算在浏览器本地完成，无任何网络请求（库已内联）；
命令行版同样只读本地文件。**请不要把备份文件发给任何不可信的第三方。**

## 致谢

- [rikkahub/rikkahub](https://github.com/rikkahub/rikkahub) — 本工具解析的数据格式来自该开源项目的存储设计，感谢原作者
- [sql.js](https://github.com/sql-js/sql.js) — SQLite 的 WebAssembly 版本
- [JSZip](https://github.com/Stuk/jszip) — 浏览器端 zip 解压

## 许可证

[MIT](LICENSE)
