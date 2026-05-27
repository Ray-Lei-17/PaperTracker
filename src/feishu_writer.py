"""
feishu_writer.py
将论文数据写入飞书多维表格，自动去重（按 arXiv ID）
"""

import os
import logging
import requests
import yaml
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"
FEISHU_BASE = "https://open.feishu.cn/open-apis"


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


class FeishuClient:
    def __init__(self):
        self.app_id = os.environ["FEISHU_APP_ID"]
        self.app_secret = os.environ["FEISHU_APP_SECRET"]
        self._token = None

    def _get_token(self) -> str:
        if self._token:
            return self._token
        resp = requests.post(
            f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
        )
        resp.raise_for_status()
        self._token = resp.json()["tenant_access_token"]
        return self._token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
        }

    def get_existing_ids(self, app_token: str, table_id: str) -> set[str]:
        """获取表格中已有的 arXiv ID，用于去重"""
        existing = set()
        page_token = None

        while True:
            params = {"page_size": 500}
            if page_token:
                params["page_token"] = page_token

            resp = requests.get(
                f"{FEISHU_BASE}/bitable/v1/apps/{app_token}/tables/{table_id}/records",
                headers=self._headers(),
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

            for record in data.get("data", {}).get("items", []):
                fields = record.get("fields", {})
                url = fields.get("arXiv链接", "")
                if url:
                    arxiv_id = url.split("/")[-1]
                    existing.add(arxiv_id)

            if not data.get("data", {}).get("has_more"):
                break
            page_token = data["data"]["page_token"]

        logger.info(f"表格中已有 {len(existing)} 条记录")
        return existing

    def batch_write(self, app_token: str, table_id: str, papers: list[dict]) -> int:
        """批量写入论文，每次最多写500条"""
        if not papers:
            return 0

        records = []
        for p in papers:
            records.append({
                "fields": {
                    "标题": p["title"],
                    "作者": p["authors"],
                    "摘要": p["abstract"],
                    "AI总结": p.get("ai_summary", ""),
                    "来源类型": p["source_type"],
                    "关键词命中": p["keywords_hit"],
                    "发布日期": p["published_date"],
                    "arXiv链接": p["arxiv_url"],
                    "是否已读": False,
                }
            })

        # 飞书单次最多写500条
        written = 0
        for i in range(0, len(records), 500):
            chunk = records[i:i+500]
            resp = requests.post(
                f"{FEISHU_BASE}/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
                headers=self._headers(),
                json={"records": chunk},
            )
            resp.raise_for_status()
            written += len(chunk)
            logger.info(f"  写入 {written}/{len(records)} 条")

        return written


def write_papers(papers: list[dict]):
    """去重后写入飞书，返回实际写入数量"""
    config = load_config()
    app_token = config["feishu"]["app_token"]
    table_id = config["feishu"]["table_id"]

    client = FeishuClient()
    existing_ids = client.get_existing_ids(app_token, table_id)

    # 过滤已存在的
    new_papers = [p for p in papers if p["arxiv_id"] not in existing_ids]
    logger.info(f"去重后新增 {len(new_papers)}/{len(papers)} 篇")

    if not new_papers:
        return 0

    return client.batch_write(app_token, table_id, new_papers)


if __name__ == "__main__":
    # 简单测试
    test_papers = [{
        "title": "Test Paper",
        "authors": "Author A, Author B",
        "abstract": "This is a test abstract.",
        "ai_summary": "测试论文总结。",
        "source_type": "今日新文",
        "keywords_hit": "multimodal RAG",
        "published_date": "2026-05-27",
        "arxiv_url": "https://arxiv.org/abs/2026.00001",
        "arxiv_id": "2026.00001",
    }]
    n = write_papers(test_papers)
    print(f"写入 {n} 条")
