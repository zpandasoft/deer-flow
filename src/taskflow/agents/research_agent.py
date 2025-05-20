# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
研究智能体模块。

负责执行信息收集和研究任务，查询和分析外部资源。
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

from langchain.schema import HumanMessage, SystemMessage, AIMessage
from langchain.schema.runnable import Runnable

from src.taskflow.agents.base import LLMAgent
from src.taskflow.exceptions import AgentError
from src.taskflow.utils.logger import log_execution_time

# 获取日志记录器
logger = logging.getLogger(__name__)


class ResearchAgent(LLMAgent[Dict[str, Any], Dict[str, Any]]):
    """
    研究智能体。
    
    执行信息收集和研究任务，查询和分析外部资源。
    """
    
    def __init__(
        self,
        llm: Runnable,
        name: str = "research_agent",
        description: str = "执行信息收集和研究任务，查询和分析外部资源",
        metadata: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        search_tool: Optional[Any] = None,
        document_tool: Optional[Any] = None
    ) -> None:
        """
        初始化研究智能体。
        
        Args:
            llm: LLM可运行实例
            name: 智能体名称
            description: 智能体描述
            metadata: 智能体元数据
            system_prompt: 系统提示词，如果为None则使用默认提示词
            search_tool: 搜索工具实例
            document_tool: 文档处理工具实例
        """
        # 如果未提供系统提示词，使用默认提示词
        if system_prompt is None:
            system_prompt = self._get_default_system_prompt()
        
        super().__init__(name, llm, description, metadata, system_prompt)
        
        # 保存工具
        self.search_tool = search_tool
        self.document_tool = document_tool
        
        # 研究状态
        self.search_history: List[Dict[str, Any]] = []
        self.collected_information: List[Dict[str, Any]] = []
    
    def _get_default_system_prompt(self) -> str:
        """
        获取默认系统提示词。
        
        注意：此方法仅作为备用，通常应通过get_agent_by_name函数获取智能体实例，
        该函数会自动从/src/prompts/目录加载提示词。
        
        Returns:
            默认系统提示词
        """
        # 尝试从/src/prompts/目录加载
        try:
            from src.taskflow.prompts import load_prompt_from_file
            
            prompt_paths = [
                "src/prompts/research_agent.md",
                "src/prompts/researcher.md",
                "src/prompts/researcher.zh-CN.md"
            ]
            
            for path in prompt_paths:
                prompt = load_prompt_from_file(path)
                if prompt:
                    logger.info(f"已从{path}加载提示词")
                    return prompt
        except Exception as e:
            logger.warning(f"无法从文件加载提示词: {str(e)}")
        
        # 如果无法从文件加载，使用内置提示词
        logger.warning("使用内置的默认研究智能体提示词")
        return """
        你是一个专业的研究智能体，负责执行信息收集和研究任务。

        你的主要任务是：
        1. 理解研究目标和问题
        2. 设计有效的搜索策略
        3. 收集和整理相关信息
        4. 评估信息的可靠性和相关性
        5. 生成结构化的研究报告
        
        在研究过程中，你可以：
        - 使用搜索工具查询相关信息
        - 使用文档处理工具分析文档内容
        - 组织和整理收集到的信息
        - 识别需要进一步调查的领域
        
        请根据提供的研究任务，首先制定研究计划，然后执行信息收集和分析，最后生成结构化研究报告。
        所有输出应为JSON格式，确保包含所有关键信息和来源引用。
        """
    
    @log_execution_time(logger)
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        运行研究智能体。
        
        Args:
            input_data: 输入数据，必须包含"research_task"字段
            
        Returns:
            研究结果
            
        Raises:
            AgentError: 如果研究任务执行失败
        """
        # 验证输入
        if "research_task" not in input_data:
            error_msg = "输入数据必须包含'research_task'字段"
            logger.error(error_msg)
            raise AgentError(error_msg)
        
        research_task = input_data["research_task"]
        context = input_data.get("context", {})
        
        # 重置状态
        self.search_history = []
        self.collected_information = []
        
        # 获取任务参数
        task_title = research_task.get("title", "研究任务")
        task_description = research_task.get("description", "")
        
        logger.info(f"开始执行研究任务: {task_title}")
        
        try:
            # 1. 制定研究计划
            logger.info("制定研究计划...")
            research_plan = await self._create_research_plan(task_description, context)
            
            # 2. 执行研究
            logger.info("执行信息收集...")
            collected_info = await self._collect_information(task_description, research_plan, context)
            
            # 3. 分析和整理信息
            logger.info("分析和整理信息...")
            organized_info = await self._organize_information(collected_info, research_plan)
            
            # 4. 生成最终报告
            logger.info("生成研究报告...")
            research_report = await self._generate_report(task_description, research_plan, organized_info)
            
            # 5. 构建完整结果
            result = {
                "task_title": task_title,
                "research_plan": research_plan,
                "collected_information": self.collected_information,
                "search_history": self.search_history,
                "research_report": research_report
            }
            
            return result
        except Exception as e:
            error_msg = f"执行研究任务时出错: {str(e)}"
            logger.exception(error_msg)
            raise AgentError(error_msg) from e
    
    async def _create_research_plan(
        self,
        task_description: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        创建研究计划。
        
        Args:
            task_description: 任务描述
            context: 上下文信息
            
        Returns:
            研究计划
        """
        messages = [
            SystemMessage(content="""
            作为研究规划专家，你需要为给定的研究任务创建详细的研究计划。
            
            请输出JSON格式的研究计划，包含以下字段：
            - research_questions: 需要回答的关键问题列表
            - search_queries: 建议的搜索查询列表
            - information_needs: 需要收集的信息类型
            - sources_to_check: 建议查询的信息源
            - expected_challenges: 可能面临的挑战
            - success_criteria: 研究成功的标准
            
            确保你的计划全面且针对性强，能够有效指导后续的研究工作。
            """),
            HumanMessage(content=f"""请为以下研究任务创建详细的研究计划：

任务描述：
{task_description}

上下文信息：
{json.dumps(context, ensure_ascii=False, indent=2) if context else "无上下文信息"}
""")
        ]
        
        response = await self._call_llm(messages)
        return self._parse_json_response(response)
    
    async def _collect_information(
        self,
        task_description: str,
        research_plan: Dict[str, Any],
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        收集信息。
        
        Args:
            task_description: 任务描述
            research_plan: 研究计划
            context: 上下文信息
            
        Returns:
            收集到的信息列表
        """
        collected_info = []
        search_queries = research_plan.get("search_queries", [])
        
        if not search_queries:
            # 如果没有搜索查询，生成一些基于任务描述的查询
            messages = [
                SystemMessage(content="根据任务描述生成5个有效的搜索查询，输出为JSON格式的查询列表。"),
                HumanMessage(content=f"任务描述: {task_description}")
            ]
            response = await self._call_llm(messages)
            generated_queries = self._parse_json_response(response)
            
            if isinstance(generated_queries, list):
                search_queries = generated_queries
            elif isinstance(generated_queries, dict) and "queries" in generated_queries:
                search_queries = generated_queries["queries"]
            else:
                search_queries = [task_description]
        
        # 执行搜索查询
        for query in search_queries[:5]:  # 限制最多5个查询
            if isinstance(query, dict) and "query" in query:
                query = query["query"]
                
            # 记录查询
            self.search_history.append({"query": query, "timestamp": self._get_timestamp()})
            
            # 执行搜索
            search_results = await self._perform_search(query)
            collected_info.extend(search_results)
            
            # 更新收集的信息
            for result in search_results:
                if result not in self.collected_information:
                    self.collected_information.append(result)
        
        return collected_info
    
    async def _perform_search(self, query: str) -> List[Dict[str, Any]]:
        """
        执行搜索。
        
        Args:
            query: 搜索查询
            
        Returns:
            搜索结果列表
        """
        results = []
        
        # 使用搜索工具（如果可用）
        if self.search_tool:
            try:
                logger.info(f"使用搜索工具查询: {query}")
                search_results = await self.search_tool(query)
                
                if search_results:
                    for result in search_results:
                        if isinstance(result, dict):
                            results.append({
                                "source": "search_tool",
                                "query": query,
                                "content": result.get("content", ""),
                                "url": result.get("url", ""),
                                "title": result.get("title", ""),
                                "timestamp": self._get_timestamp()
                            })
            except Exception as e:
                logger.error(f"搜索工具调用失败: {str(e)}")
        
        # 如果没有搜索工具或搜索失败，使用LLM生成模拟搜索结果
        if not results:
            logger.info("使用LLM生成模拟搜索结果")
            results = await self._generate_mock_search_results(query)
        
        return results
    
    async def _generate_mock_search_results(self, query: str) -> List[Dict[str, Any]]:
        """
        生成模拟搜索结果。
        
        Args:
            query: 搜索查询
            
        Returns:
            模拟搜索结果列表
        """
        messages = [
            SystemMessage(content="""
            模拟一个搜索引擎的结果。基于给定的查询，生成3-5个相关、真实且有用的搜索结果。
            
            每个结果应包含以下字段：
            - title: 结果标题
            - content: 内容摘要（至少100字）
            - url: 模拟的URL
            - source_type: 来源类型（如"网页"、"学术论文"、"新闻"等）
            
            结果应当多样化并具有实质性内容，不应包含虚假或误导信息。
            输出为JSON格式的结果列表。
            """),
            HumanMessage(content=f"搜索查询: {query}")
        ]
        
        response = await self._call_llm(messages)
        mock_results = self._parse_json_response(response)
        
        if not isinstance(mock_results, list):
            if isinstance(mock_results, dict) and "results" in mock_results:
                mock_results = mock_results["results"]
            else:
                mock_results = []
        
        # 格式化结果
        formatted_results = []
        for result in mock_results:
            formatted_results.append({
                "source": "mock_search",
                "query": query,
                "content": result.get("content", ""),
                "url": result.get("url", ""),
                "title": result.get("title", ""),
                "source_type": result.get("source_type", "网页"),
                "timestamp": self._get_timestamp()
            })
        
        return formatted_results
    
    async def _organize_information(
        self,
        collected_info: List[Dict[str, Any]],
        research_plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        组织收集到的信息。
        
        Args:
            collected_info: 收集到的信息
            research_plan: 研究计划
            
        Returns:
            组织后的信息
        """
        # 如果没有收集到信息，返回空结果
        if not collected_info:
            return {
                "topics": [],
                "insights": [],
                "gaps": []
            }
        
        # 准备输入
        info_summary = []
        for i, info in enumerate(collected_info[:10]):  # 限制最多10个条目
            info_summary.append({
                "id": i + 1,
                "title": info.get("title", "未知标题"),
                "content": info.get("content", "")[:500],  # 限制长度
                "source": info.get("source", "未知来源"),
                "url": info.get("url", "")
            })
        
        messages = [
            SystemMessage(content="""
            作为信息组织专家，你需要分析和组织收集到的研究信息。
            
            请输出JSON格式的组织结果，包含以下字段：
            - topics: 主要主题列表，每个主题包含名称、描述和相关信息ID
            - insights: 关键见解列表，每个见解包含描述和支持的信息ID
            - gaps: 信息缺口列表，指出还需要进一步调查的领域
            - reliability_assessment: 对收集的信息可靠性的评估
            - relevance_assessment: 对收集的信息与研究问题相关性的评估
            
            确保你的分析全面且有深度，能够帮助理解收集到的信息。
            """),
            HumanMessage(content=f"""请组织以下收集到的研究信息：

研究计划：
{json.dumps(research_plan, ensure_ascii=False, indent=2)}

收集到的信息：
{json.dumps(info_summary, ensure_ascii=False, indent=2)}
""")
        ]
        
        response = await self._call_llm(messages)
        return self._parse_json_response(response)
    
    async def _generate_report(
        self,
        task_description: str,
        research_plan: Dict[str, Any],
        organized_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        生成研究报告。
        
        Args:
            task_description: 任务描述
            research_plan: 研究计划
            organized_info: 组织后的信息
            
        Returns:
            研究报告
        """
        messages = [
            SystemMessage(content="""
            作为研究报告专家，你需要基于收集和组织的信息生成详细的研究报告。
            
            请输出JSON格式的研究报告，包含以下字段：
            - title: 报告标题
            - summary: 研究摘要（200-300字）
            - key_findings: 关键发现列表，每项包含标题和详细描述
            - analysis: 详细分析，包含多个部分
            - conclusions: 结论
            - recommendations: 建议列表
            - references: 参考资料列表，包含标题、url和简短描述
            
            确保你的报告专业、全面、有见地，并且所有结论都基于收集到的信息。
            """),
            HumanMessage(content=f"""请基于以下信息生成研究报告：

任务描述：
{task_description}

研究计划：
{json.dumps(research_plan, ensure_ascii=False, indent=2)}

组织后的信息：
{json.dumps(organized_info, ensure_ascii=False, indent=2)}
""")
        ]
        
        response = await self._call_llm(messages)
        return self._parse_json_response(response)
    
    def _parse_json_response(self, response: str) -> Union[Dict[str, Any], List[Any]]:
        """
        解析JSON响应。
        
        Args:
            response: LLM响应文本
            
        Returns:
            解析后的JSON对象
            
        Raises:
            AgentError: 如果无法解析响应
        """
        try:
            # 尝试直接解析JSON
            return json.loads(response)
        except json.JSONDecodeError:
            # 如果直接解析失败，尝试从文本中提取JSON
            try:
                # 寻找JSON对象的开始和结束
                start_idx = response.find('{')
                end_idx = response.rfind('}') + 1
                
                # 检查是否找到了JSON对象
                if start_idx >= 0 and end_idx > start_idx:
                    json_str = response[start_idx:end_idx]
                    return json.loads(json_str)
                
                # 检查是否是JSON数组
                start_idx = response.find('[')
                end_idx = response.rfind(']') + 1
                
                if start_idx >= 0 and end_idx > start_idx:
                    json_str = response[start_idx:end_idx]
                    return json.loads(json_str)
                
                # 如果既不是对象也不是数组，则无法解析
                raise AgentError("无法从响应中提取JSON")
            except Exception as e:
                error_msg = f"解析响应失败: {str(e)}\n原始响应: {response}"
                logger.error(error_msg)
                raise AgentError(error_msg) from e
    
    def _get_timestamp(self) -> str:
        """
        获取当前时间戳。
        
        Returns:
            格式化的时间戳
        """
        from datetime import datetime
        return datetime.now().isoformat()
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        获取智能体可用工具列表。
        
        Returns:
            工具列表
        """
        tools = []
        
        # 搜索工具
        if self.search_tool:
            tools.append({
                "name": "search",
                "description": "搜索网络获取信息",
                "available": True
            })
        
        # 文档处理工具
        if self.document_tool:
            tools.append({
                "name": "document_processor",
                "description": "处理和分析文档内容",
                "available": True
            })
        
        return tools
    
    async def analyze_document(self, document_url: str, research_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析文档内容。
        
        Args:
            document_url: 文档URL
            research_context: 研究上下文
            
        Returns:
            分析结果
            
        Raises:
            AgentError: 如果文档分析失败
        """
        # 检查URL
        try:
            parsed_url = urlparse(document_url)
            if not all([parsed_url.scheme, parsed_url.netloc]):
                raise ValueError("无效的URL")
        except Exception as e:
            raise AgentError(f"URL格式无效: {str(e)}")
        
        # 如果有文档处理工具，使用工具处理
        if self.document_tool:
            try:
                logger.info(f"使用文档工具分析URL: {document_url}")
                document_content = await self.document_tool(document_url)
                
                # 记录到收集的信息中
                self.collected_information.append({
                    "source": "document_tool",
                    "url": document_url,
                    "content": document_content.get("content", ""),
                    "title": document_content.get("title", ""),
                    "timestamp": self._get_timestamp()
                })
                
                return document_content
            except Exception as e:
                logger.error(f"文档工具调用失败: {str(e)}")
        
        # 如果没有文档工具或处理失败，使用LLM生成模拟分析
        logger.info("使用LLM生成模拟文档分析")
        return await self._generate_mock_document_analysis(document_url, research_context)
    
    async def _generate_mock_document_analysis(
        self,
        document_url: str,
        research_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        生成模拟文档分析。
        
        Args:
            document_url: 文档URL
            research_context: 研究上下文
            
        Returns:
            模拟分析结果
        """
        messages = [
            SystemMessage(content="""
            模拟文档分析结果。基于给定的URL和研究上下文，生成一个合理的文档分析结果。
            
            分析结果应包含以下字段：
            - title: 文档标题
            - content_summary: 内容摘要（至少200字）
            - key_points: 关键点列表
            - relevance: 与研究上下文的相关性评分（1-10）
            - insights: 从文档中提取的见解列表
            
            分析应当专业、有见地，并与URL表示的文档类型相符。
            输出为JSON格式。
            """),
            HumanMessage(content=f"""请分析以下文档：

文档URL: {document_url}

研究上下文:
{json.dumps(research_context, ensure_ascii=False, indent=2)}
""")
        ]
        
        response = await self._call_llm(messages)
        mock_analysis = self._parse_json_response(response)
        
        # 添加元数据
        mock_analysis["url"] = document_url
        mock_analysis["source"] = "mock_document_analysis"
        mock_analysis["timestamp"] = self._get_timestamp()
        
        # 记录到收集的信息中
        self.collected_information.append({
            "source": "mock_document_analysis",
            "url": document_url,
            "content": mock_analysis.get("content_summary", ""),
            "title": mock_analysis.get("title", ""),
            "timestamp": self._get_timestamp()
        })
        
        return mock_analysis