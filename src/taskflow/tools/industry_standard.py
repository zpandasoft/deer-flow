# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
行业标准服务模块。

提供行业标准的查询、更新和监控功能。
"""

import logging
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

from sqlalchemy.orm import Session

from src.taskflow.db.service import industry_standard_service, get_db
from src.taskflow.db.models import IndustryStandard
from src.taskflow.tools.web_crawler import WebCrawlerService
from src.taskflow.exceptions import DatabaseError, IndustryStandardError

# 获取日志记录器
logger = logging.getLogger(__name__)


class IndustryStandardService:
    """
    行业标准服务类。
    
    提供行业标准的查询、更新和监控功能。
    """
    
    def __init__(self, web_crawler_service: Optional[WebCrawlerService] = None):
        """
        初始化行业标准服务。
        
        Args:
            web_crawler_service: 网页爬虫服务，用于获取标准更新
        """
        self.web_crawler_service = web_crawler_service
    
    def get_standards_by_industry(self, industry_type: str, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """
        根据行业类型获取相关标准。
        
        Args:
            industry_type: 行业类型
            skip: 跳过的记录数
            limit: 返回的最大记录数
            
        Returns:
            标准列表
            
        Raises:
            IndustryStandardError: 查询失败时
        """
        try:
            with get_db() as db:
                standards = industry_standard_service.get_by_industry(db, industry_type, skip, limit)
                return [self._format_standard(std) for std in standards]
        except DatabaseError as e:
            logger.error(f"查询行业标准时出错: {str(e)}")
            raise IndustryStandardError(f"无法获取行业标准: {str(e)}")
    
    def get_standards_by_region(self, region: str, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """
        根据地区获取相关标准。
        
        Args:
            region: 地区名称
            skip: 跳过的记录数
            limit: 返回的最大记录数
            
        Returns:
            标准列表
            
        Raises:
            IndustryStandardError: 查询失败时
        """
        try:
            with get_db() as db:
                standards = industry_standard_service.get_by_region(db, region, skip, limit)
                return [self._format_standard(std) for std in standards]
        except DatabaseError as e:
            logger.error(f"按地区查询行业标准时出错: {str(e)}")
            raise IndustryStandardError(f"无法按地区获取行业标准: {str(e)}")
    
    def get_standard_details(self, standard_id: str) -> Dict[str, Any]:
        """
        获取标准详情。
        
        Args:
            standard_id: 标准ID
            
        Returns:
            标准详情
            
        Raises:
            IndustryStandardError: 查询失败时
        """
        try:
            with get_db() as db:
                standard = industry_standard_service.get(db, standard_id)
                if not standard:
                    raise IndustryStandardError(f"标准ID {standard_id} 不存在")
                return self._format_standard(standard, include_metadata=True)
        except DatabaseError as e:
            logger.error(f"获取标准详情时出错: {str(e)}")
            raise IndustryStandardError(f"无法获取标准详情: {str(e)}")
    
    def get_standard_by_code(self, standard_code: str) -> Dict[str, Any]:
        """
        根据标准代码获取标准。
        
        Args:
            standard_code: 标准代码
            
        Returns:
            标准详情
            
        Raises:
            IndustryStandardError: 查询失败时
        """
        try:
            with get_db() as db:
                standard = industry_standard_service.get_by_code(db, standard_code)
                if not standard:
                    raise IndustryStandardError(f"标准代码 {standard_code} 不存在")
                return self._format_standard(standard, include_metadata=True)
        except DatabaseError as e:
            logger.error(f"按代码获取标准时出错: {str(e)}")
            raise IndustryStandardError(f"无法按代码获取标准: {str(e)}")
    
    def search_standards(self, keywords: str, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """
        按关键词搜索标准。
        
        Args:
            keywords: 搜索关键词
            skip: 跳过的记录数
            limit: 返回的最大记录数
            
        Returns:
            标准列表
            
        Raises:
            IndustryStandardError: 搜索失败时
        """
        try:
            with get_db() as db:
                standards = industry_standard_service.search(db, keywords, skip, limit)
                return [self._format_standard(std) for std in standards]
        except DatabaseError as e:
            logger.error(f"搜索行业标准时出错: {str(e)}")
            raise IndustryStandardError(f"无法搜索行业标准: {str(e)}")
    
    def add_standard(self, standard_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        添加新标准。
        
        Args:
            standard_data: 标准数据
            
        Returns:
            添加的标准详情
            
        Raises:
            IndustryStandardError: 添加失败时
        """
        try:
            with get_db() as db:
                # 检查必填字段
                required_fields = [
                    "standard_name", "standard_code", "industry_type",
                    "issuing_authority", "regions", "categories"
                ]
                for field in required_fields:
                    if field not in standard_data:
                        raise IndustryStandardError(f"缺少必填字段: {field}")
                
                # 添加新标准
                new_standard = industry_standard_service.create(db, obj_in=standard_data)
                return self._format_standard(new_standard, include_metadata=True)
        except DatabaseError as e:
            logger.error(f"添加行业标准时出错: {str(e)}")
            raise IndustryStandardError(f"无法添加行业标准: {str(e)}")
    
    def update_standard(self, standard_id: str, standard_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新标准信息。
        
        Args:
            standard_id: 标准ID
            standard_data: 更新的标准数据
            
        Returns:
            更新后的标准详情
            
        Raises:
            IndustryStandardError: 更新失败时
        """
        try:
            with get_db() as db:
                # 获取现有标准
                standard = industry_standard_service.get(db, standard_id)
                if not standard:
                    raise IndustryStandardError(f"标准ID {standard_id} 不存在")
                
                # 更新标准
                updated_standard = industry_standard_service.update(
                    db, db_obj=standard, obj_in=standard_data
                )
                return self._format_standard(updated_standard, include_metadata=True)
        except DatabaseError as e:
            logger.error(f"更新行业标准时出错: {str(e)}")
            raise IndustryStandardError(f"无法更新行业标准: {str(e)}")
    
    def initialize_photovoltaic_standards(self) -> List[str]:
        """
        初始化光伏行业标准数据。
        
        Returns:
            添加的标准ID列表
            
        Raises:
            IndustryStandardError: 初始化失败时
        """
        try:
            with get_db() as db:
                added_ids = industry_standard_service.initialize_photovoltaic_standards(db)
                logger.info(f"已初始化 {len(added_ids)} 个光伏行业标准")
                return added_ids
        except DatabaseError as e:
            logger.error(f"初始化光伏标准时出错: {str(e)}")
            raise IndustryStandardError(f"无法初始化光伏标准: {str(e)}")
    
    async def monitor_standard_updates(self) -> List[Dict[str, Any]]:
        """
        监控标准更新情况。
        
        使用网页爬虫服务检查标准发布机构的最新更新。
        
        Returns:
            更新信息列表
            
        Raises:
            IndustryStandardError: 监控失败时
        """
        if not self.web_crawler_service:
            logger.warning("未配置WebCrawlerService，无法监控标准更新")
            return []
        
        try:
            with get_db() as db:
                # 获取需要监控的标准机构
                authorities_query = db.query(IndustryStandard.issuing_authority).distinct()
                authorities = [row[0] for row in authorities_query]
                
                updates = []
                
                # 检查每个机构的更新
                for authority in authorities:
                    try:
                        # 搜索并爬取该机构的最新标准信息
                        search_query = f"{authority} 最新标准 更新"
                        authority_updates = await self.web_crawler_service.search_and_crawl(search_query, limit=2)
                        
                        # 处理获取的更新信息
                        for update in authority_updates:
                            updates.append({
                                "authority": authority,
                                "title": update.get("title", ""),
                                "url": update.get("url", ""),
                                "summary": update.get("snippet", ""),
                                "content": update.get("content", "")[:500] + "..." if update.get("content") else "",
                                "timestamp": update.get("timestamp", datetime.now().isoformat())
                            })
                    except Exception as e:
                        logger.warning(f"监控标准机构 {authority} 更新时出错: {str(e)}")
                
                return updates
        except Exception as e:
            logger.error(f"监控标准更新时出错: {str(e)}")
            raise IndustryStandardError(f"无法监控标准更新: {str(e)}")
    
    def _format_standard(self, standard: IndustryStandard, include_metadata: bool = False) -> Dict[str, Any]:
        """
        格式化标准信息为API响应格式。
        
        Args:
            standard: 标准对象
            include_metadata: 是否包含元数据
            
        Returns:
            格式化的标准信息
        """
        # 基本信息
        result = {
            "id": standard.id,
            "standard_name": standard.standard_name,
            "standard_code": standard.standard_code,
            "industry_type": standard.industry_type,
            "description": standard.description,
            "issuing_authority": standard.issuing_authority,
            "regions": standard.regions,
            "categories": standard.categories,
        }
        
        # 日期字段需要格式化
        if standard.effective_date:
            result["effective_date"] = standard.effective_date.isoformat()
        if standard.expiration_date:
            result["expiration_date"] = standard.expiration_date.isoformat()
        
        # 可选包含元数据
        if include_metadata and standard.metadata:
            result["metadata"] = standard.metadata
        
        return result 