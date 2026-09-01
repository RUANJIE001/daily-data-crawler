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
        # 1. 抓取数据
        crawler = CommodityCrawler()
        
        df_a, meta_a = crawler.fetch_site_a_100ppi()
        df_b, meta_b = crawler.fetch_site_b_stats_gov()

        # 2. 导出 Excel 报表
        exporter = ExcelExporter(output_dir="./reports")
        report_path = exporter.generate_daily_report(
            site_a_df=df_a,
            site_a_meta=meta_a,
            site_b_df=df_b,
            site_b_meta=meta_b
        )

        # 3. 邮件发送
        notifier = EmailNotifier()
        send_success = notifier.send_report(
            excel_path=report_path,
            meta_a=meta_a,
            meta_b=meta_b
        )

        # 4. 执行总结
        elapsed = (get_beijing_now() - start_time).total_seconds()
        logger.info("=" * 60)
        logger.info(f"✅ 任务全流程执行完成，耗时: {elapsed:.2f} 秒")
        logger.info(f"📊 站点 A (生意社): {meta_a['status']} ({meta_a['row_count']} 行)")
        logger.info(f"📊 站点 B (统计局): {meta_b['status']} ({meta_b['row_count']} 行)")
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
