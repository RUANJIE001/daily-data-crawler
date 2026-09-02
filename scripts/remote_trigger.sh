#!/bin/bash
# scripts/remote_trigger.sh - 单行 cURL 远程拍醒脚本
# 使用方法: ./remote_trigger.sh <YOUR_GH_PAT_TOKEN>

TOKEN="${1:-$GH_PAT_TOKEN}"

if [ -z "$TOKEN" ]; then
    echo "❌ 错误: 请传入 GitHub PAT Token 或设置 GH_PAT_TOKEN 环境变量！"
    exit 1
fi

echo "🚀 发起远程触发请求..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $TOKEN" \
  https://api.github.com/repos/RUANJIE001/daily-data-crawler/actions/workflows/daily_crawler.yml/dispatches \
  -d '{"ref":"main","inputs":{"trigger_source":"curl-cron"}}')

if [ "$STATUS" -eq 204 ] || [ "$STATUS" -eq 200 ]; then
    echo "🎉 [成功] GitHub Actions 已被成功触发 (HTTP $STATUS)"
    exit 0
else
    echo "❌ [失败] 触发返回 HTTP $STATUS"
    exit 1
fi
