"""
src/exporter.py - Excel 报表结构化导出与样式美化
"""
import os
from typing import Dict
import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from src.utils import setup_logger, get_beijing_now

logger = setup_logger("Exporter")

class ExcelExporter:
    def __init__(self, output_dir: str = "./reports"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_daily_report(
        self,
        site_a_df: pd.DataFrame,
        site_a_meta: Dict,
        site_b_df: pd.DataFrame,
        site_b_meta: Dict
    ) -> str:
        """
        生成命名为 Daily_Report_YYYYMMDD.xlsx 的双 Sheet 专业报表
        """
        today_str = get_beijing_now().strftime("%Y%m%d")
        file_name = f"Daily_Report_{today_str}.xlsx"
        file_path = os.path.join(self.output_dir, file_name)
        
        logger.info(f"准备生成每日 Excel 报表: {file_path}")

        # 使用 openpyxl 引擎写入多 Sheet
        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            # 1. 写入站点 A 数据
            df_a = site_a_df if not site_a_df.empty else pd.DataFrame({"提示": ["今日未获取到有效数据或页面正在安全检查"]})
            df_a.to_excel(writer, sheet_name="生意社大宗商品监测", index=False, startrow=3)

            # 2. 写入站点 B 数据
            df_b = site_b_df if not site_b_df.empty else pd.DataFrame({"提示": ["统计局暂无新一期流通领域生产资料价格发布"]})
            df_b.to_excel(writer, sheet_name="统计局重要生产资料价格", index=False, startrow=3)

        # 进行单元格美化排版
        self._apply_professional_styling(file_path, site_a_meta, site_b_meta)
        
        logger.info(f"报表生成完毕，文件路径: {file_path} (大小: {os.path.getsize(file_path)} 字节)")
        return file_path

    def _apply_professional_styling(self, file_path: str, meta_a: Dict, meta_b: Dict):
        from openpyxl import load_workbook
        wb = load_workbook(file_path)

        # 样式定义
        title_font = Font(name="微软雅黑", size=13, bold=True, color="1F4E78")
        meta_font = Font(name="微软雅黑", size=9, italic=True, color="595959")
        header_font = Font(name="微软雅黑", size=10, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        
        data_font = Font(name="微软雅黑", size=9.5)
        alt_fill = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
        
        thin_border = Border(
            left=Side(style="thin", color="D9D9D9"),
            right=Side(style="thin", color="D9D9D9"),
            top=Side(style="thin", color="D9D9D9"),
            bottom=Side(style="thin", color="D9D9D9")
        )

        sheet_configs = [
            ("生意社大宗商品监测", meta_a, "生意社 (100ppi) 大宗商品每日价格监测报表"),
            ("统计局重要生产资料价格", meta_b, f"国家统计局 - {meta_b.get('title', '流通领域重要生产资料市场价格变动情况')}")
        ]

        now_str = get_beijing_now().strftime("%Y-%m-%d %H:%M:%S")

        for sheet_name, meta, report_title in sheet_configs:
            if sheet_name not in wb.sheetnames:
                continue
            ws = wb[sheet_name]
            ws.views.sheetView[0].showGridLines = True

            # 写入顶部元数据信息
            ws.cell(row=1, column=1, value=report_title).font = title_font
            meta_desc = f"【数据来源】: {meta.get('url')}  |  【生成时间 (北京时间)】: {now_str}  |  【记录数】: {meta.get('row_count', 0)} 条"
            ws.cell(row=2, column=1, value=meta_desc).font = meta_font

            header_row = 4
            max_row = ws.max_row
            max_col = ws.max_column

            # 表头样式美化
            for col in range(1, max_col + 1):
                cell = ws.cell(row=header_row, column=col)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                cell.border = thin_border
            ws.row_dimensions[header_row].height = 28

            # 数据单元格样式美化
            for row in range(header_row + 1, max_row + 1):
                ws.row_dimensions[row].height = 20
                is_alt = (row % 2 == 0)
                for col in range(1, max_col + 1):
                    cell = ws.cell(row=row, column=col)
                    cell.font = data_font
                    cell.border = thin_border
                    if is_alt:
                        cell.fill = alt_fill
                    
                    val_str = str(cell.value or "")
                    if any(c in val_str for c in ["%", "元", "吨", "千克"]) or val_str.replace(".", "", 1).replace("-", "", 1).isdigit():
                        cell.alignment = Alignment(horizontal="right", vertical="center")
                    else:
                        cell.alignment = Alignment(horizontal="left", vertical="center")

            # 自动调整列宽
            for col in ws.columns:
                col_letter = get_column_letter(col[0].column)
                max_len = 0
                for cell in col:
                    if cell.row < 3: # 忽略顶部长文本行
                        continue
                    if cell.value:
                        val_str = str(cell.value)
                        width = sum(2 if ord(c) > 127 else 1 for c in val_str)
                        max_len = max(max_len, width)
                ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

        wb.save(file_path)
