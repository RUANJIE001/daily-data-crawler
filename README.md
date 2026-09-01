# Daily Commodity Price Crawler & Email Notifier

基于 **GitHub Actions + Python** 的全自动每日大宗商品与生产资料价格变动数据抓取与邮件推送系统。

## 功能特性
1. **定时抓取**：北京时间每天早上 07:00 (UTC 23:00) 自动运行。
2. **多数据源**：
   - 目标站点 A：生意社大宗商品监测 (`https://www.100ppi.com/monitor2/`)
   - 目标站点 B：国家统计局数据发布 - 流通领域重要生产资料市场价格变动情况 (`https://www.stats.gov.cn/sj/`)
3. **Excel 双 Sheet 美化报表**：
   - 自动生成 `Daily_Report_YYYYMMDD.xlsx`。
   - Sheet 1：生意社大宗商品监测。
   - Sheet 2：统计局重要生产资料价格。
   - 包含商务蓝表头、数据自适应列宽、斑马纹隔行变色及来源元数据。
4. **SMTP 邮件推送**：
   - 支持 HTML 摘要表格与 Excel 附件推送至指定邮箱。
5. **GitHub Actions 零成本托管**：
   - 免服务器运行，敏感配置（邮箱密钥等）全量使用 GitHub Secrets 加密。
   - 产物自动在 GitHub Artifacts 归档保留 14 天。

## 环境变量配置 (GitHub Secrets)
在 GitHub 仓库 `Settings -> Secrets and variables -> Actions` 中配置：
- `EMAIL_HOST`: SMTP 服务器地址 (如 `smtp.qq.com` 或 `smtp.163.com`)
- `EMAIL_PORT`: SMTP 端口 (如 `465`)
- `EMAIL_USER`: 发件人邮箱 (如 `your_email@qq.com`)
- `EMAIL_AUTH_TOKEN`: 邮箱专用 SMTP 授权码 / 密码
- `EMAIL_RECEIVER`: 收件人邮箱 (如 `181505217@qq.com`)
- `EMAIL_SSL`: 是否启用 SSL (如 `true`)
