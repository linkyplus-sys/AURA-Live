# AURA-Live：单用户本地陪伴系统开发技术文档 (v1.1)
- 更新时间：2026-04-10
- 文档状态：已按当前仓库实现重写并对齐
- 适用版本：当前工作区代码
- 项目属性：单用户、本地部署、NAS 常驻优先

---

## 1. 项目定位

AURA-Live 当前不是一个泛化的“多用户聊天平台”，而是一个面向单用户、本地或 NAS 部署的陪伴式角色聊天系统。

当前实现采用 `FastAPI + 原生 HTML/CSS/JS + Ollama / OpenAI-compatible 接口 + ChromaDB` 架构，目标是提供：

- 单用户长期陪伴
- 角色人格与世界书可编辑
- 长期记忆与会话记忆并存
- 最近状态连续承接
- 删除 / 回滚后记忆可同步修正
- 适合本地电脑或 NAS 常驻运行

当前明确不以这些目标为优先：

- 多用户账号体系
- SaaS 化权限与租户隔离
- 高并发公网服务
- 部署路径和数据卷的强可移植抽象

---

## 2. 当前已实现能力

### 2.1 聊天页 `/`

聊天页是主入口，当前已经实现：

- SSE 流式聊天
- `Enter` 发送，`Shift + Enter` 换行
- 用户输入支持“动作 + 台词”混合表达
- 动作括号统一规范为中文全角 `（）`
- 助手动作自动规范为第三人称视角
- 每条助手消息可删除整轮对话
- 最新一条助手消息可重新生成
- 顶部展示运行状态、记忆数量、当前模型
- 悬浮外观入口，可快速切换背景 URL 或预设背景
- 3:4 比例悬浮立绘，整张立绘可直接拖动
- 立绘已去除边框、底部文字和拖拽把手，改为更强存在感的呼吸式展示
- 用户消息气泡已改为一体化非对称圆角轮廓，避免主块和尾巴割裂
- 背景与立绘偏移量保存在浏览器本地存储

### 2.2 设置页 `/settings`

设置页当前负责：

- 人格配置
  - 名称
  - 性格 / 人格描述
  - 表达风格
  - 当前环境与背景
  - 立绘文件名
  - 立绘上传
- 世界书配置
  - 新增 / 删除条目
  - 标题
  - 关键词
  - 内容
  - 是否总是加载
- 运行时配置
  - Provider 切换
  - 服务地址
  - API Key
  - 对话模型
  - 嵌入模型
  - 可用模型读取
  - 当前运行状态展示
- 维护操作
  - 清空历史
  - 清空记忆
  - 跳转记忆页

### 2.3 记忆页 `/memories`

记忆页当前已经实现：

- 记忆列表查看
- `persistent / session` 范围筛选
- 分类筛选
- 摘要 / key / 原话搜索
- 筛选条件持久化到浏览器 `localStorage`
- 单条记忆删除
- 刷新列表

页面展示字段包括：

- 范围 `scope`
- 分类 `category`
- 分数 `score`
- 更新时间
- 摘要 `summary`
- 记忆键 `key`
- 用户关键信息 `user_memory`
- 助手上下文 `bot_memory`
- 用户原话 `user_text`
- 助手原话 `bot_text`

### 2.4 后端能力

后端当前已经实现：

- 聊天历史保存
- 世界书按关键词触发
- 长期记忆与会话记忆召回
- 角色连续性提示词构建
- 最近重复动作 / 特征的保守抑制
- 最新回复重新生成
- 整轮删除与记忆引用回滚
- 单条记忆删除
- 本地 Ollama 与在线兼容接口切换

---

## 3. 技术栈

- 后端：`FastAPI`
- 前端：`HTML + CSS + JavaScript`
- 大模型接口：`Ollama`、`OpenAI-compatible HTTP API`
- 向量数据库：`ChromaDB`
- 运行语言：`Python 3.10+`
- 服务启动：`uvicorn`
- 容器部署：`Docker / Docker Compose`

---

## 4. 当前架构

```text
Browser
  ├─ /
  ├─ /settings
  ├─ /memories
  ├─ /static/*
  └─ /avatars/*

FastAPI (app.py)
  ├─ 页面路由
  ├─ bootstrap / health / history / memory API
  ├─ 角色、世界书、运行时配置 API
  ├─ 流式聊天与重新生成 API
  └─ 头像上传 API

ChatService (services/chat_service.py)
  ├─ 读取 soul / worldbook / runtime / history
  ├─ 规范化输入动作括号
  ├─ 构建系统提示词
  ├─ 注入世界书与记忆
  ├─ 生成连续性约束
  ├─ 调用 LLMClient
  ├─ 规范化助手动作第三人称
  ├─ 抑制最近重复动作标记
  ├─ 写入历史
  ├─ 写入记忆
  ├─ 删除整轮对话
  └─ 重新生成失败时恢复原轮次

Parser (utils/parser.py)
  ├─ 统一中英文括号
  ├─ 提取动作段
  ├─ 拆分动作与台词
  ├─ 格式化用户输入
  └─ 规范化动作视角

LLMClient (models/llm.py)
  ├─ Provider 统一封装
  ├─ 模型列表读取
  ├─ 流式聊天
  └─ 文本向量化

MemoryManager (models/memory.py)
  ├─ LLM 提取 + 规则兜底
  ├─ persistent / session 分类
  ├─ 记忆压缩、合并、覆盖
  ├─ turn_id 引用管理
  ├─ 召回与新鲜度控制
  └─ 记忆删除与回滚
```

---

## 5. 当前目录结构

```text
/ai_pet/
├─ app.py
├─ config.py
├─ Dockerfile
├─ docker-compose.yml
├─ requirements.txt
├─ soul.json
├─ worldbook.json
├─ history.json
├─ memory.json
├─ runtime.json
├─ avatars/
├─ chroma_db/
├─ models/
│  ├─ __init__.py
│  ├─ llm.py
│  └─ memory.py
├─ services/
│  ├─ __init__.py
│  └─ chat_service.py
├─ utils/
│  ├─ __init__.py
│  ├─ exceptions.py
│  ├─ file_ops.py
│  ├─ parser.py
│  └─ validators.py
├─ static/
│  ├─ index.html
│  ├─ app.js
│  ├─ chat.css
│  ├─ settings.html
│  ├─ settings.js
│  ├─ memories.html
│  ├─ memories.js
│  └─ styles.css
└─ tests/
   └─ test_chat_service_turn_management.py
```

---

## 6. 核心数据文件

### 6.1 `soul.json`

角色配置文件，当前字段如下：

```json
{
  "name": "AURA",
  "personality": "温柔、清醒，带一点陪伴感的数字宠物。",
  "style": "如果需要动作或环境描写，请写在括号()里。",
  "scene": "",
  "pet_image": "bot.png"
}
```

说明：

- `pet_image` 是当前实现中的遗留字段名
- 当前语义按“角色立绘文件名”解释
- `load_soul()` 没有做进程内缓存，聊天和设置读取时都会直接从 `soul.json` 载入
- 因此在 NAS 后台直接整份替换 `soul.json` 可以快速切换角色设定，通常不需要重启服务
- 但如果设置页已经打开并再次保存，会以当前表单内容覆盖文件，因此手工替换后应避免用旧页面状态再次提交
- 手工替换时需要保持字段结构完整，至少应包含 `name` 和 `personality`

### 6.2 `worldbook.json`

当前推荐保存为 `entries` 数组：

```json
{
  "entries": [
    {
      "title": "身份设定",
      "keywords": ["身份", "设定"],
      "content": "AURA 是一个运行在本地环境中的 AI 宠物助手。",
      "always": false
    }
  ]
}
```

说明：

- 命中 `keywords` 时注入
- `always: true` 的条目每轮注入
- 代码仍兼容旧的字典映射格式，但设置页保存为 `entries` 结构
- 后端当前也兼容“根节点直接是数组”的世界书文件，保存时会统一标准化成 `{"entries":[...]}` 结构
- `load_worldbook()` 没有做进程内缓存，聊天和设置读取时都会直接从 `worldbook.json` 载入
- 因此在 NAS 后台直接整份替换 `worldbook.json` 可以达到快速批量增条目的效果，通常不需要重启服务
- 但如果设置页已经打开并再次保存，会以当前表单内容覆盖文件，因此手工替换后应避免用旧页面状态再次提交

### 6.3 `history.json`

保存完整对话历史，当前每条消息是：

```json
{
  "role": "assistant",
  "content": "（AURA坐在窗边）那就继续聊吧。",
  "turn_id": "turn-3-abcd1234",
  "turn_index": 3
}
```

说明：

- `content` 保存归一化后的文本
- 动作括号统一成中文全角 `（）`
- `turn_id` 用于记忆回滚与整轮删除
- `turn_index` 用于会话状态和新鲜度判断

### 6.4 `memory.json`

这是基础配置文件，不是记忆正文：

```json
{
  "enabled": true,
  "save_latest_turn": true,
  "recall_count": 3
}
```

### 6.5 `runtime.json`

运行时模型配置文件：

```json
{
  "provider": "ollama",
  "base_url": "http://192.168.50.51:11434",
  "api_key": "",
  "current_model": "Gemma4:e4b",
  "embed_model": "bge-m3"
}
```

说明：

- 设置页只会对已保存 Key 做掩码展示
- `runtime.json` 中保存的是原始值，当前实现默认接受这种单用户本地存储方式

### 6.6 `chroma_db/`

真实记忆数据的持久化目录。  
`memory.json` 不是记忆本体，长期记忆和会话记忆实际保存在 `chroma_db` 中。

### 6.7 `avatars/`

立绘上传目录，文件通过 `/avatars/<filename>` 对外提供访问。

---

## 7. 系统提示词与连续性机制

当前系统提示词由这些部分组成：

- 角色人格
- 表达风格
- 当前环境与背景
- 世界书注入内容
- 记忆召回内容
- 连续性约束
- 回复规则

### 7.1 连续性约束

`ChatService.build_system_prompt()` 当前会根据最近历史生成 `【连续性约束】`，核心目标是：

- 默认延续上一轮仍然有效的关系、距离感、情绪和场景
- 避免每轮都重新起一个完全无关的新状态
- 避免角色反复复述相同衣着、姿势、动作、神态或场景
- 优先回应用户的新输入，而不是反复做同一段描写

### 7.2 重复动作抑制

除了提示词约束，当前还存在一层保守后处理：

- 会分析最近几轮助手输出中的重复动作标记
- 会对“仍坐在窗边 / 依旧坐在窗边 / 继续坐在窗边”这类轻变体做归一化
- 只在删除后仍保留有效内容时才移除重复动作段
- 当前抑制重点是动作括号段，不是完整语义级重写

---

## 8. 对话、删除与回滚工作流

### 8.1 普通聊天流程

1. 前端提交用户输入
2. 后端做清洗与长度限制
3. 统一半角括号到全角 `（）`
4. 将用户输入拆成 `【用户动作】` / `【用户台词】`
5. 读取最近历史
6. 基于最近历史和当前输入触发世界书
7. 召回长期记忆和会话记忆
8. 构建系统提示词与连续性约束
9. 调用当前模型流式生成
10. 将助手动作改写为第三人称
11. 对最近重复动作做保守抑制
12. 保存 `history.json`
13. 触发记忆提取、压缩、合并和写入

### 8.2 重新生成流程

`POST /api/chat/regenerate` 当前流程是：

1. 找到最新一组 `user -> assistant` 轮次
2. 暂时从历史中移除这一轮
3. 同步移除该轮次相关记忆引用
4. 以原用户输入重新调用聊天
5. 如果重新生成失败，则恢复原轮次并补写原记忆

### 8.3 整轮删除流程

聊天页点击助手消息上的删除按钮时：

1. 前端调用 `DELETE /api/history/turn`
2. 后端按 `turn_id` 或 `turn_index` 删除整轮消息
3. 同步移除该轮次的记忆引用
4. 返回更新后的历史与记忆数量

### 8.4 前端流式收尾

前端在 SSE `done` 事件到达时，会用后端返回的最终历史覆盖流式占位消息。  
这样可以保证用户最终看到的内容，与后端保存到 `history.json` 的内容一致。

---

## 9. 世界书机制

当前世界书采用“关键词触发 + 可选常驻”机制。

### 9.1 触发逻辑

- 触发文本来源：最近 4 条历史消息 + 当前输入
- 命中规则：`keywords` 中任一关键词命中
- `always: true` 条目始终注入

### 9.2 注入格式

命中条目会转换成：

```text
- 标题: 内容
```

然后整体进入系统提示词的 `【世界书】` 段落。

### 9.3 当前边界

- 仍是简单关键词匹配
- 不做向量召回
- 不做复杂优先级系统
- 手工替换世界书文件时，系统不会帮你做差量合并；当前策略是以最新文件内容为准

---

## 10. 记忆系统设计

### 10.1 记忆类型

当前记忆分为两类：

- `persistent`
  - 用户名称 / 称呼
  - 所在地 / 来源
  - 偏好 / 厌恶
  - 习惯 / 计划
  - 关系设定 / 互动边界
- `session`
  - 当前衣着
  - 当前动作
  - 当前场景
  - 当前状态
  - 用户当前动作态

### 10.2 提取方式

当前使用“LLM 提取 + 规则兜底”混合方案：

1. 将最近对话和当前轮内容送入记忆提取提示词
2. 优先尝试结构化 JSON 提取
3. 失败时退回规则提取
4. 对候选记忆做标准化、过滤和压缩

### 10.3 写入与合并

当前写入机制包括：

- 整轮内容先做 hash 去重
- 长期记忆按稳定 `key` 合并
- 会话记忆按槽位覆盖
- 每条记忆记录 `turn_id`
- 每条记忆保留 `turn_index`、`confidence`、`source_turn_ids`
- session 记忆会做新鲜度控制和过期失活

### 10.4 删除与回滚

当前已实现：

- 清空整库 `DELETE /api/memory`
- 删除单条记忆 `DELETE /api/memories/{memory_id}`
- 删除整轮对话时同步移除记忆引用
- 重新生成失败时恢复原轮次和原记忆

### 10.5 当前边界

- 会话记忆仍是轻量状态管理，不是完整状态机
- 旧版本遗留记忆若缺少足够 revision 信息，回滚精度会差于新写入数据
- 结构化提取偶尔失败时会自动降级到规则模式

---

## 11. 运行时模型与状态

当前统一支持两类 Provider：

### 11.1 Ollama

使用：

- `/api/tags`
- `/api/chat`
- `/api/embeddings`
- `/api/embed`

### 11.2 OpenAI-compatible

使用：

- `/models`
- `/chat/completions`
- `/embeddings`

### 11.3 运行时状态字段

`/api/bootstrap` 与 `/api/health` 当前返回的运行时字段包括：

- `healthy`
- `error`
- `provider`
- `provider_label`
- `models`
- `current_model`
- `memory_count`
- `memory_error`
- `embed_model`
- `base_url`
- `api_key_configured`
- `api_key_masked`

---

## 12. 前端状态与本地存储

当前前端会在浏览器本地保存这些状态：

- 聊天页背景 URL：`aura-live.background-url`
- 悬浮立绘偏移量：`aura-live.pet-offset`
- 记忆页筛选条件：`aura-live.memories-filters`

这些状态只影响当前浏览器体验，不参与后端持久化。

补充说明：

- 立绘当前是无边框悬浮展示，不再显示底部名称文字
- 拖动绑定在整张立绘区域，而不是单独的拖拽把手
- 立绘的呼吸感和光晕完全由前端样式实现，不影响后端数据结构

---

## 13. API 清单

### 13.1 页面路由

- `GET /`
- `GET /settings`
- `GET /memories`

### 13.2 基础与历史

- `GET /api/bootstrap`
- `GET /api/health`
- `GET /api/history`
- `DELETE /api/history`
- `DELETE /api/history/turn`

### 13.3 记忆相关

- `DELETE /api/memory`
- `GET /api/memories`
- `DELETE /api/memories/{memory_id}`

### 13.4 角色与世界书

- `GET /api/config/soul`
- `PUT /api/config/soul`
- `POST /api/assets/avatar`
- `GET /api/config/worldbook`
- `PUT /api/config/worldbook`

### 13.5 运行时配置

- `PUT /api/runtime/model`
- `PUT /api/runtime/base-url`
- `PUT /api/runtime/config`

### 13.6 聊天

- `POST /api/chat/stream`
- `POST /api/chat/regenerate`

说明：

- 两个聊天接口都使用 SSE
- 当前前端会处理 `status`、`chunk`、`done`、`error` 这四类事件

---

## 14. 部署方式与当前假设

### 14.1 本地运行

```bash
uvicorn app:app --host 0.0.0.0 --port 8501
```

### 14.2 Docker

```bash
docker build -t aura-live:latest .
docker run -d --name aura-live -p 8501:8501 aura-live:latest
```

### 14.3 Docker Compose

当前仓库自带 `docker-compose.yml`，内容体现的是 NAS 单机部署假设：

- 构建上下文：`/vol1/1000/docker/ai_pet`
- 挂载目录：`/vol1/1000/docker/ai_pet:/app`
- 映射端口：`8501:8501`

直接运行：

```bash
docker compose up -d --build
```

### 14.4 当前部署边界

当前代码和文档都按“单用户、本地 / NAS、仓库内文件直接持久化”来设计。

因此当前没有专门处理：

- 相对路径移植
- 可配置卷抽象
- 多环境部署模板

如果 NAS 上的工作目录发生变化，需要手动修改 `docker-compose.yml` 里的绝对路径绑定；当前不会自动推导或转换。

持久化时至少应保留：

- `soul.json`
- `worldbook.json`
- `history.json`
- `memory.json`
- `runtime.json`
- `avatars/`
- `chroma_db/`

---

## 15. 测试与验证资产

当前仓库已经包含最小回归测试文件：

- `tests/test_chat_service_turn_management.py`

目前覆盖的核心场景：

- 删除整轮对话时历史和记忆引用同步变化
- 重新生成失败后的原轮次恢复
- 系统提示词包含连续性约束
- 最近重复动作在最终保存历史时会被抑制

推荐执行方式：

```bash
python -m unittest discover -s tests
```

前端脚本可用：

```bash
node --check static/app.js
node --check static/memories.js
node --check static/settings.js
```

当前仓库没有 CI，也没有端到端自动化测试。

---

## 16. 当前适用场景

当前版本适合：

- 单用户本地陪伴式聊天
- 长期角色扮演 / 角色伴聊
- NAS 常驻部署
- 基于世界书和记忆系统的持续设定演化

当前版本不面向：

- 多用户系统
- 公网高并发服务
- 严格权限管理 SaaS
- 通用工作流自动化平台

---

## 17. 文档说明

本文档只描述当前仓库中已经实现的真实能力。  
后续如果继续迭代，应继续以代码现状为准同步更新，不保留已废弃设计，不提前写未落地路线图。
