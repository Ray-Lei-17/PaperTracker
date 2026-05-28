"""
fetch_arxiv.py
通过 arXiv RSS feed 拉取论文，比 API 限制宽松
- daily: 今天新出的论文
- weekly: 过去7天核心方向
- trending: 过去30天热门
"""

import yaml
import time
import random
import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

# arXiv RSS feed，按分类订阅当天新文章
RSS_URL = "https://rss.arxiv.org/rss/{category}"

# arXiv 搜索 API（备用，限速更宽松的端点）
SEARCH_URL = "https://export.arxiv.org/api/query"

HEADERS = {
    "User-Agent": "PaperTracker/1.0 (research tool; contact via GitHub)"
}


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def match_keywords(title: str, abstract: str, keywords: list) -> list:
    text = (title + " " + abstract).lower()
    return [kw for kw in keywords if kw.lower() in text]


def fetch_rss_category(category: str) -> list:
    """拉取单个分类的 RSS，返回当天论文列表"""
    url = RSS_URL.format(category=category)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"RSS 拉取失败 {category}: {e}")
        return []

    papers = []
    try:
        root = ET.fromstring(resp.content)
        ns = {"dc": "http://purl.org/dc/elements/1.1/"}
        channel = root.find("channel")
        if channel is None:
            return []

        for item in channel.findall("item"):
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            description = item.findtext("description", "").strip()
            creators = item.findall("dc:creator", ns)
            authors = ", ".join(c.text for c in creators[:5] if c.text)

            # 清理 HTML 标签
            import re
            abstract = re.sub(r"<[^>]+>", "", description).strip()

            arxiv_id = link.split("/")[-1] if link else ""

            papers.append({
                "title": title,
                "authors": authors,
                "abstract": abstract,
                "arxiv_url": link,
                "arxiv_id": arxiv_id,
                "published_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            })
    except ET.ParseError as e:
        logger.warning(f"RSS 解析失败 {category}: {e}")

    return papers


def fetch_daily(config: dict) -> list:
    """拉取今日新文：通过 RSS 获取各分类新文章，按关键词过滤"""
    logger.info("拉取今日新文（RSS）...")
    all_keywords = (
        config["keywords"]["core"]
        + config["keywords"]["related"]
        + config["keywords"]["trending"]
    )

    all_papers = []
    seen_ids = set()

    for category in config["arxiv_categories"]:
        papers = fetch_rss_category(category)
        logger.info(f"  {category}: 拉取到 {len(papers)} 篇")
        for p in papers:
            if p["arxiv_id"] in seen_ids:
                continue
            seen_ids.add(p["arxiv_id"])
            hit = match_keywords(p["title"], p["abstract"], all_keywords)
            if hit:
                p["source_type"] = "今日新文"
                p["keywords_hit"] = ", ".join(hit)
                all_papers.append(p)
        time.sleep(random.uniform(2, 5))  # 分类之间随机等待2-5秒

    logger.info(f"今日新文：找到 {len(all_papers)} 篇")
    return all_papers


def fetch_via_api(query: str, max_results: int, sort_by: str = "submittedDate") -> list:
    """通过 arXiv API 搜索，加长间隔避免限流"""
    params = {
        "search_query": query,
        "max_results": max_results,
        "sortBy": sort_by,
        "sortOrder": "descending",
        "start": 0,
    }

    for attempt in range(3):
        try:
            time.sleep(random.uniform(5, 10) + attempt * random.uniform(5, 8))  # 随机递增等待
            resp = requests.get(SEARCH_URL, params=params, headers=HEADERS, timeout=60)
            if resp.status_code == 429:
                wait = 30 * (attempt + 1)
                logger.warning(f"429 限流，等待 {wait} 秒后重试...")
                time.sleep(wait + random.uniform(0, 15))  # 限流后随机额外等待
                continue
            resp.raise_for_status()
            return _parse_atom(resp.content)
        except Exception as e:
            logger.warning(f"API 请求失败（{e}），重试 {attempt+1}/3")

    logger.error("API 请求多次失败，返回空")
    return []


def _parse_atom(content: bytes) -> list:
    """解析 arXiv API 返回的 Atom XML"""
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }
    root = ET.fromstring(content)
    papers = []

    for entry in root.findall("atom:entry", ns):
        title = entry.findtext("atom:title", "", ns).strip().replace("\n", " ")
        abstract = entry.findtext("atom:summary", "", ns).strip().replace("\n", " ")
        link = ""
        for l in entry.findall("atom:link", ns):
            if l.get("type") == "text/html":
                link = l.get("href", "")
        authors = [a.findtext("atom:name", "", ns) for a in entry.findall("atom:author", ns)]
        published = entry.findtext("atom:published", "", ns)[:10]
        arxiv_id = link.split("/")[-1] if link else ""

        papers.append({
            "title": title,
            "authors": ", ".join(authors[:5]),
            "abstract": abstract,
            "arxiv_url": link,
            "arxiv_id": arxiv_id,
            "published_date": published,
        })

    return papers


def fetch_weekly(config: dict) -> list:
    """拉取过去7天核心方向论文"""
    logger.info("拉取自研方向（过去7天）...")
    core_keywords = config["keywords"]["core"]
    kw_part = " OR ".join(f'"{kw}"' for kw in core_keywords)
    cat_part = " OR ".join(f"cat:{c}" for c in config["arxiv_categories"])
    query = f"({kw_part}) AND ({cat_part})"

    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    raw = fetch_via_api(query, max_results=100)

    results = []
    for p in raw:
        try:
            pub_date = datetime.fromisoformat(p["published_date"]).replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if pub_date < cutoff:
            continue
        hit = match_keywords(p["title"], p["abstract"], core_keywords)
        if hit:
            p["source_type"] = "自研方向"
            p["keywords_hit"] = ", ".join(hit)
            results.append(p)

    logger.info(f"自研方向：找到 {len(results)} 篇")
    return results


def fetch_trending(config: dict) -> list:
    """拉取过去30天热门方向论文"""
    logger.info("拉取热门方向（过去30天）...")
    all_keywords = config["keywords"]["core"] + config["keywords"]["related"]
    kw_part = " OR ".join(f'"{kw}"' for kw in all_keywords)
    cat_part = " OR ".join(f"cat:{c}" for c in config["arxiv_categories"])
    query = f"({kw_part}) AND ({cat_part})"

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    raw = fetch_via_api(query, max_results=50, sort_by="relevance")

    results = []
    for p in raw:
        try:
            pub_date = datetime.fromisoformat(p["published_date"]).replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if pub_date < cutoff:
            continue
        hit = match_keywords(p["title"], p["abstract"], all_keywords)
        p["source_type"] = "热门方向"
        p["keywords_hit"] = ", ".join(hit)
        results.append(p)

    logger.info(f"热门方向：找到 {len(results)} 篇")
    return results