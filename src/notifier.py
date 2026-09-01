"""
src/notifier.py - SMTP 邮件发送（带 HTML 摘要与 Excel 附件）
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.header import Header
from typing import Dict
from src.utils import setup_logger, get_beijing_now

logger = setup_logger("Notifier")

class EmailNotifier:
    def __init__(self):
        self.smtp_host = os.getenv("EMAIL_HOST", "smtp.qq.com")
        self.smtp_port = int(os.getenv("EMAIL_PORT", "465"))
        self.smtp_user = os.getenv("EMAIL_USER", "")
        self.auth_token = os.getenv("EMAIL_AUTH_TOKEN", "")
        self.receiver = os.getenv("EMAIL_RECEIVER", "181505217@qq.com")
        self.use_ssl = os.getenv("EMAIL_SSL", "true").lower() in ("true", "1", "yes")

    def send_report(self, excel_path: str, meta_a: Dict, meta_b: Dict) -> bool:
        """
        发送每日数据监测报表邮件
        """
        if not self.smtp_user or not self.auth_token:
            logger.error("未配置 EMAIL_USER 或 EMAIL_AUTH_TOKEN 环境变量，无法发送邮件！")
            return False

        now_str = get_beijing_now().strftime("%Y-%m-%d %H:%M:%S")
        date_str = get_beijing_now().strftime("%Y%m%d")
        subject = f"【每日数据监测】大宗商品与流通生产资料市场变动日报 ({date_str})"

        # 创建复合邮件对象
        msg = MIMEMultipart("mixed")
        msg["From"] = Header(f"自动化数据机器人 <{self.smtp_user}>", "utf-8")
        msg["To"] = Header(self.receiver, "utf-8")
        msg["Subject"] = Header(subject, "utf-8")

        # 1. 构建 HTML 摘要正文
        html_content = self._render_html_body(now_str, meta_a, meta_b)
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        # 2. 挂载 Excel 附件
        if os.path.exists(excel_path):
            file_name = os.path.basename(excel_path)
            with open(excel_path, "rb") as f:
                part = MIMEApplication(f.read(), Name=file_name)
            # 处理跨平台邮件客户端的中文附件名编码
            part.add_header("Content-Disposition", "attachment", filename=("utf-8", "", file_name))
            msg.attach(part)
        else:
            logger.warning(f"附件文件不存在: {excel_path}，将只发送正文")

        # 3. 发送邮件
        receivers = [r.strip() for r in self.receiver.split(",") if r.strip()]
        try:
            logger.info(f"正在连接 SMTP 服务器 {self.smtp_host}:{self.smtp_port} (SSL: {self.use_ssl})...")
            if self.use_ssl:
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=30) as server:
                    server.login(self.smtp_user, self.auth_token)
                    server.sendmail(self.smtp_user, receivers, msg.as_string())
            else:
                with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
                    server.starttls()
                    server.login(self.smtp_user, self.auth_token)
                    server.sendmail(self.smtp_user, receivers, msg.as_string())
            
            logger.info(f"邮件成功发送至: {receivers}")
            return True

        except Exception as e:
            logger.error(f"邮件发送失败: {e}", exc_info=True)
            return False

    def _render_html_body(self, run_time: str, meta_a: Dict, meta_b: Dict) -> str:
        """生成美观的响应式 HTML 摘要模版"""
        total_rows = meta_a.get("row_count", 0) + meta_b.get("row_count", 0)
        
        status_badge_a = '<span style="color:#0f766e; background:#ccfbf1; padding:2px 8px; border-radius:4px; font-weight:bold;">成功</span>' if meta_a.get("status") == "成功" else '<span style="color:#b91c1c; background:#fee2e2; padding:2px 8px; border-radius:4px; font-weight:bold;">异常</span>'
        status_badge_b = '<span style="color:#0f766e; background:#ccfbf1; padding:2px 8px; border-radius:4px; font-weight:bold;">成功</span>' if meta_b.get("status") == "成功" else '<span style="color:#d97706; background:#fef3c7; padding:2px 8px; border-radius:4px; font-weight:bold;">无新发布</span>'

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f3f4f6; margin: 0; padding: 20px; color: #1f2937; }}
                .container {{ max-width: 680px; margin: 0 auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #1e3a8a, #3b82f6); color: #ffffff; padding: 24px; text-align: left; }}
                .header h2 {{ margin: 0 0 8px 0; font-size: 20px; }}
                .header p {{ margin: 0; opacity: 0.9; font-size: 13px; }}
                .content {{ padding: 24px; }}
                .summary-card {{ display: flex; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 16px; margin-bottom: 20px; justify-content: space-around; }}
                .metric {{ text-align: center; }}
                .metric-label {{ font-size: 12px; color: #64748b; margin-bottom: 4px; }}
                .metric-val {{ font-size: 18px; font-weight: bold; color: #0f172a; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }}
                th {{ background: #f1f5f9; color: #475569; text-align: left; padding: 10px 12px; border-bottom: 2px solid #e2e8f0; }}
                td {{ padding: 10px 12px; border-bottom: 1px solid #f1f5f9; }}
                .footer {{ background: #f8fafc; padding: 16px 24px; text-align: center; font-size: 12px; color: #94a3b8; border-top: 1px solid #e2e8f0; }}
                a {{ color: #2563eb; text-decoration: none; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>每日大宗商品与生产资料价格变动</h2>
                    <p>自动抓取执行时间 (北京时间): {run_time}</p>
                </div>
                <div class="content">
                    <div class="summary-card">
                        <div class="metric">
                            <div class="metric-label">监控数据源</div>
                            <div class="metric-val">2 个站点</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">今日提取总数</div>
                            <div class="metric-val" style="color:#2563eb;">{total_rows} 条</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">附件状态</div>
                            <div class="metric-val" style="color:#059669;">Excel 已就绪</div>
                        </div>
                    </div>
                    
                    <h3 style="font-size: 15px; margin: 16px 0 8px 0; color: #334155;">抓取摘要明细</h3>
                    <table>
                        <thead>
                            <tr>
                                <th>数据源</th>
                                <th>抓取状态</th>
                                <th>提取条数</th>
                                <th>最新期数 / 详情</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td><a href="{meta_a.get('url')}" target="_blank">生意社大宗商品</a></td>
                                <td>{status_badge_a}</td>
                                <td><b>{meta_a.get('row_count', 0)}</b> 条</td>
                                <td>{meta_a.get('detail')}</td>
                            </tr>
                            <tr>
                                <td><a href="{meta_b.get('url')}" target="_blank">国家统计局</a></td>
                                <td>{status_badge_b}</td>
                                <td><b>{meta_b.get('row_count', 0)}</b> 条</td>
                                <td>{meta_b.get('title', meta_b.get('detail'))}</td>
                            </tr>
                        </tbody>
                    </table>
                    <p style="font-size: 13px; color: #64748b; margin-top: 16px; line-height: 1.5;">
                        📎 <b>详细数据已生成 Excel 报表并附于邮件附件中</b>，包含两个独立 Sheet 并已完成自适应列宽排版，请查收附件。
                    </p>
                </div>
                <div class="footer">
                    本邮件由 GitHub Actions 自动化服务每日定时发送，无需回复。
                </div>
            </div>
        </body>
        </html>
        """
