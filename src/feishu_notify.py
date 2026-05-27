"""
feishu_notify.py
通过飞书自建应用发送消息给指定用户
"""

import os
import json
import logging
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

FEISHU_BASE = "https://open.feishu.cn/open-apis"


def _get_token() -> str:
    resp = requests.post(
        f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal",
        json={
            "app_id": os.environ["FEISHU_APP_ID"],
            "app_secret": os.environ["FEISHU_APP_SECRET"],
        },
    )
    resp.raise_for_status()
    return resp.json()["tenant_access_token"]


def _send(text: str):
    token = _get_token()
    user_id = os.environ.get("FEISHU_USER_ID", "")
    if not user_id:
        logger.warning("FEISHU_USER_ID 未设置，跳过通知")
        return

    resp = requests.post(
        f"{FEISHU_BASE}/im/v1/messages?receive_id_type=user_id",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "receive_id": user_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}),
        },
        timeout=10,
    )
    resp.raise_for_status()
    logger.info("飞书通知发送成功")


def send_daily_report(papers: list[dict]):
    today = datetime.now().strftime("%Y-%m-%d")
    today_papers = [p for p in papers if p["source_type"] == "今日新文"]
    trending_papers = [p for p in papers if p["source_type"] == "热门方向"]

    lines = [f"📚 论文速报 {today}\n"]

    lines.append(f"🆕 今日新文（{len(today_papers)} 篇）")
    for p in today_papers[:5]:
        summary = p.get("ai_summary") or "（摘要生成中）"
        lines.append(f"• {p['title'][:50]}")
        lines.append(f"  → {summary}")
        lines.append(f"  {p['arxiv_url']}")
    if len(today_papers) > 5:
        lines.append(f"  ...还有 {len(today_papers)-5} 篇，查看多维表格")

    lines.append(f"\n🔥 热门方向（{len(trending_papers)} 篇）")
    for p in trending_papers[:3]:
        summary = p.get("ai_summary") or "（摘要生成中）"
        lines.append(f"• {p['title'][:50]}")
        lines.append(f"  → {summary}")
        lines.append(f"  {p['arxiv_url']}")

    lines.append("\n📊 https://my.feishu.cn/base/QEIsbVwrJaCQRMsDx3ycrjcrnsb")
    _send("\n".join(lines))


def send_weekly_report(papers: list[dict]):
    week_str = datetime.now().strftime("%Y 第%W周")
    lines = [f"📖 每周自研方向报告 {week_str}\n"]
    lines.append(f"共找到 {len(papers)} 篇相关论文\n")

    for p in papers[:8]:
        summary = p.get("ai_summary") or "（摘要生成中）"
        lines.append(f"• {p['title'][:55]}")
        lines.append(f"  关键词：{p['keywords_hit']}")
        lines.append(f"  → {summary}")
        lines.append(f"  {p['arxiv_url']}\n")

    lines.append("📊 https://my.feishu.cn/base/QEIsbVwrJaCQRMsDx3ycrjcrnsb")
    _send("\n".join(lines))
