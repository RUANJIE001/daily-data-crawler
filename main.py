"""
main.py - 每日数据采集、导出与邮件推送总调度入口
"""
import sys
from src.utils import setup_logger, get_beijing_now
from src.crawler import CommodityCrawler
from src.exporter import ExcelExporter
from src.notifier import EmailNotifier

logger = setup_logger("Main")

def main():
    start_time = get_beijing_now()
    logger.info("=" * 60)
    logger.info(f"🚀 开始执行每日数据采集任务 | 当前北京时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    try:
        crawler = CommodityCrawler()
        
        # 判断是否为周一 (weekday() == 0) 或 启用了强制抓取参数
        force_site_b = ("--force-site-b" in sys.argv) or (sys.argv[1:2] == ["--all"])
        is_monday = (start_time.weekday() == 0) or force_site_b
        weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][start_time.weekday()]

        logger.info(f"📅 今天是: {weekday_cn} | 抓取模式: {'📈 周一深度版 (站点A + 站点B过去10期趋势)' if is_monday else '📊 每日监测版 (仅站点A生意社)'}")

        # 1. 抓取站点 A (生意社) - 每天固定抓取
        df_a, meta_a = crawler.fetch_site_a_100ppi()

        df_b_latest = None
        df_b_trend = None
        period_headers = []
        meta_b = None

        # 2. 抓取站点 B (国家统计局数据发布 - 仅在周一抓取过去 10 期与构建走势矩阵)
        if is_monday:
            logger.info("⚡️ 触发周一策略：开始抓取国家统计局过去 10 期生产资料价格公告...")
            df_b_latest, df_b_trend, period_headers, meta_b = crawler.fetch_site_b_stats_gov_history(
                base_url="https://www.stats.gov.cn/sj/zxfb/",
                max_issues=10
            )
        else:
            logger.info("⏩ 今日非周一，跳过站点 B (国家统计局历史数据) 抓取以极速生成日报。")

        # 3. 导出 Excel 报表 (常规每日生成 1-Sheet，周一生成 3-Sheet 附带原生趋势折线图)
        exporter = ExcelExporter(output_dir="./reports")
        report_path = exporter.generate_daily_report(
            site_a_df=df_a,
            site_a_meta=meta_a,
            site_b_latest_df=df_b_latest,
            site_b_trend_df=df_b_trend,
            period_headers=period_headers,
            site_b_meta=meta_b,
            is_weekly_report=is_monday
        )

        # 4. 发送对应模版的邮件 (每日版 / 周一深度版)
        notifier = EmailNotifier()
        send_success = notifier.send_report(
            excel_path=report_path,
            meta_a=meta_a,
            meta_b=meta_b,
            period_headers=period_headers,
            is_weekly_report=is_monday
        )

        # 5. 执行总结
        elapsed = (get_beijing_now() - start_time).total_seconds()
        logger.info("=" * 60)
        logger.info(f"✅ 任务全流程执行完成，耗时: {elapsed:.2f} 秒")
        logger.info(f"📊 站点 A (生意社): {meta_a['status']} ({meta_a['row_count']} 行)")
        if is_monday and meta_b:
            logger.info(f"📊 站点 B (统计局最新): {meta_b['status']} ({len(df_b_latest) if df_b_latest is not None else 0} 行)")
            logger.info(f"📈 站点 B (历史趋势): 采集 {len(period_headers)} 期，构建 {len(df_b_trend) if df_b_trend is not None else 0} 项商品走势图")
            logger.info("📑 生成工作表: 3 个 Sheet (Sheet 1 + Sheet 2 + Sheet 3)")
        else:
            logger.info("📑 生成工作表: 1 个 Sheet (Sheet 1 生意社大宗商品监测)")
        logger.info(f"📧 邮件推送状态: {'成功' if send_success else '失败'}")
        logger.info("=" * 60)

        if not send_success:
            logger.warning("邮件推送未成功，请检查 GitHub Secrets 配置是否正确。")
            sys.exit(1)

    except Exception as e:
        logger.critical(f"❌ 任务运行期间遭遇未捕获的致命错误: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
