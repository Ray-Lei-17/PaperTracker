"""
fetch_arxiv.py
从 arXiv 拉取论文，支持三种模式：
- daily: 今天新出的论文（按关键词过滤）
- weekly: 过去7天的论文（核心关键词，用于自研方向追踪）
- trending: 过去30天高引用/热门论文
"""

import arxiv
import yaml
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def build_query(keywords: list[str], categories: list[str]) -> str:
    """拼接 arXiv 搜索 query"""
    kw_part = " OR ".join(f'"{kw}"' for kw in keywords)
    cat_part = " OR ".join(f"cat:{c}" for c in categories)
    return f"({kw_part}) AND ({cat_part})"


def match_keywords(paper, all_keywords: list[str]) -> list[str]:
    """返回论文命中的关键词列表"""
    text = (paper.title + " " + paper.summary).lower()
    return [kw for kw in all_keywords if kw.lower() in text]


def fetch_daily(config: dict) -> list[dict]:
    """拉取今天新出的论文（所有关键词）"""
    logger.info("拉取今日新文...")
    all_keywords = (
        config["keywords"]["core"]
        + config["keywords"]["related"]
        + config["keywords"]["trending"]
    )
    query = build_query(all_keywords, config["arxiv_categories"])

    cutoff = datetime.now(timezone.utc) - timedelta(days=1)
    results = []

    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=100,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    for paper in client.results(search):
        if paper.published < cutoff:
            break
        hit_keywords = match_keywords(paper, all_keywords)
        if not hit_keywords:
            continue
        results.append(_to_dict(paper, "今日新文", hit_keywords))

    logger.info(f"今日新文：找到 {len(results)} 篇")
    return results


def fetch_weekly(config: dict) -> list[dict]:
    """拉取过去7天的核心方向论文（只用 core 关键词）"""
    logger.info("拉取自研方向（过去7天）...")
    core_keywords = config["keywords"]["core"]
    query = build_query(core_keywords, config["arxiv_categories"])

    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    results = []

    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=200,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    for paper in client.results(search):
        if paper.published < cutoff:
            break
        hit_keywords = match_keywords(paper, core_keywords)
        if not hit_keywords:
            continue
        results.append(_to_dict(paper, "自研方向", hit_keywords))

    logger.info(f"自研方向：找到 {len(results)} 篇")
    return results


def fetch_trending(config: dict) -> list[dict]:
    """拉取过去30天的热门方向论文（按相关性排序，取前50篇）"""
    logger.info("拉取热门方向（过去30天）...")
    all_keywords = config["keywords"]["core"] + config["keywords"]["related"]
    query = build_query(all_keywords, config["arxiv_categories"])

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    results = []

    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=50,
        sort_by=arxiv.SortCriterion.Relevance,
    )

    for paper in client.results(search):
        if paper.published < cutoff:
            continue
        hit_keywords = match_keywords(paper, all_keywords)
        results.append(_to_dict(paper, "热门方向", hit_keywords))

    logger.info(f"热门方向：找到 {len(results)} 篇")
    return results


def _to_dict(paper, source_type: str, hit_keywords: list[str]) -> dict:
    return {
        "title": paper.title,
        "authors": ", ".join(a.name for a in paper.authors[:5]),
        "abstract": paper.summary.replace("\n", " "),
        "source_type": source_type,
        "keywords_hit": ", ".join(hit_keywords),
        "published_date": paper.published.strftime("%Y-%m-%d"),
        "arxiv_url": paper.entry_id,
        "arxiv_id": paper.entry_id.split("/")[-1],
    }


if __name__ == "__main__":
    cfg = load_config()
    papers = fetch_daily(cfg)
    for p in papers[:3]:
        print(p["title"], "|", p["keywords_hit"])
