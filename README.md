# 📚 Paper Tracker

基于 arXiv + 小米 MiMo + 飞书多维表格的科研论文自动追踪系统。

## 功能

- **每日**：抓取今日新文 + 热门方向论文，推送早报到飞书
- **每周**：抓取自研方向（核心关键词）过去7天论文，推送周报

## 配置

修改 `config.yaml` 调整关键词和追踪方向，无需改代码。

## GitHub Secrets 配置

在仓库 Settings → Secrets and variables → Actions 中添加：

| Secret 名称 | 说明 |
|-------------|------|
| `MIMO_API_KEY` | 小米 MiMo API Key |
| `FEISHU_APP_ID` | 飞书应用 App ID |
| `FEISHU_APP_SECRET` | 飞书应用 App Secret |
| `FEISHU_USER_ID` | 飞书用户ID |

## 本地测试

```bash
pip install -r requirements.txt

export MIMO_API_KEY=your_key
export FEISHU_APP_ID=your_id
export FEISHU_APP_SECRET=your_secret
export FEISHU_USER_ID=your_userid

python run_daily.py   # 测试每日任务
python run_weekly.py  # 测试每周任务
```
