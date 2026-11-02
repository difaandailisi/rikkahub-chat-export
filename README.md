# RikkaHub 聊天记录和文件导出 · RikkaHub Chat & File Export

> 把 RikkaHub「备份与恢复」导出的备份，还原成人类可读的 **Markdown / TXT / PDF**，包含 AI 的思考过程。
> 纯本地解析，数据不出设备。提供 **网页版（零安装 / 离线）** 与 **Python 命令行版**。
>
> Turn a RikkaHub backup into readable **Markdown / TXT / PDF**, including the AI's reasoning.
> 100% local parsing — your data never leaves your device. **Zero-install web app** + **Python CLI**.

**[▶ 在线使用 / Live demo](https://difaandailisi.github.io/rikkahub-chat-export/)**

---

## 这个工具解决什么问题 · The Problem

RikkaHub（[rikkahub/rikkahub](https://github.com/rikkahub/rikkahub)）的
「设置 → 备份与恢复 → 导出为文件」会打出一个 zip：

```
rikkahub_backup_YYYYMMDD_HHMMSS.zip
├── rikka_hub.db     # SQLite 数据库，所有聊天记录都在这里
├── settings.json    # 应用设置
└── upload/          # 你发过的图片和文件
```

这个 zip **只能导回 RikkaHub**，不能直接阅读；手动解压后得到的 `.db` 也不是给人看的。
本工具读取其中的 SQLite 数据库，把每个会话还原成可读文档，**包括思考过程（reasoning）、
工具调用、图片与文件引用**。

> RikkaHub's "Backup & Restore → Export to file" produces a zip that can only be
> imported back into the app. This tool reads the SQLite database inside and renders
> every conversation as a readable document — **with reasoning, tool calls, images and files**.

---

## 功能 · Features

### 网页版 / Web app (`index.html`)

| 功能 Feature | 说明 Description |
|---|---|
| 直读备份 zip / Read the zip directly | 不用手动解压，自动定位 `rikka_hub.db` / Auto-finds the db, no manual unzip |
| 兼容 .db / Drops in a `.db` | 也可直接选择解压后的 `rikka_hub.db` / Pick the extracted db file directly |
| 批量解析 / Batch parse | 一次解析全部会话，按更新时间排序 / All conversations, sorted by update time |
| 思考过程 / Reasoning | `reasoning` 以引用块完整保留 / Kept as blockquotes |
| 工具调用 / Tool calls | 工具名 + 输入 JSON + 输出（递归含图片/文件）/ Recursive, incl. nested media |
| 图片·视频·音频·文件 / Media | 网络地址渲染为链接，本地/base64 如实标注 / Links, paths or inline notes |
| 分支选择 / Branch selection | 只导出当前选中分支（`select_index`），与 App 一致 / Matches the app |
| 下载 MD / TXT | 每个会话一键下载 / One-click per conversation |
| 另存 PDF / Save as PDF | 调起浏览器打印，中文排版 / Browser print, CJK layout |
| 打包下载全部 / Download all | 全部会话打包为 zip / Bundle everything into a zip |
| 零安装·离线 / Zero-install & offline | 单文件自包含，不联网、不上传 / Single self-contained file, no network |

### Python 命令行版 / CLI (`rikka_unpack.py`)

| 功能 Feature | 说明 Description |
|---|---|
| 三种输入 / 3 input types | `.zip` / 解压目录 / `rikka_hub.db` |
| 三种输出 / 3 output types | `.md` / `.txt` / 合并 `.pdf`（reportlab + 中文字体） |
| 思考过程开关 / Reasoning toggle | 默认导出；`--no-reasoning` 关闭 / On by default |
| 会话过滤 / Filter | `--only 关键字` 只导出标题匹配 / Only titles containing keyword |
| 无思考提示 / Missing-reasoning hint | 库里没有 reasoning 时提示原因 / Explains why |
| 导出索引 / Index | 生成 `index.txt` 列出会话与消息数 / Lists conversations |

---

## 在线使用 · Use Online

打开 **https://difaandailisi.github.io/rikkahub-chat-export/**，选择你导出的 `.zip`（或 `.db`）即可。
零安装，手机 / 电脑浏览器均可；完全离线运行，聊天数据不会上传到任何服务器。
也可以把仓库里的 `index.html` 下载下来，永久离线使用。

> Open the link above, pick your `.zip` (or `.db`). Works on phone and desktop.
> Fully offline — nothing is uploaded. You can also download `index.html` for permanent offline use.

## Python 命令行 · CLI

```bash
pip install reportlab
python3 rikka_unpack.py 你的备份.zip --out 导出目录 --fmt md,txt,pdf
# 输入可以是 .zip / 解压后的目录 / rikka_hub.db
# --no-reasoning 不导出思考过程；--only 关键字 只导出匹配会话
```

PDF 使用 reportlab 自带的中文 CID 字体（STSong-Light），无需额外字体文件。

## 示例输出 · Sample Output

见 [`sample/`](sample/)：一份包含「思考过程 + 正文 + 工具调用 + 图片」的会话，导出为
Markdown、TXT 与合并 PDF（用按真实表结构构造的测试库生成）。

## 数据存储原理 · How It Works

- 聊天记录在 `message_node` 表：`conversation_id` + `node_index`（顺序）+ `messages`（JSON）+ `select_index`（选中分支）
- `conversation` 表存标题、时间、置顶；其 `nodes` 列在新版恒为 `"[]"`
- 每条 `UIMessage` 含 `role` 与 `parts[]`，`parts` 用 `type` 区分
  `text / reasoning / image / video / audio / document / tool / server_tool / ...`
- 完整表结构、JSON 格式与扩展指南见 [`AGENTS.md`](AGENTS.md)（写给 AI / 二次开发者）

## 常见问题 · FAQ

**导出的内容里没有思考过程？ · No reasoning in the output?**
当时的模型 / 供应商没有把思考内容回传给 RikkaHub，备份里本来就没有这条数据，任何工具都无法恢复。
The model/provider didn't return reasoning to RikkaHub, so it isn't in the backup at all.

**隐私安全吗？ · Is it private?**
安全。网页版全部在浏览器本地计算，无网络请求（库已内联）；命令行版只读本地文件。
Do not send your backup to any untrusted third party.

## 致谢 · Credits

- [rikkahub/rikkahub](https://github.com/rikkahub/rikkahub) — 数据格式来源 / data format source
- [sql.js](https://github.com/sql-js/sql.js) — SQLite in WebAssembly
- [JSZip](https://github.com/Stuk/jszip) — browser-side zip

## 许可证 · License

[MIT](LICENSE)
