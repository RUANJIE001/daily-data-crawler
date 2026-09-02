---
name: smtp-email-automation-ci
description: >-
  生产级 Python smtplib 与 GitHub Actions / 云端环境邮件推送与 Excel 图表自动化方案。
  包含主流邮箱配置（Gmail/QQ/163）、多通道故障倒换、字符清洗、RFC 2231 中文附件、openpyxl 股票涨跌高亮与原生图表排版避坑规则。
---

# Python CI/CD 自动化邮件推送与报表生成最佳实践指南 (含踩坑全录)

本指南总结了在 Python 脚本、云服务器及 GitHub Actions 环境下实现自动化邮件推送、Excel 多 Sheet 报表排版与图表绘制的完整规范及全部实战避坑经验。

---

## 1. 主流邮箱服务商配置矩阵

| 邮箱服务商 | SMTP 服务器 Host | 推荐端口 / 协议 | 密码类型 | 核心注意事项 |
| :--- | :--- | :--- | :--- | :--- |
| **Gmail** | `smtp.gmail.com` | **`587` (STARTTLS)**<br>备用 `465` (SSL) | 16 位**应用专用密码** | ① 必须开启两步验证并在 [Google App Passwords](https://myaccount.google.com/apppasswords) 生成<br>② 生成的 16 位密码自带空格，代码中必须自动剔除空格<br>③ 云执行机连接 587 端口最稳定 |
| **QQ 邮箱** | `smtp.qq.com` | **`465` (SSL)**<br>备用 `587` (STARTTLS) | 16 位**SMTP 授权码** | ① 在“设置 -> 账户 -> POP3/SMTP服务”开启并生成<br>② 发件人账号与发件服务器必须同属 QQ，不可混用 |
| **163 邮箱** | `smtp.163.com` | **`465` (SSL)**<br>备用 `587` (STARTTLS) | **客户端授权密码** | ① 在“设置 -> POP3/SMTP/IMAP”中开启<br>② 网页登录密码无法用于 SMTP 登录 |
| **Outlook** | `smtp.office365.com` | **`587` (STARTTLS)** | 账号密码 / 应用密码 | ① 需支持 STARTTLS |

---

## 2. 生产级 Python SMTP 核心代码实现

具备 **自动清洗空格、双通道自动故障倒换、RFC 2231 中文附件编码、底层 Debug 诊断** 的标准实现：

```python
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.header import Header
from typing import List, Optional

def clean_val(v: Optional[str]) -> str:
    """去除首尾空白、常见外层引号、换行符"""
    if not v:
        return ""
    return str(v).strip().strip("'").strip('"').replace("\n", "").replace("\r", "")

def send_email_robust(
    subject: str,
    html_body: str,
    receiver_emails: List[str],
    attachment_path: Optional[str] = None
) -> bool:
    # 1. 读取并严格清洗环境变量
    raw_host = clean_val(os.getenv("EMAIL_HOST", "smtp.gmail.com"))
    host = raw_host.replace("http://", "").replace("https://", "").split(":")[0]
    user = clean_val(os.getenv("EMAIL_USER", ""))
    
    # ⚠️ 踩坑重点：必须完全剔除密码中的所有内部空格（针对 Google 16位密码形如 abcd efgh ijkl mnop）
    token = clean_val(os.getenv("EMAIL_AUTH_TOKEN", "")).replace(" ", "")
    
    if not user or not token:
        print("❌ 错误：EMAIL_USER 或 EMAIL_AUTH_TOKEN 缺失！")
        return False

    # 2. 构建复合邮件对象
    msg = MIMEMultipart("mixed")
    msg["From"] = Header(f"自动化服务机器人 <{user}>", "utf-8")
    msg["To"] = Header(", ".join(receiver_emails), "utf-8")
    msg["Subject"] = Header(subject, "utf-8")

    # 挂载 HTML 摘要正文
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # 挂载附件（⚠️ 踩坑重点：RFC 2231 中文文件名编码，防止附件在 Outlook/Foxmail 变成 bin/未命名）
    if attachment_path and os.path.exists(attachment_path):
        file_name = os.path.basename(attachment_path)
        with open(attachment_path, "rb") as f:
            part = MIMEApplication(f.read(), Name=file_name)
        part.add_header("Content-Disposition", "attachment", filename=("utf-8", "", file_name))
        msg.attach(part)

    # 3. SSL 上下文握手与双通道自动回退
    context = ssl.create_default_context()
    channels = [
        ("STARTTLS", 587),
        ("SSL", 465)
    ]

    for mode, port in channels:
        server = None
        try:
            print(f"🚀 尝试连接 {host}:{port} ({mode} 模式)...")
            if mode == "STARTTLS":
                server = smtplib.SMTP(host, port, timeout=30)
                server.set_debuglevel(0) # 排错时可设为 1 打印原始报文
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
            else:
                server = smtplib.SMTP_SSL(host, port, context=context, timeout=30)
                server.set_debuglevel(0)
                server.ehlo()

            server.login(user, token)
            server.sendmail(user, receiver_emails, msg.as_string())
            print(f"🎉 邮件发送成功至: {receiver_emails}")
            return True

        except smtplib.SMTPAuthenticationError as auth_err:
            print(f"❌ SMTP 认证失败 (账号/授权码不正确): {auth_err}")
            return False # 密码错误无需重试其他端口
        except Exception as e:
            print(f"⚠️ {mode} 模式连接失败 ({e})，切换备用通道...")
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass

    print("❌ 所有 SMTP 通道均连接失败！")
    return False
```

---

## 3. 踩坑与避坑血泪全录 (Top 10 Pitfalls)

### 💣 坑 1：Google 应用专用密码自带空格导致 535 Auth Error
- **现象**：从 Google 安全中心生成的 16 位密码为 `abcd efgh ijkl mnop`，直接填入 Secrets 会报 `535 5.7.8 BadCredentials`。
- **解法**：代码中对 Token 强制执行 `.replace(" ", "")`。

### 💣 坑 2：发件 Host 与发件账号域名不匹配
- **现象**：连接 `smtp.qq.com` 却使用 `xxx@gmail.com` 作为发件人，QQ 服务器返回 `535 Login fail. Account abnormal`。
- **解法**：`EMAIL_HOST` 与 `EMAIL_USER` 必须同源（Gmail 对应 `smtp.gmail.com`，QQ 对应 `smtp.qq.com`）。

### 💣 坑 3：云端 CI 环境（GitHub Actions）连接被秒挂断 (`Connection unexpectedly closed`)
- **现象**：在云端 Linux 机器上连接 Gmail `465` 端口时，由于缺少 SNI 上下文与双重 EHLO 握手，直接被 Google 防火墙掐断。
- **解法**：优先使用 **端口 587 + STARTTLS**，显式传入 `ssl.create_default_context()`，并在 `starttls()` 前后各执行一次 `ehlo()`。

### 💣 坑 4：中文附件名变乱码或变成 `attachment.bin`
- **现象**：附件名包含中文（如 `日报_20260901.xlsx`）在部分客户端中变成 `未命名.dat` 或 `bin`。
- **解法**：必须采用 RFC 2231 标准三元组格式：`part.add_header("Content-Disposition", "attachment", filename=("utf-8", "", file_name))`。

### 💣 坑 5：GitHub Actions 定时任务严重延迟（00 分整点大塞车）
- **现象**：设置北京时间 07:00（即 UTC `0 23 * * *`），常常延迟到 8 点多才收到邮件。
- **解法**：**避开 `:00` 分整点**。改为非整点（如 `06:38` 对应 UTC `38 22 * * *`），通常在 1 分钟内立即触发。

### 💣 坑 6：openpyxl 图表系列标题抛出 `TypeError`
- **现象**：给 `series.title` 赋值普通字符串 `str` 或 `Reference` 时，openpyxl 报错：`series.tx should be SeriesLabel but value is ...`。
- **解法**：必须使用 `from openpyxl.chart.series import SeriesLabel`，赋值 `series.tx = SeriesLabel(v=product_name)`。

### 💣 坑 7：openpyxl 图表 X 轴与 Y 轴刻度标签全挤在左侧纵轴
- **现象**：生成折线图后，期数（X轴）和价格（Y轴）全部竖着堆在图表左侧。
- **解法**：openpyxl 默认将两者 `axPos` 设为 `'l'`。必须显式指定：
  ```python
  chart.x_axis.axPos = "b"  # 明确置于底部横轴 (Bottom)
  chart.y_axis.axPos = "l"  # 明确置于左侧纵轴 (Left)
  chart.x_axis.tickLblPos = "low"
  chart.y_axis.tickLblPos = "low"
  chart.x_axis.crosses = "autoZero"
  chart.y_axis.crosses = "autoZero"
  ```

### 💣 坑 8：带有 `%` 规格的产品名（如“硫酸 98%”）被错误右对齐
- **现象**：产品名称列中，无 `%` 的居左，带 `%` 的跑到最右侧。
- **解法**：不能靠内容字符（是否含 `%`）来决定对齐，必须**基于表头列名进行列级对齐策略绑定**（表头含“名称/产品/规格”一律强制左对齐）。

### 💣 坑 9：数值列中的 `0` 或 `0.0` 出现对齐异常
- **现象**：正负数靠右，但 `0` 或 `0.0` 跑到左侧。
- **解法**：在数值列（含“涨跌/价格/涨幅/期数”）中，无论内容是数字还是 `0`、`0.0%`、`-`，整列一律强制统一右对齐。

### 💣 坑 10：openpyxl 默认样式导致折线图全变成单一绿色
- **现象**：折线图使用 `chart.style = 13` 时，同分类的所有折线都是浅绿、深绿，极难区分。
- **解法**：移除 `chart.style`，引入 D3 10/12 色高对比度调色板，并手动指定细线宽（`15000 EMU` ≈ 1.2pt）：
  ```python
  series.graphicalProperties.line.solidFill = color_hex
  series.graphicalProperties.line.width = 15000
  ```

---

## 4. 可直接复用的 AI 提示词模版 (Prompt Template)

```text
你是一名资深 Python DevOps 工程师。请为我编写自动化邮件推送与报表生成脚本，必须严格遵守以下规范：
1. 邮件发送模块：
   - 优先使用 587 端口 (STARTTLS) 并支持 465 (SSL) 自动回退；
   - 自动清洗 EMAIL_AUTH_TOKEN 中的内部空格（兼容 Google 16位应用专用密码）；
   - 附件中文名必须使用 RFC 2231 标准参数 filename=("utf-8", "", file_name)；
   - 异常捕获必须区分 SMTPAuthenticationError 与连接错误。
2. Excel 排版与图表模块 (openpyxl)：
   - 表头语义级对齐：产品/文本列强制左对齐，数值/涨幅/价格列（含0与0.0）强制右对齐，单位列居中；
   - 股票涨跌配色：涨/正数用加粗红色 (#C00000)，跌/负数用加粗绿色 (#008000)；
   - 折线图生成：必须显式设置 x_axis.axPos = 'b'、y_axis.axPos = 'l'，图表系列标题必须使用 SeriesLabel(v=...)，折线使用 15000 EMU 细线条及多色系高对比度调色板。
3. GitHub Actions 配置：
   - 定时 Cron 必须采用非整点分钟（如 38 分、55 分）以避开全球整点排队拥堵。
```
