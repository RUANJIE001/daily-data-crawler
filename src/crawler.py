"""
src/crawler.py - 核心抓取与解析逻辑
"""
from typing import Tuple, Dict, Any, Optional
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

            # 寻找最匹配的数据表格（根据列数或内容特征选择最大的表格）
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

            # 解析表头与数据行
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

            # 构建 DataFrame
            if headers and rows_data:
                max_len = max(len(r) for r in rows_data)
                if len(headers) < max_len:
                    headers.extend([f"列_{j+1}" for j in range(len(headers), max_len)])
                df = pd.DataFrame(rows_data, columns=headers[:max_len])
            else:
                df = pd.DataFrame(rows_data)

            # 数据清洗：去除全空行
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

    def fetch_site_b_stats_gov(self, base_url: str = "https://www.stats.gov.cn/sj/") -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        抓取站点 B：国家统计局 - 流通领域重要生产资料市场价格变动情况
        """
        logger.info(f"开始扫描站点 B (国家统计局数据发布): {base_url}")
        meta = {
            "source_name": "国家统计局 (stats.gov.cn)",
            "url": base_url,
            "status": "失败",
            "row_count": 0,
            "title": "未找到最新发布",
            "detail": ""
        }

        try:
            resp = self.session.get(base_url, timeout=20)
            resp.encoding = resp.apparent_encoding or "utf-8"
            
            if resp.status_code != 200:
                meta["detail"] = f"导航页 HTTP 状态码异常: {resp.status_code}"
                return pd.DataFrame(), meta

            soup = BeautifulSoup(resp.text, "lxml")
            
            # 扫描包含“流通领域重要生产资料市场价格变动情况”的最新文章链接
            target_link: Optional[str] = None
            target_title: str = ""
            
            for a_tag in soup.find_all("a", href=True):
                text = (a_tag.get_text() + " " + a_tag.get("title", "")).strip()
                if "流通领域重要生产资料" in text and "价格变动" in text:
                    target_link = urljoin(base_url, a_tag["href"])
                    target_title = text.split("\n")[0].strip()
                    break

            # 如果在首页未直接找到，尝试查找“最新发布”栏目
            if not target_link:
                zxfb_url = urljoin(base_url, "zxfb/")
                logger.info(f"首页未检索到，深入扫描最新发布栏目: {zxfb_url}")
                zxfb_resp = self.session.get(zxfb_url, timeout=20)
                zxfb_resp.encoding = zxfb_resp.apparent_encoding or "utf-8"
                zxfb_soup = BeautifulSoup(zxfb_resp.text, "lxml")
                for a_tag in zxfb_soup.find_all("a", href=True):
                    text = (a_tag.get_text() + " " + a_tag.get("title", "")).strip()
                    if "流通领域重要生产资料" in text and "价格变动" in text:
                        target_link = urljoin(zxfb_url, a_tag["href"])
                        target_title = text.split("\n")[0].strip()
                        break

            if not target_link:
                meta["status"] = "无新发布"
                meta["detail"] = "未检索到近期流通领域重要生产资料市场价格变动公告"
                logger.warning("站点 B 未检索到目标文章")
                return pd.DataFrame(), meta

            logger.info(f"命中最新价格公告: [{target_title}] -> {target_link}")
            meta["title"] = target_title
            meta["url"] = target_link

            # 请求具体文章详情页
            art_resp = self.session.get(target_link, timeout=20)
            art_resp.encoding = art_resp.apparent_encoding or "utf-8"
            art_soup = BeautifulSoup(art_resp.text, "lxml")

            article_table = art_soup.find("table")
            if not article_table:
                meta["detail"] = "公告详情页中未找到价格数据表格"
                return pd.DataFrame(), meta

            # 解析表格数据（处理大类层级结构，如“一、黑色金属”，“二、有色金属”）
            raw_rows = []
            for tr in article_table.find_all("tr"):
                cells = [td.get_text(strip=True).replace("\xa0", "") for td in tr.find_all(["th", "td"])]
                if cells:
                    raw_rows.append(cells)

            if len(raw_rows) <= 1:
                meta["detail"] = "公告详情页表格无有效数据"
                return pd.DataFrame(), meta

            # 标准表头结构定义
            std_columns = ["分类大类", "产品名称", "规格/型号", "单位", "本期价格(元)", "比上期价格涨跌(元)", "涨跌幅(%)"]
            parsed_data = []
            current_category = "综合/其他"

            for row in raw_rows:
                # 过滤纯表头行
                row_str = "".join(row)
                if "产品名称" in row_str or "本期价格" in row_str or "涨跌幅" in row_str:
                    continue
                
                # 判断是否为大类分类行（如 "一、黑色金属"）
                if len(row) == 1 or (len(row) >= 1 and any(row[0].startswith(x) for x in ["一、", "二、", "三、", "四、", "五、", "六、", "七、", "八、", "九、", "十、"])):
                    current_category = row[0]
                    continue
                
                # 正常数据行
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

                    parsed_data.append([
                        current_category, product, spec, unit, price, diff, rate
                    ])

            df = pd.DataFrame(parsed_data, columns=std_columns)
            meta["status"] = "成功"
            meta["row_count"] = len(df)
            meta["detail"] = f"成功解析 [{target_title}]，共 {len(df)} 种生产资料价格"
            logger.info(f"站点 B 抓取解析成功，提取 {len(df)} 条价格变动记录")
            return df, meta

        except Exception as e:
            logger.error(f"站点 B 抓取发生异常: {e}", exc_info=True)
            meta["detail"] = f"抓取异常: {str(e)}"
            return pd.DataFrame(), meta
