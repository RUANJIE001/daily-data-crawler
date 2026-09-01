"""
src/crawler.py - 核心抓取与解析逻辑（支持站点B多期历史抓取与趋势构建）
"""
import re
from typing import Tuple, Dict, Any, List, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import pandas as pd
from src.utils import setup_logger, create_robust_session, get_beijing_now

logger = setup_logger("Crawler")

class CommodityCrawler:
    def __init__(self):
        self.session = create_robust_session()

    def fetch_site_a_100ppi(self, url: str = "https://www.100ppi.com/monitor2/") -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        抓取站点 A：生意社大宗商品数据监测
        """
        logger.info(f"开始抓取站点 A (生意社): {url}")
        meta = {
            "source_name": "生意社 (100ppi)",
            "url": url,
            "status": "失败",
            "row_count": 0,
            "detail": ""
        }
        
        try:
            resp = self.session.get(url, timeout=20)
            resp.encoding = resp.apparent_encoding or "utf-8"
            
            if resp.status_code != 200:
                meta["detail"] = f"HTTP 状态码异常: {resp.status_code}"
                return pd.DataFrame(), meta

            soup = BeautifulSoup(resp.text, "lxml")
            tables = soup.find_all("table")
            
            if not tables:
                meta["detail"] = "未在页面中找到数据表格"
                return pd.DataFrame(), meta

            # 寻找数据量最大的表格
            target_table = None
            max_rows = 0
            for tbl in tables:
                rows = tbl.find_all("tr")
                if len(rows) > max_rows:
                    max_rows = len(rows)
                    target_table = tbl

            if not target_table or max_rows <= 1:
                meta["detail"] = "未解析到有效数据行"
                return pd.DataFrame(), meta

            rows_data = []
            headers = []
            
            all_tr = target_table.find_all("tr")
            for i, tr in enumerate(all_tr):
                cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
                if not cells:
                    continue
                if i == 0 and not headers:
                    headers = cells
                else:
                    if len(cells) == len(headers):
                        rows_data.append(cells)
                    elif len(cells) > 0:
                        rows_data.append(cells)

            if headers and rows_data:
                max_len = max(len(r) for r in rows_data)
                if len(headers) < max_len:
                    headers.extend([f"列_{j+1}" for j in range(len(headers), max_len)])
                df = pd.DataFrame(rows_data, columns=headers[:max_len])
            else:
                df = pd.DataFrame(rows_data)

            df.dropna(how="all", inplace=True)
            meta["status"] = "成功"
            meta["row_count"] = len(df)
            meta["detail"] = f"成功提取 {len(df)} 条商品监测记录"
            logger.info(f"站点 A 抓取成功，共 {len(df)} 行数据")
            return df, meta

        except Exception as e:
            logger.error(f"站点 A 抓取发生异常: {e}", exc_info=True)
            meta["detail"] = f"抓取异常: {str(e)}"
            return pd.DataFrame(), meta

    def fetch_site_b_stats_gov_history(
        self,
        base_url: str = "https://www.stats.gov.cn/sj/zxfb/",
        max_issues: int = 10
    ) -> Tuple[pd.DataFrame, pd.DataFrame, List[str], Dict[str, Any]]:
        """
        抓取站点 B：国家统计局数据发布栏目，获取过去 10 次流通领域重要生产资料价格变动情况
        返回: (latest_df, trend_matrix_df, period_names, meta)
        """
        logger.info(f"开始抓取站点 B 过去 {max_issues} 期价格公告: {base_url}")
        meta = {
            "source_name": "国家统计局数据发布 (stats.gov.cn)",
            "url": base_url,
            "status": "失败",
            "latest_title": "",
            "crawled_issues_count": 0,
            "detail": ""
        }

        # 1. 分页检索目标文章链接列表
        article_links = [] # List of dict: {"title": ..., "url": ..., "date": ...}
        seen_urls = set()

        page_index = 0
        max_pages_to_scan = 15 # 最多扫描 15 页以确保找到 10 期

        while len(article_links) < max_issues and page_index < max_pages_to_scan:
            page_url = base_url if page_index == 0 else urljoin(base_url, f"index_{page_index}.html")
            logger.info(f"扫描数据发布列表第 {page_index + 1} 页: {page_url}")
            
            try:
                resp = self.session.get(page_url, timeout=20)
                resp.encoding = resp.apparent_encoding or "utf-8"
                if resp.status_code != 200:
                    logger.warning(f"第 {page_index + 1} 页请求失败，状态码: {resp.status_code}")
                    page_index += 1
                    continue

                soup = BeautifulSoup(resp.text, "lxml")
                found_in_page = 0
                for a_tag in soup.find_all("a", href=True):
                    title_text = (a_tag.get("title", "") or a_tag.get_text()).strip()
                    if "流通领域重要生产资料" in title_text and "价格变动" in title_text:
                        full_url = urljoin(page_url, a_tag["href"])
                        if full_url not in seen_urls:
                            seen_urls.add(full_url)
                            article_links.append({
                                "title": title_text,
                                "url": full_url
                            })
                            found_in_page += 1
                            if len(article_links) >= max_issues:
                                break

                logger.info(f"本页发现 {found_in_page} 篇目标文章，累计获取 {len(article_links)}/{max_issues} 篇")
            except Exception as e:
                logger.error(f"扫描第 {page_index + 1} 页出错: {e}")

            page_index += 1

        if not article_links:
            meta["detail"] = "未检索到任何流通领域重要生产资料价格变动公告"
            return pd.DataFrame(), pd.DataFrame(), [], meta

        logger.info(f"共定位到 {len(article_links)} 期价格公告，准备逐一解析详情...")
        meta["crawled_issues_count"] = len(article_links)
        meta["latest_title"] = article_links[0]["title"]

        # 2. 依次抓取各期的表格数据
        # raw_issue_tables: List of Tuple(issue_short_name, df_single_issue)
        parsed_issues = []

        for idx, art in enumerate(article_links):
            title = art["title"]
            url = art["url"]
            
            # 提取简短期数名称，如 "2026年8月中旬" 或 "26-08中"
            short_name = self._extract_period_name(title, idx)
            logger.info(f"[{idx+1}/{len(article_links)}] 解析: {short_name} -> {url}")
            
            df_issue = self._parse_single_article(url)
            if not df_issue.empty:
                parsed_issues.append((short_name, df_issue))

        if not parsed_issues:
            meta["detail"] = "所有公告详情解析均未获取到有效表格数据"
            return pd.DataFrame(), pd.DataFrame(), [], meta

        # 最近一期作为 Sheet 2 的主要数据
        latest_short_name, latest_df = parsed_issues[0]

        # 3. 构建过去 10 次的趋势透视矩阵 (Sheet 3) - 采用时间倒序排列（最新期在最左侧）
        trend_matrix_df, period_headers = self._build_trend_matrix(parsed_issues)

        meta["status"] = "成功"
        meta["detail"] = f"成功采集过去 {len(parsed_issues)} 次价格发布，并生成 {len(trend_matrix_df)} 项商品趋势矩阵"
        return latest_df, trend_matrix_df, period_headers, meta

    def _extract_period_name(self, title: str, fallback_idx: int) -> str:
        """从文章标题中提取期数，如 '2026年8月中旬' -> '2026-08中' 或 '8月中旬'"""
        match = re.search(r"(\d{4}年)?(\d{1,2}月[上中下]旬)", title)
        if match:
            year = match.group(1) or ""
            period = match.group(2)
            if year:
                return f"{year.replace('年', '-')}{period}"
            return period
        match_date = re.search(r"(\d{4})[年\-](\d{1,2})[月\-](\d{1,2})", title)
        if match_date:
            return f"{match_date.group(2)}月{match_date.group(3)}日"
        return f"第{fallback_idx + 1}期"

    def _parse_single_article(self, url: str) -> pd.DataFrame:
        """解析单篇统计局价格公告中的 50 种生产资料表格"""
        try:
            resp = self.session.get(url, timeout=20)
            resp.encoding = resp.apparent_encoding or "utf-8"
            if resp.status_code != 200:
                return pd.DataFrame()

            soup = BeautifulSoup(resp.text, "lxml")
            article_table = soup.find("table")
            if not article_table:
                return pd.DataFrame()

            raw_rows = []
            for tr in article_table.find_all("tr"):
                cells = [td.get_text(strip=True).replace("\xa0", "") for td in tr.find_all(["th", "td"])]
                if cells:
                    raw_rows.append(cells)

            if len(raw_rows) <= 1:
                return pd.DataFrame()

            std_columns = ["分类大类", "产品名称", "规格/型号", "单位", "本期价格(元)", "比上期价格涨跌(元)", "涨跌幅(%)"]
            parsed_data = []
            current_category = "综合/其他"

            for row in raw_rows:
                row_str = "".join(row)
                if "产品名称" in row_str or "本期价格" in row_str or "涨跌幅" in row_str:
                    continue
                
                # 判断分类大类行（如 "一、黑色金属"）
                if len(row) == 1 or any(row[0].startswith(x) for x in ["一、", "二、", "三、", "四、", "五、", "六、", "七、", "八、", "九、", "十、"]):
                    current_category = row[0]
                    continue
                
                if len(row) >= 5:
                    product = row[0]
                    if len(row) == 5:
                        spec = "-"
                        unit = row[1]
                        price = row[2]
                        diff = row[3]
                        rate = row[4]
                    else:
                        spec = row[1]
                        unit = row[2]
                        price = row[3]
                        diff = row[4]
                        rate = row[5] if len(row) > 5 else "0.0"

                    # 数值清洗
                    clean_price = self._clean_num(price)
                    clean_diff = self._clean_num(diff)
                    clean_rate = self._clean_num(rate)

                    parsed_data.append([
                        current_category, product, spec, unit, clean_price, clean_diff, clean_rate
                    ])

            return pd.DataFrame(parsed_data, columns=std_columns)
        except Exception as e:
            logger.error(f"解析文章 {url} 失败: {e}")
            return pd.DataFrame()

    def _clean_num(self, val_str: str) -> float:
        """安全将字符串转为浮点数"""
        try:
            s = str(val_str).replace(",", "").replace("%", "").strip()
            return float(s)
        except Exception:
            return 0.0

    def _build_trend_matrix(self, chronological_issues: List[Tuple[str, pd.DataFrame]]) -> Tuple[pd.DataFrame, List[str]]:
        """
        根据按时间正序排列的各期数据，构建 50 种生产资料价格趋势宽表
        """
        if not chronological_issues:
            return pd.DataFrame(), []

        # 以最新一期或第一期作为基准商品清单
        base_df = chronological_issues[-1][1].copy()
        
        # 基础列：分类大类、产品名称、规格/型号、单位
        matrix_data = []
        period_headers = [issue_name for issue_name, _ in chronological_issues]

        for _, row in base_df.iterrows():
            item_record = {
                "分类大类": row["分类大类"],
                "产品名称": row["产品名称"],
                "规格/型号": row["规格/型号"],
                "单位": row["单位"]
            }
            
            # 填入各期价格
            prices = []
            for issue_name, df_issue in chronological_issues:
                # 按产品名称和规格匹配
                match = df_issue[df_issue["产品名称"] == row["产品名称"]]
                if not match.empty:
                    p = float(match.iloc[0]["本期价格(元)"])
                else:
                    p = None
                item_record[issue_name] = p
                if p is not None:
                    prices.append(p)

            # 计算 10 期总涨跌额与总涨跌幅 (最新期 prices[0] 对比 最早一期 prices[-1])
            if len(prices) >= 2 and prices[-1] > 0:
                newest_p = prices[0]
                oldest_p = prices[-1]
                diff_total = round(newest_p - oldest_p, 2)
                rate_total = round((newest_p - oldest_p) / oldest_p * 100, 2)
            else:
                diff_total = 0.0
                rate_total = 0.0

            item_record["区间总涨跌(元)"] = diff_total
            item_record["区间总涨跌幅(%)"] = rate_total
            matrix_data.append(item_record)

        trend_df = pd.DataFrame(matrix_data)
        return trend_df, period_headers
