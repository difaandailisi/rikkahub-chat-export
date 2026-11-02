#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rikka_unpack.py —— RikkaHub 整包备份(.db / zip) -> 人类可读 (.md / .txt / .pdf)

RikkaHub 的「设置 -> 备份与恢复 -> 导出为文件」会打出一个 zip，
里面是 rikka_hub.db (SQLite) + settings.json + upload/。
这个脚本把 db 里的聊天记录抽取出来，转成 Markdown / 纯文本 / PDF，
并且保留 AI 的思考过程(reasoning)。

用法:
  python3 rikka_unpack.py <输入> [--out 输出目录] [--fmt md,txt,pdf] [--no-reasoning]

  输入可以是:
    - 一个 .zip 备份文件
    - 一个包含 rikka_hub.db 的目录
    - 直接是 rikka_hub.db 文件
"""

import argparse
import json
import os
import sqlite3
import sys
import zipfile
import tempfile
import shutil
from datetime import datetime, timezone

# ----------------------------------------------------------------------------
# 数据库读取
# ----------------------------------------------------------------------------

def find_db(path):
    """从 zip / 目录 / 直接 db 文件中定位 rikka_hub.db，返回 (db_path, cleanup_temp)。"""
    if os.path.isfile(path) and path.lower().endswith(".zip"):
        tmp = tempfile.mkdtemp(prefix="rikka_")
        with zipfile.ZipFile(path) as z:
            z.extractall(tmp)
        db = os.path.join(tmp, "rikka_hub.db")
        if not os.path.exists(db):
            # 某些备份嵌套一层目录，递归找
            for root, _, files in os.walk(tmp):
                if "rikka_hub.db" in files:
                    db = os.path.join(root, "rikka_hub.db")
                    break
        return db, tmp
    if os.path.isdir(path):
        db = os.path.join(path, "rikka_hub.db")
        if not os.path.exists(db):
            for root, _, files in os.walk(path):
                if "rikka_hub.db" in files:
                    db = os.path.join(root, "rikka_hub.db")
                    break
        return db, None
    if os.path.isfile(path):
        return path, None
    raise FileNotFoundError(f"找不到 rikka_hub.db: {path}")


def list_tables(conn):
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {r[0] for r in cur.fetchall()}


def load_conversations(db_path):
    """读取所有会话及其消息节点，返回 list[dict]。"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    tables = list_tables(conn)

    conversations = []
    if "conversation" in tables:
        rows = conn.execute(
            "SELECT id, title, create_at, update_at, assistant_id, is_pinned "
            "FROM conversation ORDER BY update_at DESC"
        ).fetchall()
    else:
        rows = []

    for c in rows:
        cid = c["id"]
        nodes = []
        if "message_node" in tables:
            node_rows = conn.execute(
                "SELECT messages, select_index FROM message_node "
                "WHERE conversation_id=? ORDER BY node_index ASC",
                (cid,),
            ).fetchall()
            for nr in node_rows:
                try:
                    msgs = json.loads(nr["messages"]) if nr["messages"] else []
                except Exception:
                    msgs = []
                sel = nr["select_index"] or 0
                if isinstance(msgs, list) and msgs:
                    if 0 <= sel < len(msgs):
                        nodes.append(msgs[sel])
                    else:
                        nodes.append(msgs[-1])
        conversations.append({
            "id": cid,
            "title": c["title"] or "(无标题)",
            "create_at": c["create_at"],
            "update_at": c["update_at"],
            "assistant_id": c["assistant_id"],
            "is_pinned": bool(c["is_pinned"]),
            "messages": nodes,
        })
    conn.close()
    return conversations


# ----------------------------------------------------------------------------
# 消息解析
# ----------------------------------------------------------------------------

ROLE_LABEL = {
    "system": "系统",
    "user": "用户",
    "assistant": "助手",
    "tool": "工具",
}

def norm_role(role):
    if not role:
        return "用户"
    return ROLE_LABEL.get(str(role).lower(), str(role))


def fmt_ts(ts):
    """把时间戳(millis)或 ISO 字符串尽量整理成可读时间。"""
    if ts is None:
        return ""
    if isinstance(ts, (int, float)):
        try:
            # 毫秒时间戳
            dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        except Exception:
            return str(ts)
    s = str(ts)
    return s.replace("T", " ").replace("Z", "")[:19]


def safe_text(v):
    return v if isinstance(v, str) else ("" if v is None else str(v))


def render_parts(parts, fmt, depth=0):
    """把 parts 渲染成对应格式的文本片段。fmt in {'md','txt','pdf'}。"""
    out = []
    for part in (parts or []):
        if not isinstance(part, dict):
            continue
        ptype = part.get("type", "")
        if ptype == "text":
            t = safe_text(part.get("text"))
            if fmt == "txt":
                import re
                t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
            out.append(t)
        elif ptype == "reasoning":
            reasoning = safe_text(part.get("reasoning"))
            if not reasoning.strip():
                continue
            if fmt == "md":
                block = "\n".join("> " + ln for ln in reasoning.splitlines())
                out.append("**思考过程：**\n" + block)
            elif fmt == "txt":
                block = "\n".join("  > " + ln for ln in reasoning.splitlines())
                out.append("[思考过程]\n" + block)
            else:  # pdf
                out.append("思考过程：\n" + reasoning)
        elif ptype in ("image", "video", "audio"):
            url = safe_text(part.get("url"))
            label = {"image": "图片", "video": "视频", "audio": "音频"}[ptype]
            if url.startswith("data:"):
                out.append(f"[{label}：内嵌媒体，已省略 base64]")
            elif url.startswith("file://"):
                out.append(f"[{label}：本地文件 {url}]")
            else:
                if fmt == "md":
                    out.append(f"![{label}]({url})")
                else:
                    out.append(f"[{label}] {url}")
        elif ptype == "document":
            url = safe_text(part.get("url"))
            name = safe_text(part.get("fileName")) or "文件"
            if fmt == "md":
                out.append(f"[📎 {name}]({url})" if url.startswith("http") else f"[文件：{name} {url}]")
            else:
                out.append(f"[文件：{name}] {url}")
        elif ptype in ("tool", "server_tool"):
            name = safe_text(part.get("toolName"))
            inp = safe_text(part.get("input"))
            try:
                parsed = json.loads(inp) if inp else None
                inp_show = json.dumps(parsed, ensure_ascii=False, indent=2) if parsed else inp
            except Exception:
                inp_show = inp
            header = f"工具调用：{name}" if name else "工具调用"
            if fmt == "md":
                out.append(f"**{header}**\n```json\n{inp_show}\n```")
            elif fmt == "txt":
                out.append(f"[{header}]\n输入: {inp_show}")
            else:
                out.append(f"{header}\n输入: {inp_show}")
            # 递归渲染工具输出
            out_parts = part.get("output") or []
            if out_parts:
                sub = render_parts(out_parts, fmt, depth + 1)
                out.append("\n".join(sub))
        elif ptype in ("tool_call", "tool_result"):
            name = safe_text(part.get("toolName"))
            out.append(f"[旧版工具数据：{name}]")
        elif ptype == "search":
            out.append("[搜索]")
        # 其它未知类型忽略
    return out


# ----------------------------------------------------------------------------
# 各格式渲染
# ----------------------------------------------------------------------------

def render_conversation(conv, fmt):
    title = conv["title"]
    lines = []
    if fmt == "md":
        lines.append(f"# {title}\n")
        meta = []
        if conv.get("create_at"):
            meta.append(f"- 创建时间：{fmt_ts(conv['create_at'])}")
        if conv.get("update_at"):
            meta.append(f"- 更新时间：{fmt_ts(conv['update_at'])}")
        if conv.get("is_pinned"):
            meta.append("- 已置顶")
        if meta:
            lines.append("\n".join(meta) + "\n")
    elif fmt == "txt":
        lines.append("=" * 60)
        lines.append(f"会话：{title}")
        if conv.get("create_at"):
            lines.append(f"创建时间：{fmt_ts(conv['create_at'])}")
        if conv.get("update_at"):
            lines.append(f"更新时间：{fmt_ts(conv['update_at'])}")
        lines.append("=" * 60)
    else:  # pdf 由调用方处理，这里返回纯文本流
        lines.append(title)
        lines.append("")

    for msg in conv["messages"]:
        role = norm_role(msg.get("role"))
        parts_text = render_parts(msg.get("parts", []), fmt)
        body = "\n\n".join(p for p in parts_text if p)
        if not body.strip():
            continue
        if fmt == "md":
            lines.append(f"### {role}\n")
            lines.append(body)
            lines.append("")
        elif fmt == "txt":
            ts = fmt_ts(msg.get("createdAt"))
            head = f"--- {role} ---" + (f"  ({ts})" if ts else "")
            lines.append(head)
            lines.append(body)
            lines.append("")
        else:
            lines.append(f"【{role}】")
            lines.append(body)
            lines.append("")
    return "\n".join(lines)


# ----------------------------------------------------------------------------
# PDF 生成 (reportlab, 自带中文 CID 字体 STSong-Light)
# ----------------------------------------------------------------------------

def render_pdf(conversations, out_path, include_reasoning=True):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        cjk = "STSong-Light"
    except Exception:
        cjk = "Helvetica"

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontName=cjk, fontSize=18)
    h3 = ParagraphStyle("h3", parent=styles["Heading3"], fontName=cjk, fontSize=12)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontName=cjk, fontSize=10, leading=15)
    meta = ParagraphStyle("meta", parent=styles["BodyText"], fontName=cjk, fontSize=9, textColor="#555555")

    def esc(s):
        return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                .replace("\n", "<br/>"))

    doc = SimpleDocTemplate(out_path, pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm)
    flow = []
    for i, conv in enumerate(conversations):
        flow.append(Paragraph(esc(conv["title"]), h1))
        m = []
        if conv.get("create_at"):
            m.append(f"创建：{fmt_ts(conv['create_at'])}")
        if conv.get("update_at"):
            m.append(f"更新：{fmt_ts(conv['update_at'])}")
        if m:
            flow.append(Paragraph(esc("　".join(m)), meta))
        flow.append(Spacer(1, 6))
        for msg in conv["messages"]:
            role = norm_role(msg.get("role"))
            # 复用 render_parts 的纯文本版本 (fmt='pdf')
            parts_text = render_parts(msg.get("parts", []), "pdf")
            body_text = "\n\n".join(p for p in parts_text if p)
            if not body_text.strip():
                continue
            flow.append(Paragraph(f"【{role}】", h3))
            flow.append(Paragraph(esc(body_text), body))
            flow.append(Spacer(1, 8))
        if i != len(conversations) - 1:
            flow.append(PageBreak())
    doc.build(flow)


# ----------------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------------

def sanitize(name):
    bad = '<>:"/\\|?*'
    s = "".join("_" if ch in bad else ch for ch in name)
    return s[:60] or "untitled"


def main():
    ap = argparse.ArgumentParser(description="RikkaHub 备份解包 -> md/txt/pdf")
    ap.add_argument("input", help=".zip 备份 / 含 db 的目录 / rikka_hub.db")
    ap.add_argument("--out", default="rikka_export", help="输出目录")
    ap.add_argument("--fmt", default="md,txt,pdf", help="输出格式, 逗号分隔")
    ap.add_argument("--no-reasoning", action="store_true", help="不包含思考过程")
    ap.add_argument("--only", default="", help="只导出标题包含此关键字的会话")
    args = ap.parse_args()

    fmts = [f.strip().lower() for f in args.fmt.split(",") if f.strip()]
    if not fmts:
        fmts = ["md"]

    db_path, tmp = find_db(args.input)
    if not os.path.exists(db_path):
        print(f"[错误] 未找到 rikka_hub.db：{db_path}", file=sys.stderr)
        sys.exit(1)

    print(f"[读取] {db_path}")
    conversations = load_conversations(db_path)
    if args.only:
        conversations = [c for c in conversations if args.only in c["title"]]
    print(f"[发现] {len(conversations)} 个会话")

    if not args.no_reasoning:
        # 统计是否真的有 reasoning，给用户一个提示
        has = any(any(p.get("type") == "reasoning" for m in c["messages"] for p in (m.get("parts") or []))
                  for c in conversations)
        if not has:
            print("[提示] 这些会话里没有 reasoning(思考过程) 数据——"
                  "这通常是因为当时用的模型/供应商没有把思考回传给 RikkaHub。")

    os.makedirs(args.out, exist_ok=True)

    # 逐会话输出
    for conv in conversations:
        base = os.path.join(args.out, sanitize(conv["title"]))
        for fmt in fmts:
            if fmt == "md":
                with open(base + ".md", "w", encoding="utf-8") as f:
                    f.write(render_conversation(conv, "md"))
            elif fmt == "txt":
                with open(base + ".txt", "w", encoding="utf-8") as f:
                    f.write(render_conversation(conv, "txt"))
        print(f"[导出] {conv['title']}")

    # 合并 PDF
    if "pdf" in fmts:
        pdf_path = os.path.join(args.out, "全部会话.pdf")
        render_pdf(conversations, pdf_path)
        print(f"[导出] {pdf_path}")

    # 索引
    idx = os.path.join(args.out, "index.txt")
    with open(idx, "w", encoding="utf-8") as f:
        f.write(f"共 {len(conversations)} 个会话\n")
        for c in conversations:
            f.write(f"- {c['title']}  (消息 {len(c['messages'])} 条)\n")

    if tmp:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"[完成] 输出目录：{os.path.abspath(args.out)}")


if __name__ == "__main__":
    main()
