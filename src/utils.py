"""
src/utils.py - 通用工具函数与网络请求会话封装
"""
import logging
from datetime import datetime, timezone, timedelta
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# 统一使用北京时间 (UTC+8)
BEIJING_TZ = timezone(timedelta(hours=8))

def get_beijing_now() -> datetime:
    """获取当前北京时间"""
    return datetime.now(BEIJING_TZ)

def setup_logger(name: str = "DailyCrawler") -> logging.Logger:
    """配置控制台格式化日志"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

def create_robust_session(retries: int = 3, backoff_factor: float = 1.5) -> requests.Session:
    """
    创建带自动重试、超时与现代浏览器 User-Agent 伪装的 Session
    """
    session = requests.Session()
    
    # 配置指数退避重试策略
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # 模拟真实 Chrome 浏览器请求头
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
                  "image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    })
    return session
