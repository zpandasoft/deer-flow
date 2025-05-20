# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
Web爬虫服务模块。

提供网页爬取和搜索功能，支持内容抽取和处理。
"""

import logging
import os
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
import urllib.parse

import aiohttp
import requests
from bs4 import BeautifulSoup

from src.crawler.crawler import Crawler
from src.taskflow.exceptions import CrawlerError

# 获取日志记录器
logger = logging.getLogger(__name__)


class WebCrawlerService:
    """
    网页爬虫服务类。
    
    提供网页爬取、搜索和内容提取功能。
    """
    
    def __init__(self, proxy_config: Optional[Dict[str, str]] = None):
        """
        初始化爬虫服务。
        
        Args:
            proxy_config: 代理配置，格式为 {"http": "http://proxy:port", "https": "https://proxy:port"}
        """
        self.session = requests.Session()
        if proxy_config:
            self.session.proxies.update(proxy_config)
        
        # 创建基础爬虫实例
        self.crawler = Crawler()
        
        # 用于异步请求的会话
        self.async_session = None
        
        # 搜索API配置
        self.serp_api_key = os.getenv("SERP_API_KEY")
        self.use_serp_api = self.serp_api_key is not None
    
    async def _ensure_async_session(self):
        """确保异步会话已创建"""
        if self.async_session is None:
            self.async_session = aiohttp.ClientSession()
    
    async def close(self):
        """关闭异步会话"""
        if self.async_session:
            await self.async_session.close()
            self.async_session = None
    
    async def crawl_url(self, url: str) -> Dict[str, Any]:
        """
        爬取指定URL的内容。
        
        Args:
            url: 要爬取的URL
            
        Returns:
            包含爬取内容和元数据的字典
            
        Raises:
            CrawlerError: 爬取失败时
        """
        try:
            # 使用基础爬虫获取文章
            article = self.crawler.crawl(url)
            
            # 构建结果
            result = {
                "url": url,
                "title": article.title,
                "content": article.to_markdown(),
                "content_html": article.html_content,
                "content_blocks": article.to_message(),
                "timestamp": datetime.now().isoformat()
            }
            
            return result
        except Exception as e:
            logger.error(f"爬取URL {url} 失败: {str(e)}")
            raise CrawlerError(f"爬取URL失败: {str(e)}")
    
    async def _search_with_serp_api(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        使用SerpAPI搜索。
        
        Args:
            query: 搜索查询词
            limit: 返回结果数量
            
        Returns:
            搜索结果列表
        """
        await self._ensure_async_session()
        
        params = {
            "engine": "google",
            "q": query,
            "api_key": self.serp_api_key,
            "num": limit
        }
        
        try:
            async with self.async_session.get("https://serpapi.com/search", params=params) as response:
                if response.status != 200:
                    logger.error(f"SerpAPI请求失败: {response.status}")
                    raise CrawlerError(f"搜索API请求失败: 状态码 {response.status}")
                
                data = await response.json()
                
                if "error" in data:
                    logger.error(f"SerpAPI返回错误: {data['error']}")
                    raise CrawlerError(f"搜索API返回错误: {data['error']}")
                
                results = []
                
                # 处理普通搜索结果
                if "organic_results" in data:
                    for result in data["organic_results"][:limit]:
                        results.append({
                            "title": result.get("title", ""),
                            "url": result.get("link", ""),
                            "snippet": result.get("snippet", ""),
                            "position": result.get("position", 0)
                        })
                
                return results
        except Exception as e:
            logger.error(f"使用SerpAPI搜索时出错: {str(e)}")
            raise CrawlerError(f"搜索失败: {str(e)}")
    
    async def _search_fallback(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        备用搜索方法（直接抓取搜索引擎结果页）。
        
        注意：此方法仅作为备用，可能违反搜索引擎服务条款。
        生产环境应使用官方API。
        
        Args:
            query: 搜索查询词
            limit: 返回结果数量
            
        Returns:
            搜索结果列表
        """
        await self._ensure_async_session()
        
        # 构建搜索URL
        search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&num={limit}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        try:
            async with self.async_session.get(search_url, headers=headers) as response:
                if response.status != 200:
                    logger.error(f"搜索请求失败: {response.status}")
                    raise CrawlerError(f"搜索请求失败: 状态码 {response.status}")
                
                html = await response.text()
                
                # 解析搜索结果
                soup = BeautifulSoup(html, "html.parser")
                results = []
                
                # 提取搜索结果（根据Google搜索结果的HTML结构）
                for idx, result in enumerate(soup.select("div.g")[:limit]):
                    title_elem = result.select_one("h3")
                    link_elem = result.select_one("a")
                    snippet_elem = result.select_one("div.VwiC3b")
                    
                    if title_elem and link_elem and link_elem.has_attr("href"):
                        title = title_elem.get_text()
                        url = link_elem["href"]
                        snippet = snippet_elem.get_text() if snippet_elem else ""
                        
                        # 确保URL是以http开头的
                        if url.startswith("/url?"):
                            url_parts = urllib.parse.urlparse(url)
                            query_parts = urllib.parse.parse_qs(url_parts.query)
                            if "q" in query_parts:
                                url = query_parts["q"][0]
                        
                        results.append({
                            "title": title,
                            "url": url,
                            "snippet": snippet,
                            "position": idx + 1
                        })
                
                return results
        except Exception as e:
            logger.error(f"备用搜索方法失败: {str(e)}")
            raise CrawlerError(f"搜索失败: {str(e)}")
    
    async def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        搜索关键词。
        
        Args:
            query: 搜索查询词
            limit: 返回结果数量
            
        Returns:
            搜索结果列表
            
        Raises:
            CrawlerError: 搜索失败时
        """
        try:
            # 优先使用SerpAPI
            if self.use_serp_api:
                return await self._search_with_serp_api(query, limit)
            # 否则使用备用方法
            else:
                logger.warning("未配置SERP_API_KEY，使用备用搜索方法")
                return await self._search_fallback(query, limit)
        except Exception as e:
            logger.error(f"搜索查询 '{query}' 失败: {str(e)}")
            raise CrawlerError(f"搜索查询失败: {str(e)}")
    
    async def search_and_crawl(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        搜索关键词并爬取结果页面。
        
        Args:
            query: 搜索查询词
            limit: 返回结果数量
            
        Returns:
            包含爬取内容的搜索结果列表
            
        Raises:
            CrawlerError: 操作失败时
        """
        try:
            # 先执行搜索
            search_results = await self.search(query, limit)
            
            # 并发爬取搜索结果
            crawled_results = []
            
            async def crawl_result(result):
                try:
                    # 爬取网页内容
                    content = await self.crawl_url(result["url"])
                    # 合并搜索结果和爬取内容
                    return {**result, **content}
                except Exception as e:
                    logger.warning(f"爬取搜索结果 {result['url']} 失败: {str(e)}")
                    # 返回原始搜索结果，标记爬取失败
                    return {
                        **result,
                        "crawl_success": False,
                        "crawl_error": str(e)
                    }
            
            # 创建爬取任务
            tasks = [crawl_result(result) for result in search_results]
            
            # 并发执行爬取任务
            for task_result in await asyncio.gather(*tasks, return_exceptions=True):
                if isinstance(task_result, Exception):
                    logger.warning(f"爬取任务失败: {str(task_result)}")
                else:
                    crawled_results.append(task_result)
            
            return crawled_results
        except Exception as e:
            logger.error(f"搜索并爬取查询 '{query}' 失败: {str(e)}")
            raise CrawlerError(f"搜索并爬取失败: {str(e)}")
    
    def _extract_main_content(self, html: str) -> str:
        """
        从HTML提取主要内容。
        
        Args:
            html: HTML内容
            
        Returns:
            提取的主要内容
        """
        # 使用现有Crawler的内容提取功能
        from src.crawler.readability_extractor import ReadabilityExtractor
        from src.crawler.article import Article
        
        extractor = ReadabilityExtractor()
        article = extractor.extract_article(html)
        
        return article.to_markdown() 