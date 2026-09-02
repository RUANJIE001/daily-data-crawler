"""
scripts/remote_trigger.py - GitHub Actions 远程高精度触发脚本
用于在 VPS、云函数、本地 Mac / NAS 定时调度，实现 100% 准点、秒级唤醒 GitHub Actions
"""
import os
import sys
import json
import urllib.request
import ssl
from typing import Optional, Dict, Any

class GitHubActionsTrigger:
    def __init__(self, owner: str = "RUANJIE001", repo: str = "daily-data-crawler", token: Optional[str] = None):
        self.owner = owner
        self.repo = repo
        self.token = (token or os.getenv("GH_PAT_TOKEN") or "").strip().replace(" ", "")
        self.api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/actions/workflows/daily_crawler.yml/dispatches"

    def trigger(self, ref: str = "main", inputs: Optional[Dict[str, Any]] = None) -> bool:
        if not self.token:
            print("❌ 错误: 未提供 GitHub PAT 访问令牌！请设置环境变量 GH_PAT_TOKEN 或在初始化时传入 token。")
            return False

        payload = {"ref": ref}
        if inputs:
            payload["inputs"] = inputs

        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "GitHubActions-Remote-Trigger/1.0",
            "Content-Type": "application/json"
        }

        req = urllib.request.Request(self.api_url, data=data, headers=headers, method="POST")
        ctx = ssl.create_default_context()

        try:
            print(f"🚀 正在远程拍醒 GitHub Actions: {self.owner}/{self.repo} (分支: {ref})...")
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                if resp.status in [200, 204]:
                    print("🎉 [成功] 已在 3 秒内秒级唤醒 GitHub Actions 执行！")
                    return True
                else:
                    print(f"⚠️ [警告] 响应状态码异常: HTTP {resp.status}")
                    return False
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="ignore")
            if e.code == 404:
                print(f"❌ 错误 404: 仓库或工作流文件不存在，请检查仓库名与分支是否正确！")
            elif e.code in [401, 403]:
                print(f"❌ 错误 {e.code}: PAT 令牌无效或缺少 'workflow' / 'repo' 权限！")
            else:
                print(f"❌ 触发失败: HTTP {e.code} - {err}")
            return False
        except Exception as e:
            print(f"❌ 连接异常: {e}")
            return False

if __name__ == "__main__":
    token = sys.argv[1] if len(sys.argv) > 1 else os.getenv("GH_PAT_TOKEN")
    client = GitHubActionsTrigger(token=token)
    success = client.trigger(inputs={"trigger_source": "vps-remote-cron"})
    sys.exit(0 if success else 1)
