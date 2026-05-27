"""
summarize.py
调用小米 MiMo API，为每篇论文生成一句话中文总结
"""

import os
import time
import logging
import requests
import yaml
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"
MIMO_BASE_URL = "https://api.xiaomimimo.com/v1/chat/completions"

PROMPT_TEMPLATE = """你是一个AI论文助手。请用1-2句中文概括以下论文的核心贡献，要求：
- 说清楚做了什么、解决了什么问题
- 如果有具体数字或对比结果请包含
- 不超过80字

论文标题：{title}
论文摘要：{abstract}

只输出总结内容，不要任何前缀。"""


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def summarize_paper(title: str, abstract: str, config: dict) -> str:
    """调用 MiMo API 生成单篇论文总结"""
    api_key = os.environ.get("MIMO_API_KEY", "")
    if not api_key:
        logger.warning("MIMO_API_KEY 未设置，跳过摘要生成")
        return ""

    prompt = PROMPT_TEMPLATE.format(title=title, abstract=abstract[:1000])

    try:
        resp = requests.post(
            MIMO_BASE_URL,
            headers={
                "Content-Type": "application/json",
                "api-key": api_key,
            },
            json={
                "model": config["summarize"]["model"],
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": config["summarize"]["max_tokens"],
                "temperature": 0.3,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"摘要生成失败：{e}")
        return ""


def summarize_papers(papers: list[dict], config: dict) -> list[dict]:
    """批量生成摘要，每篇之间间隔0.5秒避免限速"""
    logger.info(f"开始生成摘要，共 {len(papers)} 篇...")
    for i, paper in enumerate(papers):
        summary = summarize_paper(paper["title"], paper["abstract"], config)
        paper["ai_summary"] = summary
        if (i + 1) % 10 == 0:
            logger.info(f"  已处理 {i+1}/{len(papers)} 篇")
        time.sleep(0.5)
    logger.info("摘要生成完成")
    return papers


if __name__ == "__main__":
    cfg = load_config()
    test = {
        "title": "Visual RAG with Document Grounding",
        "abstract": "We propose a novel approach for visual document retrieval augmented generation with fine-grained grounding.",
    }
    result = summarize_paper(test["title"], test["abstract"], cfg)
    print(result)
