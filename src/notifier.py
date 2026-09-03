"""
src/notifier.py - SMTP 邮件发送模块（支持 3-Sheet 结构与过去 10 期走势摘要）
"""
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.header import Header
from typing import Dict, List
from src.utils import setup_logger, get_beijing_now

logger = setup_logger("Notifier")

def clean_value(val: str) -> str:
    if not val:
        return ""
    return val.strip().strip("'").strip('"')

def clean_host(host_str: str) -> str:
    h = clean_value(host_str).replace("http://", "").replace("https://", "")
    if ":" in h:
        h = h.split(":")[0]
    return h.strip()

class EmailNotifier:
    def __init__(self):
        raw_host = os.getenv("EMAIL_HOST", "smtp.gmail.com")
        self.smtp_host = clean_host(raw_host) or "smtp.gmail.com"
        
        raw_port = clean_value(os.getenv("EMAIL_PORT", "587"))
        try:
            self.smtp_port = int(raw_port)
        except Exception:
            self.smtp_port = 587

        self.smtp_user = clean_value(os.getenv("EMAIL_USER", ""))
        self.auth_token = clean_value(os.getenv("EMAIL_AUTH_TOKEN", "")).replace(" ", "").replace("\n", "").replace("\r", "")
        self.receiver = clean_value(os.getenv("EMAIL_RECEIVER", "181505217@qq.com"))

    def send_report(
        self,
        excel_path: str,
        meta_a: Dict,
        meta_b: Optional[Dict] = None,
        period_headers: Optional[List[str]] = None,
        is_weekly_report: bool = False
    ) -> bool:
        if not self.smtp_user:
            logger.error("❌ 未检测到 EMAIL_USER 环境变量，请在 GitHub Secrets 中配置！")
            return False
        if not self.auth_token:
            logger.error("❌ 未检测到 EMAIL_AUTH_TOKEN 环境变量，请在 GitHub Secrets 中配置！")
            return False

        masked_user = self.smtp_user[:3] + "***" + self.smtp_user[self.smtp_user.find("@"):] if "@" in self.smtp_user else "***"
        logger.info(f"📧 发件人: {masked_user}")
        logger.info(f"📧 目标 Host: '{self.smtp_host}'")

        now_str = get_beijing_now().strftime("%Y-%m-%d %H:%M:%S")
        date_str = get_beijing_now().strftime("%Y%m%d")
        
        if is_weekly_report:
            subject = f"📈 【周报特别版】大宗商品每日监测 + 统计局生产资料10期走势 ({date_str})"
        else:
            subject = f"📊 【大宗商品每日监测】生意社价格变动监测日报 ({date_str})"

        msg = MIMEMultipart("mixed")
        msg["From"] = Header(f"自动化数据机器人 <{self.smtp_user}>", "utf-8")
        msg["To"] = Header(self.receiver, "utf-8")
        msg["Subject"] = Header(subject, "utf-8")

        # 1. HTML 正文
        html_content = self._render_html_body(
            now_str=now_str,
            meta_a=meta_a,
            meta_b=meta_b or {},
            period_headers=period_headers or [],
            is_weekly_report=is_weekly_report
        )
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        # 2. 附件
        if os.path.exists(excel_path):
            file_name = os.path.basename(excel_path)
            with open(excel_path, "rb") as f:
                part = MIMEApplication(f.read(), Name=file_name)
            part.add_header("Content-Disposition", "attachment", filename=("utf-8", "", file_name))
            msg.attach(part)
        else:
            logger.warning(f"⚠️ 附件不存在: {excel_path}")

        receivers = [r.strip() for r in self.receiver.split(",") if r.strip()]
        context = ssl.create_default_context()

        # 通道列表：优先 587 STARTTLS，后备 465 SSL
        channels = [
            ("STARTTLS", self.smtp_host, 587),
            ("SSL", self.smtp_host, 465)
        ]

        for mode_type, host, port in channels:
            server = None
            try:
                logger.info(f"🚀 发起连接 -> Host: {host}, Port: {port}, Mode: {mode_type}")
                if mode_type == "SSL":
                    server = smtplib.SMTP_SSL(host, port, context=context, timeout=30)
                    server.set_debuglevel(1)
                    server.ehlo()
                    server.login(self.smtp_user, self.auth_token)
                    server.sendmail(self.smtp_user, receivers, msg.as_string())
                else:
                    server = smtplib.SMTP(host, port, timeout=30)
                    server.set_debuglevel(1)
                    server.ehlo()
                    server.starttls(context=context)
                    server.ehlo()
                    server.login(self.smtp_user, self.auth_token)
                    server.sendmail(self.smtp_user, receivers, msg.as_string())

                logger.info(f"🎉 邮件发送成功！已投递至: {receivers}")
                return True

            except smtplib.SMTPAuthenticationError as auth_err:
                logger.error(f"❌ SMTP 认证失败 (密码错误): {auth_err}")
                return False
            except Exception as e:
                logger.warning(f"⚠️ 模式 {mode_type} (端口 {port}) 异常: {e}")
            finally:
                if server:
                    try:
                        server.quit()
                    except Exception:
                        pass

        logger.error("❌ 所有 SMTP 连接方式均尝试失败！")
        return False

    def _render_html_body(
        self,
        now_str: str,
        meta_a: Dict,
        meta_b: Dict,
        period_headers: List[str],
        is_weekly_report: bool = False
    ) -> str:
        status_badge_a = '<span style="color:#0f766e; background:#ccfbf1; padding:2px 8px; border-radius:4px; font-weight:bold;">成功</span>' if meta_a.get("status") == "成功" else '<span style="color:#b91c1c; background:#fee2e2; padding:2px 8px; border-radius:4px; font-weight:bold;">异常</span>'
        
        if is_weekly_report:
            status_badge_b = '<span style="color:#0f766e; background:#ccfbf1; padding:2px 8px; border-radius:4px; font-weight:bold;">成功 (10期)</span>' if meta_b.get("status") == "成功" else '<span style="color:#d97706; background:#fef3c7; padding:2px 8px; border-radius:4px; font-weight:bold;">无新发布</span>'
            period_span_str = f"{period_headers[0]} ~ {period_headers[-1]}" if len(period_headers) >= 2 else "10 期"

            header_title = "📈 周一深度版：大宗商品与生产资料价格变动 (含10期走势)"
            metric_cards = f"""
                <div class="metric">
                    <div class="metric-label">站点A监测</div>
                    <div class="metric-val" style="color:#2563eb;">{meta_a.get('row_count', 0)} 条</div>
                </div>
                <div class="metric">
                    <div class="metric-label">统计局覆盖期数</div>
                    <div class="metric-val" style="color:#059669;">{len(period_headers)} 期</div>
                </div>
                <div class="metric">
                    <div class="metric-label">报表工作表</div>
                    <div class="metric-val" style="color:#7c3aed;">3 个 Sheet</div>
                </div>
            """
            table_rows = f"""
                <tr>
                    <td><span class="sheet-badge">Sheet 1</span>生意社大宗商品</td>
                    <td><a href="{meta_a.get('url')}" target="_blank">生意社 Monitor2</a></td>
                    <td>{status_badge_a}</td>
                    <td><b>{meta_a.get('row_count', 0)}</b> 行大宗商品每日监测数据</td>
                </tr>
                <tr>
                    <td><span class="sheet-badge">Sheet 2</span>统计局生产资料(最新)</td>
                    <td><a href="{meta_b.get('url')}" target="_blank">统计局最新发布</a></td>
                    <td>{status_badge_b}</td>
                    <td>{meta_b.get('latest_title', '最新一期价格')} (50 种生产资料)</td>
                </tr>
                <tr>
                    <td><span class="sheet-badge">Sheet 3</span>生产资料走势(近10次)</td>
                    <td><a href="{meta_b.get('url')}" target="_blank">统计局历史数据</a></td>
                    <td>{status_badge_b}</td>
                    <td>覆盖 <b>{period_span_str}</b>，包含各细项原生趋势折线图</td>
                </tr>
            """
            attachment_tip = "📈 <b>Excel 附件包含 3 个 Sheet</b>：已在 Sheet 3 绘制各商品细项及分类原生走势折线图，请查收附件。"
        else:
            header_title = "📊 大宗商品价格每日监测日报"
            metric_cards = f"""
                <div class="metric">
                    <div class="metric-label">站点A大宗商品监测</div>
                    <div class="metric-val" style="color:#2563eb;">{meta_a.get('row_count', 0)} 条</div>
                </div>
                <div class="metric">
                    <div class="metric-label">报表工作表</div>
                    <div class="metric-val" style="color:#7c3aed;">1 个 Sheet</div>
                </div>
                <div class="metric">
                    <div class="metric-label">统计局生产资料走势</div>
                    <div class="metric-val" style="color:#059669; font-size: 14px;">每周一深度推送</div>
                </div>
            """
            table_rows = f"""
                <tr>
                    <td><span class="sheet-badge">Sheet 1</span>生意社大宗商品</td>
                    <td><a href="{meta_a.get('url')}" target="_blank">生意社 Monitor2</a></td>
                    <td>{status_badge_a}</td>
                    <td><b>{meta_a.get('row_count', 0)}</b> 行大宗商品每日监测数据</td>
                </tr>
            """
            attachment_tip = "📊 <b>Excel 附件已生成完毕</b>：包含今日生意社大宗商品全量监测数据（Sheet 1）。国家统计局生产资料与10期走势图将在每周一随周报推送。"

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
                .metric-val {{ font-size: 17px; font-weight: bold; color: #0f172a; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }}
                th {{ background: #f1f5f9; color: #475569; text-align: left; padding: 10px 12px; border-bottom: 2px solid #e2e8f0; }}
                td {{ padding: 10px 12px; border-bottom: 1px solid #f1f5f9; }}
                .sheet-badge {{ display: inline-block; background: #e0e7ff; color: #3730a3; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; margin-right: 4px; }}
                .footer {{ background: #f8fafc; padding: 16px 24px; text-align: center; font-size: 12px; color: #94a3b8; border-top: 1px solid #e2e8f0; }}
                a {{ color: #2563eb; text-decoration: none; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>{header_title}</h2>
                    <p>自动抓取执行时间 (北京时间): {now_str}</p>
                </div>
                <div class="content">
                    <div class="summary-card">
                        {metric_cards}
                    </div>
                    
                    <h3 style="font-size: 15px; margin: 16px 0 8px 0; color: #334155;">数据采集与报表结构摘要</h3>
                    <table>
                        <thead>
                            <tr>
                                <th>Sheet 工作表</th>
                                <th>数据源</th>
                                <th>状态</th>
                                <th>内容摘要</th>
                            </tr>
                        </thead>
                        <tbody>
                            {table_rows}
                        </tbody>
                    </table>
                    <p style="font-size: 13px; color: #64748b; margin-top: 16px; line-height: 1.5;">
                        {attachment_tip}
                    </p>
                </div>
                <div class="footer">
                    本邮件由 GitHub Actions 自动化服务每日定时发送，无需回复。
                </div>
            </div>
        </body>
        </html>
        """
