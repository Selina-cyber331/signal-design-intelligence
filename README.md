# SIGNAL — 自动设计情报系统

每天日本时间约 09:00 由 GitHub Actions 自动抓取 Google News RSS（定向 Figma 官方、AI 公司、UX 研究与发布会等）以及 TechCrunch、Smashing Magazine 的 RSS，写入 `data/news.json`，静态网站自动读取。无需付费 API，也无需人工填写新闻。

## 快速部署（约需一次性设置）

1. 在 GitHub 创建新仓库，例如 `signal-design-intelligence`，将这个文件夹里的**全部内容**（包括隐藏的 `.github/`）上传到仓库根目录，默认分支为 `main`。
2. 在仓库 **Settings → Actions → General → Workflow permissions** 设置 **Read and write permissions**。如组织策略不允许则联系管理员。
3. 在 **Settings → Pages → Build and deployment → Source** 选择 **GitHub Actions**。
4. 进入 **Actions → Fetch design intelligence → Run workflow** 立即执行一次。
5. 完成后在 **Settings → Pages** 查看网址；以后由 `cron: 0 0 * * *` 每天触发，时间为日本时间 09:00 左右（GitHub 有时延迟，不保证整点）。打开网页即展示自动更新的新闻。旧内容可归档，收藏与任务保存在本浏览器 localStorage。

## Lark 可选推送

在 Lark 群创建自定义机器人，获得 webhook 地址；在 GitHub 仓库 **Settings → Secrets and variables → Actions → New repository secret** 添加 `LARK_WEBHOOK_URL`。下次定时执行时如有新资讯，将推送至群聊。需遵守所在组织对 webhook 和数据访问的安全要求，不要把 webhook 直接放进网页或仓库。

## 局部运行

```bash
python3 fetch_news.py
python3 -m http.server 8000
```

浏览器打开 http://localhost:8000 即可预览。纯双击 HTML 文件不会发起云端抓取。

## 重要限制

- 读取公开 RSS，无需账号。Google News 可能只给聚合页面链接；对外站内容的访问取决于地域、源站和网络政策。
- 摘要优先采用 RSS 来源提供的文字，不是 AI 中文重写。需要中文 AI 摘要、个性化推荐、跨设备同步时，可后续加入 API 与数据库。
- 如果来源故障或网络失败，脚本不会伪造新闻；有旧数据时保留历史，首次完全失败时为 0 条。
- 定时任务必须部署在 GitHub 才会运行，不等同于现有 ChatGPT 09:00 早报。
