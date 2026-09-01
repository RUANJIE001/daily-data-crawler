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
        
        # 1. 抓取站点 A (生意社)
        df_a, meta_a = crawler.fetch_site_a_100ppi()

        # 2. 抓取站点 B (国家统计局数据发布 - 过去 10 期生产资料价格变动)
        df_b_latest, df_b_trend, period_headers, meta_b = crawler.fetch_site_b_stats_gov_history(
            base_url="https://www.stats.gov.cn/sj/zxfb/",
            max_issues=10
        )

        # 3. 导出 3-Sheet Excel 报表与原生趋势折线图
        exporter = ExcelExporter(output_dir="./reports")
        report_path = exporter.generate_daily_report(
            site_a_df=df_a,
            site_a_meta=meta_a,
            site_b_latest_df=df_b_latest,
            site_b_trend_df=df_b_trend,
            period_headers=period_headers,
            site_b_meta=meta_b
        )

        # 4. 发送带 3-Sheet 报表的邮件
        notifier = EmailNotifier()
        send_success = notifier.send_report(
            excel_path=report_path,
            meta_a=meta_a,
            meta_b=meta_b,
            period_headers=period_headers
        )

        # 5. 执行总结
        elapsed = (get_beijing_now() - start_time).total_seconds()
        logger.info("=" * 60)
        logger.info(f"✅ 任务全流程执行完成，耗时: {elapsed:.2f} 秒")
        logger.info(f"📊 站点 A (生意社): {meta_a['status']} ({meta_a['row_count']} 行)")
        logger.info(f"📊 站点 B (统计局最新): {meta_b['status']} ({len(df_b_latest)} 行)")
        logger.info(f"📈 站点 B (历史趋势): 采集 {len(period_headers)} 期，构建 {len(df_b_trend)} 项商品走势图")
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
