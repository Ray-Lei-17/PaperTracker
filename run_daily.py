"""
run_daily.py
每日任务入口：拉取今日新文 + 热门方向，生成摘要，写入飞书，发送通知
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from fetch_arxiv import load_config, fetch_daily, fetch_trending
from summarize import summarize_papers
from feishu_writer import write_papers
from feishu_notify import send_daily_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    logger.info("=== 每日论文追踪任务开始 ===")
    config = load_config()

    # 1. 拉取论文
    daily_papers = fetch_daily(config)
    trending_papers = fetch_trending(config)
    all_papers = daily_papers + trending_papers
    logger.info(f"共拉取 {len(all_papers)} 篇论文")

    if not all_papers:
        logger.info("没有新论文，任务结束")
        return

    # 2. 生成摘要
    all_papers = summarize_papers(all_papers, config)

    # 3. 写入飞书
    written = write_papers(all_papers)
    logger.info(f"写入飞书：{written} 篇")

    # 4. 发送通知
    send_daily_report(all_papers)

    logger.info("=== 每日任务完成 ===")


if __name__ == "__main__":
    main()
