"""
fetch_arxiv.py
从 arXiv 拉取论文，支持三种模式：
- daily: 今天新出的论文（按关键词过滤）
- weekly: 过去7天的论文（核心关键词，用于自研方向追踪）
- trending: 过去30天热门论文
"""

import arxiv
import yaml
import time
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def build_query(keywords: list, categories: list) -> str:
    kw_part = " OR ".join(f'"{kw}"' for kw in keywords)
    cat_part = " OR ".join(f"cat:{c}" for c in categories)
    return f"({kw_part}) AND ({cat_part})"


def match_keywords(paper, all_keywords: list) -> list:
    text = (paper.title + " " + paper.summary).lower()
    return [kw for kw in all_keywords if kw.lower() in text]


def fetch_with_retry(client, search, max_retries=3) -> list:
    """带重试的拉取，遇到限流等待后重试"""
    for attempt in range(max_retries):
        try:
            results = list(client.results(search))
            return results
        except Exception as e:
            wait = 10 * (attempt + 1)
            logger.warning(f"请求失败（{e}），{wait}秒后重试（{attempt+1}/{max_retries}）...")
            time.sleep(wait)
    logger.error("多次重试后仍失败，返回空结果")
    return []


def fetch_daily(config: dict) -> list:
    logger.info("拉取今日新文...")
    all_keywords = (
        config["keywords"]["core"]
        + config["keywords"]["related"]
        + config["keywords"]["trending"]
    )
    query = build_query(all_keywords, config["arxiv_categories"])
    cutoff = datetime.now(timezone.utc) - timedelta(days=1)

    # delay_seconds 控制请求间隔，避免限流
    client = arxiv.Client(delay_seconds=3, num_retries=3)
    search = arxiv.Search(
        query=query,
        max_results=100,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    papers = fetch_with_retry(client, search)
    results = []
    for paper in papers:
        if paper.published < cutoff:
            continue
        hit = match_keywords(paper, all_keywords)
        if hit:
            results.append(_to_dict(paper, "今日新文", hit))

    logger.info(f"今日新文：找到 {len(results)} 篇")
    return results


def fetch_weekly(config: dict) -> list:
    logger.info("拉取自研方向（过去7天）...")
    core_keywords = config["keywords"]["core"]
    query = build_query(core_keywords, config["arxiv_categories"])
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    client = arxiv.Client(delay_seconds=3, num_retries=3)
    search = arxiv.Search(
        query=query,
        max_results=200,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    papers = fetch_with_retry(client, search)
    results = []
    for paper in papers:
        if paper.published < cutoff:
            continue
        hit = match_keywords(paper, core_keywords)
        if hit:
            results.append(_to_dict(paper, "自研方向", hit))

    logger.info(f"自研方向：找到 {len(results)} 篇")
    return results


def fetch_trending(config: dict) -> list:
    logger.info("拉取热门方向（过去30天）...")
    all_keywords = config["keywords"]["core"] + config["keywords"]["related"]
    query = build_query(all_keywords, config["arxiv_categories"])
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    client = arxiv.Client(delay_seconds=3, num_retries=3)
    search = arxiv.Search(
        query=query,
        max_results=50,
        sort_by=arxiv.SortCriterion.Relevance,
    )

    papers = fetch_with_retry(client, search)
    results = []
    for paper in papers:
        if paper.published < cutoff:
            continue
        hit = match_keywords(paper, all_keywords)
        results.append(_to_dict(paper, "热门方向", hit))

    logger.info(f"热门方向：找到 {len(results)} 篇")
    return results


def _to_dict(paper, source_type: str, hit_keywords: list) -> dict:
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
