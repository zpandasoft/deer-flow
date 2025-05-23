


-- 创建上下文分析结果表
CREATE TABLE IF NOT EXISTS `context_analysis` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键',
  `msg_id` varchar(100) NOT NULL COMMENT '',
  `content` varchar(100) NOT NULL COMMENT '',
  `llm_response` text NOT NULL COMMENT 'LLM响应内容',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_objective_id` (`objective_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建目标分解表
CREATE TABLE IF NOT EXISTS `objectives` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键',
  `objective_id` varchar(100) NOT NULL COMMENT '目标ID',
  `title` varchar(255) NOT NULL COMMENT '目标标题',
  `description` text NOT NULL COMMENT '目标描述', 
  `justification` text NOT NULL COMMENT '目标理由',
  `evaluation_criteria` text NOT NULL COMMENT '目标评估标准',
  `status` varchar(50) NOT NULL DEFAULT 'CREATED' COMMENT '目标状态',
  `parent_id` varchar(100) DEFAULT NULL COMMENT '父目标ID',
  `retry_count` int(11) NOT NULL DEFAULT 0 COMMENT '重试次数',
  `max_retries` int(11) NOT NULL DEFAULT 3 COMMENT '最大重试次数',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `completed_at` datetime DEFAULT NULL COMMENT '完成时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_objective_id` (`objective_id`),
  KEY `idx_parent_id` (`parent_id`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建任务分析表
CREATE TABLE IF NOT EXISTS `tasks` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键',
  `task_id` varchar(100) NOT NULL COMMENT '任务ID',
  `objective_id` varchar(100) NOT NULL COMMENT '目标ID',
  `title` varchar(255) NOT NULL COMMENT '任务标题',
  `description` text NOT NULL COMMENT '任务描述',
  `status` varchar(50) DEFAULT 'PENDING' COMMENT '任务状态',
  `priority` int(11) NOT NULL DEFAULT 0 COMMENT '优先级',
  `is_sufficient` tinyint(1) NOT NULL DEFAULT 0 COMMENT '是否充分',
  `evaluation_criteria` text DEFAULT NULL COMMENT '评估标准',
  `retry_count` int(11) NOT NULL DEFAULT 0 COMMENT '重试次数',
  `max_retries` int(11) NOT NULL DEFAULT 3 COMMENT '最大重试次数',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `completed_at` datetime DEFAULT NULL COMMENT '完成时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_task_id` (`task_id`),
  KEY `idx_objective_id` (`objective_id`),
  KEY `idx_status` (`status`),
  CONSTRAINT `fk_tasks_objective` FOREIGN KEY (`objective_id`) REFERENCES `objectives` (`objective_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建任务步骤表
CREATE TABLE IF NOT EXISTS `steps` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键',
  `step_id` varchar(100) NOT NULL COMMENT '步骤ID',
  `task_id` varchar(100) NOT NULL COMMENT '任务ID',
  `title` varchar(255) NOT NULL COMMENT '步骤标题',
  `description` text NOT NULL COMMENT '步骤描述',
  `status` varchar(50) DEFAULT 'PENDING' COMMENT '步骤状态',
  `priority` int(11) NOT NULL DEFAULT 0 COMMENT '优先级',
  `is_sufficient` tinyint(1) NOT NULL DEFAULT 0 COMMENT '是否充分',
  `evaluation_criteria` text DEFAULT NULL COMMENT '评估标准',
  `retry_count` int(11) NOT NULL DEFAULT 0 COMMENT '重试次数',
  `max_retries` int(11) NOT NULL DEFAULT 3 COMMENT '最大重试次数',
  `timeout_seconds` int(11) NOT NULL DEFAULT 300 COMMENT '超时时间(秒)',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `completed_at` datetime DEFAULT NULL COMMENT '完成时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_step_id` (`step_id`),
  KEY `idx_task_id` (`task_id`),
  KEY `idx_status` (`status`),
  CONSTRAINT `fk_steps_task` FOREIGN KEY (`task_id`) REFERENCES `tasks` (`task_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建研究结果表
CREATE TABLE IF NOT EXISTS `research_results` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键',
  `task_id` varchar(100) NOT NULL COMMENT '任务ID',
  `llm_response` text NOT NULL COMMENT 'LLM响应内容',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_task_id` (`task_id`),
  CONSTRAINT `fk_research_task` FOREIGN KEY (`task_id`) REFERENCES `tasks` (`task_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建处理结果表
CREATE TABLE IF NOT EXISTS `processing_results` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键',
  `category` varchar(100) NOT NULL COMMENT '类别',
  `llm_response` text NOT NULL COMMENT 'LLM响应内容',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_category` (`category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建质量评估表
CREATE TABLE IF NOT EXISTS `quality_evaluations` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键',
  `task_id` varchar(100) NOT NULL COMMENT '任务ID',
  `llm_response` text NOT NULL COMMENT 'LLM响应内容',
  `quality_passed` tinyint(1) NOT NULL COMMENT '质量是否通过',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_task_id` (`task_id`),
  CONSTRAINT `fk_quality_task` FOREIGN KEY (`task_id`) REFERENCES `tasks` (`task_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建合成结果表
CREATE TABLE IF NOT EXISTS `synthesis_results` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键',
  `llm_response` text NOT NULL COMMENT 'LLM响应内容',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建错误日志表
CREATE TABLE IF NOT EXISTS `error_logs` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键',
  `log_id` varchar(255) NOT NULL COMMENT '日志ID',
  `error_type` varchar(100) NOT NULL COMMENT '错误类型',
  `error_message` text NOT NULL COMMENT '错误信息',
  `error_source` varchar(255) NOT NULL COMMENT '错误来源',
  `traceback` text DEFAULT NULL COMMENT '错误追踪',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_log_id` (`log_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建智能体调用记录表
CREATE TABLE IF NOT EXISTS `agent_llm_calls` (
  `call_id` varchar(36) NOT NULL COMMENT '调用ID',
  `agent_name` varchar(100) NOT NULL COMMENT '智能体名称',
  `node_name` varchar(100) NOT NULL COMMENT '节点名称',
  `reference_id` varchar(36) DEFAULT NULL COMMENT '引用ID',
  `reference_type` varchar(20) DEFAULT NULL COMMENT '引用类型',
  `input_data` longtext NOT NULL COMMENT '输入数据',
  `output_data` longtext NOT NULL COMMENT '输出数据',
  `tokens_used` int(11) DEFAULT NULL COMMENT '使用的token数量',
  `duration_ms` int(11) DEFAULT NULL COMMENT '持续时间(毫秒)',
  `status` varchar(20) NOT NULL COMMENT '状态',
  `error_message` text DEFAULT NULL COMMENT '错误信息',
  `model_name` varchar(100) DEFAULT NULL COMMENT '模型名称',
  `metadata` json DEFAULT NULL COMMENT '元数据',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`call_id`),
  KEY `idx_agent_name` (`agent_name`),
  KEY `idx_reference_id` (`reference_id`),
  KEY `idx_status` (`status`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;