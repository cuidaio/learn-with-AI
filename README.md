# learn-with-AI

AI 知识学习平台：文档上传 → 语义分块 → 向量化 → 知识图谱 → RAG 问答 → 自动出题。

## 功能

- **文档管理**：上传、分块、语义检索
- **知识图谱**：实体 / 关系提取，浏览 + 编辑双模式
- **RAG 问答**：基于文档的流式问答，支持引用溯源
- **自动出题**：根据知识点生成题目并判分
- **API 配置**：可视化配置 Embedding / LLM 服务

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.10 / FastAPI / pgvector |
| 前端 | Vue 3 / Vite / @antv/g6 / Pinia |
| 数据库 | PostgreSQL 16 + pgvector |
| 缓存 | Redis 7 |
| 部署 | Docker Compose |

## 前置条件

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)（Windows / macOS 均可）
  - **Windows 用户**：安装后务必在 Settings → General 中勾选 **Use the WSL 2 based engine**，否则容器可能无法启动。
  - 启动 Docker Desktop，等状态栏显示 **"Docker is running"** 后再执行下一步。
- 一个可用的 **Embedding** 服务（如 SiliconFlow、OpenAI、智谱等兼容 OpenAI 接口的平台）
- 一个可用的 **LLM** 服务（如 DeepSeek、OpenAI）

## 快速开始

### 方式一：双击启动脚本（推荐，自动引导）

| 系统 | 命令 |
|------|------|
| Windows | 双击 `start.bat` |
| macOS / Linux | `chmod +x start.sh && ./start.sh` |

脚本会自动：检查 `.env`（不存在则从模板复制并提示你填写）→ 检测 Docker → 启动 → 显示访问地址。

### 方式二：手动命令行

#### 1. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，至少填入以下必填项：

| 变量 | 说明 |
|------|------|
| `EMBEDDING_BASE_URL` | Embedding 服务地址 |
| `EMBEDDING_API_KEY` | Embedding API Key |
| `EMBEDDING_MODEL` | Embedding 模型名 |
| `LLM_BASE_URL` | LLM 服务地址 |
| `LLM_API_KEY` | LLM API Key |
| `LLM_MODEL` | LLM 模型名 |

> `DATABASE_URL` 在 Docker 环境下保持默认即可，无需修改。其余可选参数见 `.env.example` 注释行，带默认值，首次运行可不动。

#### 2. 启动

```bash
docker compose up -d
```

首次启动会拉取镜像并构建，约需数分钟。

#### 3. 访问

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:5173 |
| 后端 API | http://localhost:7480 |
| API 文档（Swagger） | http://localhost:7480/docs |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

打开浏览器访问 http://localhost:5173 即可使用。

### 快速体验（可选）

仓库提供了 2 篇示例文档（`sample_docs/`），方便你开箱即体验完整流程：

1. 启动后进入「文档管理」。
2. 上传 `sample_docs/` 下的 `机器学习基础.txt` 和/或 `知识图谱入门.md`。
3. 等待系统自动完成分块、向量化、实体与关系提取。
4. 切换到「知识图谱」浏览实体关系，或进入「问答」输入问题（如"什么是 Transformer？"RAG 会基于你上传的文档回答）。

## 常用命令

```bash
# 查看日志
docker-compose logs -f backend
docker-compose logs -f frontend

# 重启单个服务（改代码后）
docker-compose restart backend
docker-compose restart frontend

# 重新构建（依赖变更后）
docker-compose up -d --build backend
docker-compose up -d --build frontend

# 停止
docker-compose down

# 停止并清空数据（⚠️ 删除所有文档、图谱、题目）
docker-compose down -v
```

## 数据持久化

所有数据（文档、向量、图谱、题目、配置）保存在 Docker 卷 `postgres_data` 中：

- 正常 `docker-compose down` 后再 `up`，数据保留
- 只有 `docker-compose down -v` 才会清空数据

## 项目结构

```
.
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── core/             # 核心引擎（RAG、图谱、分块、出题…）
│   │   ├── routes/           # API 路由
│   │   ├── tasks/            # 异步任务
│   │   ├── database.py       # 数据库连接 + 初始化
│   │   ├── models.py         # ORM 模型
│   │   ├── schemas.py        # Pydantic 请求/响应
│   │   └── main.py           # FastAPI 入口
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                 # Vue 3 前端
│   ├── src/
│   │   ├── components/       # 图谱、聊天、题目、配置面板…
│   │   ├── stores/           # Pinia 状态
│   │   └── layouts/
│   ├── Dockerfile
│   └── package.json
├── dev_plan/                 # 开发里程碑文档
├── docker-compose.yml
├── .env.example              # 环境变量模板
└── .gitignore
```

## 许可证

仅供学习交流使用。
