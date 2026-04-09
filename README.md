## 1. 项目概述

AURA-Live 是一个运行在本地或 NAS 环境中的 AI char互动应用，可用于“蒸馏同事”。当前版本采用 `FastAPI + 原生 HTML/CSS/JS + Ollama + ChromaDB` 架构，目标是提供一个可定制人格、可持续记忆、可本地部署的沉浸式聊天界面。

当前实现已经包含以下能力：

- 本地流式聊天
- 可配置的人格、表达风格、环境背景和头像
- 关键词触发式世界书
- 长期记忆提取、向量存储、召回与查看
- 最新一条 AI 回复的“重新生成”
- 可切换的 Ollama 服务地址与当前模型
- 可拖动的形象展示卡片
- 可更换的页面背景
- Docker / Docker Compose 部署

---

## 2. 当前功能清单

### 2.1 聊天页 `/`

聊天页是当前应用的主入口，包含以下特性：

- 固定尺寸的沉浸式聊天窗口
- 消息区独立滚动，输入框固定在底部
- `Enter` 发送，`Shift + Enter` 换行
- SSE 流式输出助手回复
- 聊天气泡支持轻量 Markdown 渲染
- 括号中的动作、神态、环境描写按斜体动作段处理
- 动作描写统一使用第三人称视角
- 右上角快捷设置入口，可快速切换背景图
- 左侧可拖动 3:4 形象展示卡片
- 最新一条助手消息支持悬浮显示“重新生成”按钮

### 2.2 设置页 `/settings`

设置页负责管理运行配置和内容配置，当前包含：

- `Soul` 人格配置
  - 名称
  - 性格描述
  - 表达风格
  - 当前环境与背景描述
  - 头像文件名
- `Worldbook` 世界书表单编辑
  - 标题
  - 关键词
  - 内容
  - 是否总是加载
- `Runtime` 运行配置
  - Ollama 服务地址
  - 当前模型选择
  - Ollama 在线状态
  - 历史消息数量
  - 长期记忆数量
- 运维操作
  - 清空对话历史
  - 清空记忆库
  - 跳转到记忆查看页

### 2.3 记忆页 `/memories`

记忆页用于查看当前长期记忆库中的内容，当前展示：

- 记忆分类
- 记忆分数
- 更新时间
- 记忆摘要
- 用户关键信息
- 助手上下文信息
- 用户原话
- 助手原话

---

## 3. 当前技术架构

### 3.1 技术栈

- 后端：`FastAPI`
- 前端：`原生 HTML / CSS / JavaScript`
- 模型服务：`Ollama`
- 记忆存储：`ChromaDB`
- 语言：`Python 3.10+`
- 服务启动：`uvicorn`
- 容器部署：`Docker / Docker Compose`

### 3.2 模块分层

```text
Browser
  ├─ /                  聊天页
  ├─ /settings          设置页
  ├─ /memories          记忆查看页
  └─ /static/*          静态资源

FastAPI (app.py)
  ├─ 页面路由
  ├─ 配置接口
  ├─ 聊天 SSE 接口
  ├─ 重新生成接口
  └─ 记忆列表接口

ChatService (services/chat_service.py)
  ├─ 加载 soul / worldbook / history / runtime
  ├─ 构建 prompt
  ├─ 世界书触发
  ├─ 调用 LLMClient
  ├─ 保存历史
  ├─ 写入记忆
  └─ 处理重新生成

LLMClient (models/llm.py)
  ├─ /api/tags
  ├─ /api/chat
  ├─ /api/embeddings
  └─ /api/embed

MemoryManager (models/memory.py)
  ├─ 记忆提取
  ├─ 向量写入
  ├─ 去重与合并
  ├─ 相似度召回
  └─ 记忆列表读取
```

---

## 4. 当前目录结构

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
└─ static/
   ├─ index.html
   ├─ app.js
   ├─ chat.css
   ├─ settings.html
   ├─ settings.js
   ├─ memories.html
   ├─ memories.js
   └─ styles.css
```

---

## 5. 核心数据文件

### 5.1 `soul.json`

用于定义 AI 人格和外观。当前字段：

```json
{
  "name": "AURA",
  "personality": "人格描述",
  "style": "表达风格",
  "scene": "当前环境与背景",
  "pet_image": "bot.png"
}
```

### 5.2 `worldbook.json`

用于定义世界书。当前推荐格式为 `entries` 数组，每条世界书支持关键词触发和常驻注入：

```json
{
  "entries": [
    {
      "title": "AURA 身份",
      "keywords": ["AURA", "身份", "你是谁"],
      "content": "AURA 是一个运行在本地环境中的 AI char。",
      "always": false
    }
  ]
}
```

说明：

- `keywords` 命中时加载进 prompt
- `always: true` 时每轮都加载
- 当前设置页使用表单编辑世界书，再保存为该格式

### 5.3 `history.json`

保存完整对话历史。每条记录包含：

```json
{
  "role": "user",
  "content": "消息内容"
}
```

### 5.4 `memory.json`

当前是记忆基础配置文件，占位用途为主：

```json
{
  "enabled": true,
  "save_latest_turn": true,
  "recall_count": 3
}
```

### 5.5 `runtime.json`

保存当前运行时配置：

```json
{
  "base_url": "http://192.168.50.51:11434",
  "current_model": "Gemma4:e4b"
}
```

### 5.6 `chroma_db/`

长期记忆的真实存储位置。`memory.json` 不是记忆内容本体，真实记忆数据保存在 `chroma_db` 下的 Chroma 持久化库中。

---

## 6. 当前运行配置

`config.py` 当前支持的关键环境变量如下：

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `OLLAMA_BASE_URL` | `http://192.168.50.51:11434` | Ollama 服务地址 |
| `DEFAULT_MODEL` | `Gemma4:e4b` | 默认对话模型 |
| `EMBED_MODEL` | `bge-m3` | 默认嵌入模型 |
| `REQUEST_TIMEOUT` | `60` | 请求超时时间 |
| `MAX_RETRIES` | `3` | HTTP 重试次数 |
| `RETRY_DELAY` | `1.0` | 初始重试间隔 |
| `CHROMA_DB_PATH` | `chroma_db` | 记忆数据库目录 |
| `MEMORY_COLLECTION` | `pet_memory` | 记忆集合名 |
| `MEMORY_RECALL_COUNT` | `3` | 每轮召回记忆条数 |
| `MEMORY_SIMILARITY_THRESHOLD` | `0.58` | 记忆召回相似度阈值 |
| `MAX_INPUT_LENGTH` | `1000` | 单轮输入上限 |
| `HISTORY_WINDOW` | `12` | 进入 prompt 的最近历史窗口 |

---

## 7. 当前对话工作流

### 7.1 聊天主流程

每轮对话的当前执行流程为：

```text
用户输入
  -> 输入清理与长度校验
  -> 读取 soul / worldbook / history / runtime
  -> 用当前输入召回长期记忆
  -> 用“最近 4 条历史 + 当前输入”触发世界书
  -> 组装 system prompt
  -> 调用 Ollama 流式生成
  -> 规范括号中的动作描写为第三人称
  -> 保存 history.json
  -> 提取并写入长期记忆
  -> 返回前端并更新运行状态
```

### 7.2 系统 Prompt 组成

当前 `system prompt` 由以下部分动态拼装：

- 人格定义
- 表达风格
- 当前环境与背景
- 命中的世界书条目
- 召回到的长期记忆
- 回复规则

回复规则当前明确要求：

- 自然、简洁、有陪伴感
- 不自称语言模型或系统
- 动作、神态、环境描写写在括号中
- 括号内动作统一使用第三人称描述char

### 7.3 最新回复重新生成

当前已经支持“重新生成最新一条助手回复”：

- 仅对最新一条助手消息显示按钮
- 按钮默认隐藏，鼠标悬停时显示
- 点击后会先移除最新一轮对话，再重新生成
- 若后端生成失败，会回滚原有历史

---

## 8. 当前世界书机制

世界书现在不是整本常驻 prompt，而是关键词触发加载。

### 8.1 触发规则

- 触发文本来源：`最近 4 条历史 + 当前输入`
- 逐条检查 `keywords`
- 命中后把对应条目加入 `【世界书】`
- `always: true` 的条目每轮必定注入

### 8.2 设置页编辑行为

设置页当前使用表单式世界书编辑器，不需要手写 JSON。每条记录包含：

- 标题
- 关键词
- 内容
- 是否总是加载

保存时会统一写回 `worldbook.json`。

---

## 9. 当前记忆机制

### 9.1 存储位置

- 聊天历史：`history.json`
- 长期记忆：`chroma_db/`
- 记忆基础配置：`memory.json`

### 9.2 当前记忆提取策略

当前记忆系统会同时处理两类内容：

#### 用户高价值记忆

优先提取以下信息：

- 名称
- 称呼偏好
- 所在地
- 来源
- 职业
- 喜好 / 厌恶
- 习惯
- 计划
- 近期状态
- 互动边界

低价值寒暄不会写入，例如：

- 你好
- 谢谢
- 哈哈
- 再见

#### 助手上下文记忆

会额外提取char的上下文状态：

- 当前衣着
- 当前动作
- 当前场景

这使得像“穿着什么”“刚才做了什么”“现在处于什么环境”这类上下文更容易被保留下来。

### 9.3 当前记忆去重与合并

当前记忆不是无限堆积，写入时会做三层控制：

- `user_text + bot_text` 哈希去重
- 同类记忆按 `memory_key` 合并
- 相似候选记忆按相似度进一步合并

因此：

- 重复内容不会不断增长
- 同类状态会被更新而不是无止境新增

### 9.4 当前记忆召回

当前召回策略为：

- 使用用户当前输入进行向量检索
- 默认召回 `3` 条
- 先取候选，再用相似度阈值过滤
- 阈值默认为 `0.58`
- 若没有命中但最相近结果足够接近，会回退保留 1 条

召回后的内容会进入 `【长期记忆】` 段落参与回复生成。

### 9.5 当前记忆查看

当前支持独立记忆查看页 `/memories`，可以查看：

- 分类
- 分数
- 时间
- 摘要
- 用户关键信息
- 助手上下文
- 原始对话

---

## 10. 当前前端实现说明

### 10.1 聊天页前端

`static/index.html` + `static/app.js` + `static/chat.css` 当前负责：

- 聊天页 UI
- SSE 消息流接收
- 流式更新节流
- 最新回复重新生成
- 背景图切换与本地缓存
- char卡片拖动与位置缓存
- 聊天气泡富文本渲染
- 动作括号格式处理

### 10.2 设置页前端

`static/settings.html` + `static/settings.js` + `static/styles.css` 当前负责：

- 人格配置表单
- 世界书表单编辑
- Ollama 服务地址切换
- 当前模型切换
- 运行状态显示
- 清空历史与记忆
- 跳转记忆页

### 10.3 记忆页前端

`static/memories.html` + `static/memories.js` 当前负责：

- 拉取 `/api/memories`
- 以卡片形式展示长期记忆
- 刷新当前记忆列表

---

## 11. 当前 API 列表

### 11.1 页面路由

| 路由 | 方法 | 说明 |
| --- | --- | --- |
| `/` | `GET` | 聊天页 |
| `/settings` | `GET` | 设置页 |
| `/memories` | `GET` | 记忆查看页 |

### 11.2 数据与配置接口

| 路由 | 方法 | 说明 |
| --- | --- | --- |
| `/api/bootstrap` | `GET` | 返回页面初始化所需的全部数据 |
| `/api/health` | `GET` | 返回运行状态、模型状态、记忆状态 |
| `/api/history` | `GET` | 获取历史消息 |
| `/api/history` | `DELETE` | 清空历史消息 |
| `/api/memory` | `DELETE` | 清空记忆库 |
| `/api/memories` | `GET` | 获取长期记忆列表 |
| `/api/config/soul` | `GET` | 获取人格配置 |
| `/api/config/soul` | `PUT` | 更新人格配置 |
| `/api/config/worldbook` | `GET` | 获取世界书 |
| `/api/config/worldbook` | `PUT` | 更新世界书 |
| `/api/runtime/model` | `PUT` | 更新当前模型 |
| `/api/runtime/base-url` | `PUT` | 更新 Ollama 服务地址 |

### 11.3 聊天接口

| 路由 | 方法 | 说明 |
| --- | --- | --- |
| `/api/chat/stream` | `POST` | 正常聊天的 SSE 流式接口 |
| `/api/chat/regenerate` | `POST` | 重新生成最新回复的 SSE 流式接口 |

### 11.4 运行状态字段

`/api/health` 与 `/api/bootstrap.runtime` 当前返回：

- `healthy`
- `error`
- `models`
- `current_model`
- `memory_count`
- `memory_error`
- `embed_model`
- `base_url`

---

## 12. 部署与运行

### 12.1 本地运行

安装依赖：

```bash
pip install -r requirements.txt
```

准备模型：

```bash
ollama pull Gemma4:e4b
ollama pull bge-m3
```

启动服务：

```bash
uvicorn app:app --host 0.0.0.0 --port 8501
```

访问地址：

```text
http://127.0.0.1:8501
```

### 12.2 NAS / Docker Compose

当前默认 NAS 目标参数：

- NAS IP：`192.168.50.51`
- 应用端口：`8501`
- Ollama 端口：`11434`
- 默认聊天模型：`Gemma4:e4b`
- 默认嵌入模型：`bge-m3`
- 目标目录：`/vol1/1000/docker/ai_pet`

当前 `docker-compose.yml` 中的核心环境变量：

```yaml
environment:
  OLLAMA_BASE_URL: "http://192.168.50.51:11434"
  DEFAULT_MODEL: "Gemma4:e4b"
  EMBED_MODEL: "bge-m3"
  APP_TITLE: "AURA Live"
  REQUEST_TIMEOUT: "60"
```

部署命令：

```bash
cd /vol1/1000/docker/ai_pet
docker compose up -d --build
```

容器启动命令由 `Dockerfile` 中的 `uvicorn app:app --host 0.0.0.0 --port 8501` 提供。

### 12.3 持久化目录

以下路径需要保存在挂载卷中：

- `/app/soul.json`
- `/app/worldbook.json`
- `/app/history.json`
- `/app/memory.json`
- `/app/runtime.json`
- `/app/avatars/`
- `/app/chroma_db/`

---

## 13. 当前使用约束

### 13.1 Ollama 依赖

聊天和记忆都依赖 Ollama，但依赖点不同：

- 聊天依赖 `DEFAULT_MODEL`
- 记忆依赖 `EMBED_MODEL`

如果只安装了聊天模型而没有安装嵌入模型：

- 聊天可以正常工作
- 记忆不会写入
- `memory_count` 不会增长
- `memory_error` 会反映错误信息

### 13.2 部署边界

当前版本的目标部署场景是：

- 本地设备
- 局域网
- 单用户或家庭环境

不建议直接裸露到公网。

---

## 14. 常见问题

### 14.1 聊天正常，但记忆一直是 0

最常见原因是嵌入模型不存在。当前默认嵌入模型是：

```bash
bge-m3
```

确认是否已安装：

```bash
curl http://192.168.50.51:11434/api/tags
```

如果未安装，执行：

```bash
ollama pull bge-m3
```

### 14.2 页面能打开，但无法聊天

通常是 `OLLAMA_BASE_URL` 不可达，先检查：

```bash
curl http://192.168.50.51:11434/api/tags
```

### 14.3 为什么动作描写会变成第三人称

这是当前实现规则。括号内动作、神态、环境描写会被统一规范为第三人称，以保持char叙述视角一致。

### 14.4 真正的长期记忆在哪里看

现在可以直接访问：

```text
/memories
```

底层存储仍在 `chroma_db/`，但日常查看不再需要手动翻数据库文件。
