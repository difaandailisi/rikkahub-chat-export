# AGENTS.md —— 给 AI / 二次开发者的数据格式与代码指南

本文档描述 RikkaHub 备份文件的完整存储结构，以及本仓库的代码组织。
目标：让 AI 助手或新贡献者**不读 RikkaHub 源码**也能正确解析、扩展或重写本工具。

> 数据格式逆向自开源项目 [rikkahub/rikkahub](https://github.com/rikkahub/rikkahub)（Apache-2.0）。
> 本文基于其 master 分支（数据库 schema version 32，2026-11）核对。

## 1. 备份包结构

「设置 → 备份与恢复 → 导出为文件」产出的 zip：

```
rikkahub_backup_YYYYMMDD_HHMMSS.zip
├── rikka_hub.db     # SQLite 数据库，聊天记录全部在这里
├── settings.json    # 应用设置（供应商配置、助手设定等）
└── upload/          # 用户发送的附件（图片、文件）
```

## 2. 数据库 schema（仅与本工具相关的两张表）

### conversation（会话元数据）

| 列 | 类型 | 说明 |
|---|---|---|
| id | TEXT PK | UUID 字符串 |
| assistant_id | TEXT | 所属助手 UUID |
| title | TEXT | 会话标题 |
| nodes | TEXT | **恒为 `"[]"`** —— 旧版存消息图，新版消息已迁移到 message_node 表，勿解析此列 |
| create_at / update_at | INTEGER | Unix 毫秒时间戳 |
| is_pinned | INTEGER | 0/1 置顶 |
| chat_suggestions / mode_injection_ids / lorebook_ids | TEXT | JSON 数组，本工具忽略 |
| custom_system_prompt / workspace_cwd / folder_id / config | TEXT | 可空，本工具忽略 |

### message_node（消息节点，**真正的聊天记录**）

| 列 | 类型 | 说明 |
|---|---|---|
| id | TEXT PK | 节点 UUID |
| conversation_id | TEXT FK→conversation.id | CASCADE 删除 |
| node_index | INTEGER | 节点顺序，按此排序即得到线性对话 |
| messages | TEXT | **JSON 数组**：`List<UIMessage>`，是该节点的多个「分支」（如重新生成的多个回复） |
| select_index | INTEGER | 当前选中的分支下标；`messages[select_index]` 即 UI 上显示的那条 |

**重建线性对话的规则**（与 RikkaHub `Conversation.currentMessages` 一致）：

```
for node in message_node WHERE conversation_id=? ORDER BY node_index ASC:
    msgs = json.loads(node.messages)
    pick = msgs[select_index]  # 越界时回退 msgs[-1]
    emit(pick)
```

## 3. UIMessage JSON 结构

```jsonc
{
  "id": "uuid",
  "role": "user",            // system | user | assistant | tool（不区分大小写处理）
  "parts": [ /* UIMessagePart 数组，见下 */ ],
  "createdAt": "2026-11-03T06:27:00",  // kotlinx LocalDateTime
  "finishedAt": "...",       // 可空
  "modelId": "uuid",         // 可空
  "modelSnapshot": { "modelId": "gpt-x", "displayName": "GPT X" },  // 可空，模型名快照
  "usage": { "promptTokens": 0, "completionTokens": 0, ... },       // 可空
  "generationTimeMs": 1234,  // 可空
  "stepCount": 2,            // 可空
  "isContextCheckpoint": false  // true 表示这是压缩检查点（历史摘要）
}
```

序列化配置（kotlinx.serialization）：`ignoreUnknownKeys=true`，`encodeDefaults=true`，
`explicitNulls=false` → **解析时必须容忍未知字段与缺失字段**。

## 4. UIMessagePart（多态，判别式字段为 `type`）

| type | 关键字段 | 渲染建议 |
|---|---|---|
| `text` | `text` | 正文原样输出 |
| `reasoning` | `reasoning`, `createdAt`, `finishedAt`, `reasoningType`(`reasoning_text`/`summary_text`) | 思考过程，Markdown 渲染为 `>` 引用块 |
| `image` | `url` | `http(s)` → 图片链接；`file://` → 本地路径标注；`data:` → 内嵌 base64（省略） |
| `video` / `audio` | `url` | 同 image |
| `document` | `url`, `fileName`, `mime` | 文件引用 |
| `tool` | `toolCallId`, `toolName`, `input`(JSON字符串), `output`(嵌套 UIMessagePart 数组), `approvalState` | 工具调用；**必须递归渲染 output** |
| `server_tool` | `toolCallId`, `toolName`, `input`/`output`(JsonElement), `status`(`in_progress`/`completed`/`failed`) | 服务端工具（如网页搜索） |
| `tool_call` | `toolCallId`, `toolName`, `arguments` | （旧版，已弃用） |
| `tool_result` | `toolCallId`, `toolName`, `content`, `arguments` | （旧版，已弃用） |
| `search` | — | （旧版，已弃用） |

未知 `type` 应跳过而非报错（向前兼容）。

## 5. 本仓库代码

```
index.html        网页版，单文件自包含：
                  - 内联 sql.js 1.10.3（wasm 以 base64 嵌入，经 Blob URL 加载）
                  - 内联 JSZip 3.10.1（zip 解包）
                  - 核心函数：findDb / processFile / renderParts / convToMd / convToTxt
rikka_unpack.py   Python CLI，仅标准库 + reportlab：
                  - find_db()      zip/目录/db 三种输入定位 rikka_hub.db
                  - load_conversations()  读两表并按 select_index 取分支
                  - render_parts() parts → md/txt/pdf 文本（递归工具 output）
                  - render_pdf()   reportlab + UnicodeCIDFont("STSong-Light") 中文字体
sample/           按真实结构构造的测试库的导出示例
```

修改 `index.html` 后需重新生成内联库时，参见构建方式：sql.js/JSZip 从 CDN 下载对应版本
dist 文件，wasm base64 编码后注入占位符（本仓库提交的是已生成产物，无构建步骤）。

## 6. 测试要点

1. 构造测试库：建 `conversation` + `message_node` 两表，插入含
   `reasoning` + `text` + `tool`（其 `output` 内嵌 `image`）的 assistant 消息，
   同一节点放两条分支且 `select_index=0`。
2. 断言输出：包含思考过程、工具调用、图片链接；**不包含**未选中分支的文本。
3. 网页版用 Playwright 无头浏览器验证：`setInputFiles` 分别喂 `.db` 与 `.zip`，
   等待状态栏出现「解析完成」，断言渲染区文本，并确认无 console error。

## 7. 已知边界

- `settings.json` 不解析（含供应商 API Key，**任何导出工具都不应展示它**）
- reasoning 缺失不是 bug：部分供应商不返回思考内容，备份里本来就没有
- `nodes` 列在极旧版本可能含数据，本工具按新版行为忽略；如需兼容旧备份，
  可在 `load_conversations()` 里增加 `nodes` 非空时的回退解析
