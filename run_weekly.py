"""
run_weekly.py
每周任务入口：拉取自研方向过去7天论文，生成摘要，写入飞书，发送周报
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from fetch_arxiv import load_config, fetch_weekly
from summarize import summarize_papers
from feishu_writer import write_papers
from feishu_notify import send_weekly_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    logger.info("=== 每周自研方向追踪任务开始 ===")
    config = load_config()

    # 1. 拉取过去7天的核心方向论文
    papers = fetch_weekly(config)
    logger.info(f"共拉取 {len(papers)} 篇论文")

    if not papers:
        logger.info("本周暂无相关论文，任务结束")
        return

    # 2. 生成摘要
    papers = summarize_papers(papers, config)

    # 3. 写入飞书（自动去重，不会重复写已有的）
    written = write_papers(papers)
    logger.info(f"写入飞书：{written} 篇新论文")

    # 4. 发送周报
    send_weekly_report(papers)

    logger.info("=== 每周任务完成 ===")


if __name__ == "__main__":
    main()
