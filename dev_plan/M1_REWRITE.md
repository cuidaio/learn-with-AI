---

## CC，请执行以下任务：M1 — 完整重写（Clean Slate）

**当前状态**：M1.x 代码因反复修补，已积累大量废弃逻辑和互相冲突的实现。现有代码**全部删除**，从头开始实现一个新的分块系统。

---

### 一、删除范围

**删除整个 `backend/app/core/` 目录下的以下文件：**
- `chunking.py`
- `l1_boundary_detector.py`
- `atomic_splitter.py`（如果存在）
- `parent_chunk_builder.py`（如果存在）
- `preprocess.py`（仅保留 `clean_ocr_text()` 函数，其他删除）

**保留以下文件不变：**
- `config.py`（将更新参数）
- `embeddings.py`（不变）
- `logging.py`（不变）
- `models.py`（将重写）
- `schemas.py`（将重写）
- `routes/documents.py`（将简化）
- `tests/test_smoke.py`（将重写）

**不保留任何旧分块逻辑代码。** 不要尝试复用任何现有函数。从头写。

---

### 二、新架构核心设计

#### 2.1 数据模型（models.py 重写）

```python
# 仅三个表，删除所有其他表

class Document(Base):
    __tablename__ = "documents"
    id: UUID
    title: str
    raw_text: str
    cleaned_text: str
    created_at: datetime
    total_atomic_units: int = 0
    total_sub_chunks: int = 0
    total_section_blocks: int = 0

class SubChunk(Base):
    """L2：语义检索单元，存向量"""
    __tablename__ = "sub_chunks"
    id: UUID
    document_id: UUID
    content: str
    start_pos: int
    end_pos: int
    chunk_index: int
    embedding: Vector  # pgvector
    metadata: JSONB  # 包含 source: "heading"|"paragraph"|"sentence"|"merged"

class SectionBlock(Base):
    """L1：上下文容器，不存向量"""
    __tablename__ = "section_blocks"
    id: UUID
    document_id: UUID
    sub_chunk_ids: List[UUID]  # 存储该L1块包含的所有L2块ID
    content: str  # 拼接所有L2块的内容
    start_pos: int  # 第一个L2块的start_pos
    end_pos: int  # 最后一个L2块的end_pos
    block_index: int
    title: str  # 从结构信号提取的标题（可选）
    metadata: JSONB  # 记录边界来源、置信度等
```

#### 2.2 处理流程（五阶段）

```
原始文本
   ↓
【阶段一】清洗文本
   └── clean_ocr_text() → 去除页码、合并断行、移除标记
   ↓
【阶段二】提取结构信号
   └── extract_structural_signals() → 检测标题/章节号，不依赖全局可靠性判断
   ↓
【阶段三】拆分原子单元
   └── split_atomic_units() → 按段落+句子拆分，同时保留结构信号位置信息
   ↓
【阶段四】聚合为子块（SubChunk / L2）
   └── build_sub_chunks() → 每个子块200-1500字符，语义完整，存向量
   ↓
【阶段五】聚合为章节块（SectionBlock / L1）
   └── build_section_blocks() → 将相邻子块打包，切分点永远在子块边界
```

#### 2.3 阶段二：结构信号提取（不再使用置信度/可靠性）

```python
@dataclass
class StructuralSignal:
    position: int
    level: int  # 1=章, 2=节, 3=小节
    content: str  # 标题文本
    source: str  # "markdown_heading" | "chinese_chapter" | "numeric_ordinal"
    
# 不做置信度判断。信号只有"存在"和"不存在"。在阶段五中，
# 这些信号将作为"硬墙"——任何信号的position处，L1块必须切分。
```

#### 2.4 阶段三：原子单元拆分

```python
@dataclass
class AtomicUnit:
    content: str
    start_pos: int
    end_pos: int
    type: str  # "heading" | "paragraph" | "sentence"
    heading_level: int = 0  # 仅当type="heading"时有效
    is_signal_boundary: bool = False  # 是否对应结构信号

# 拆分逻辑：
# 1. 按段落（\n\n）切分
# 2. 段落 >300字符时，按句子（。！？；）进一步拆分为句子
# 3. 如果某个原子单元的位置与结构信号重合，标记 is_signal_boundary=True
```

#### 2.5 阶段四：子块生成

```python
# 输入：List[AtomicUnit]
# 输出：List[SubChunk]
# 规则：
# 1. 从第一个原子单元开始累积，直到累积长度 ≥ CHUNK_SIZE (800)
# 2. 在原子单元边界处切分，绝不在原子单元中间切
# 3. 强制约束：每个SubChunk 200-1500字符
# 4. 如果遇到 is_signal_boundary=True 的原子单元，可以在此处优先切分（但不强制）
```

#### 2.6 阶段五：章节块生成

```python
# 输入：List[SubChunk] + List[StructuralSignal]
# 输出：List[SectionBlock]
# 规则（按优先级排列）：
# 1. 【硬墙】任何 StructuralSignal 的位置，L1块必须在此切分。
#    即：包含该信号位置的SubChunk作为前一个L1块的最后一个块。
# 2. 【大小约束】每个L1块包含的SubChunk内容总和在 500-3000字符
# 3. 【余数处理】如果最后剩余的子块不足 500 字符，并入前一个L1块
# 4. 【重叠】相邻L1块之间，保留最后一个SubChunk作为重叠（可选）
```

---

### 三、接口变更（routes/documents.py）

#### POST /api/documents 响应

```json
{
  "status": "success",
  "document_id": "...",
  "total_atomic_units": 45,
  "total_sub_chunks": 12,
  "total_section_blocks": 5,
  "total_characters": 5840
}
```

#### GET /api/documents/{id}/chunks 响应

```json
{
  "document_id": "...",
  "section_blocks": [
    {
      "block_index": 0,
      "title": "抽象逻辑思维的发展特点",
      "content": "...全文...",
      "sub_chunks": [
        {
          "chunk_index": 0,
          "content": "...片段...",
          "char_count": 380
        }
      ]
    }
  ]
}
```

---

### 四、配置参数（config.py）

```python
# 分块参数（仅保留必要的，删除所有阈值和权重）
CHUNK_SIZE: int = 800           # 子块目标大小
MIN_CHUNK_SIZE: int = 200       # 子块最小
MAX_CHUNK_SIZE: int = 1500      # 子块最大
SECTION_MIN_SIZE: int = 500     # 章节块最小
SECTION_MAX_SIZE: int = 3000    # 章节块最大
```

**删除所有与“置信度”、“阈值”、“权重”、“策略选择”、“信号融合”相关的参数。**

---

### 五、测试用例（test_smoke.py 重写）

仅保留5个核心测试：

1. `test_clean_text()`：验证清洗逻辑
2. `test_atomic_split()`：验证原子单元拆分
3. `test_sub_chunk_build()`：验证子块生成
4. `test_section_build()`：验证章节块生成
5. `test_e2e_upload()`：端到端上传测试

**删除所有测试M1.x多版本遗留的17个测试。**

---

### 六、执行顺序

1. 删除上述目录和文件
2. 重写 `models.py`
3. 重写 `schemas.py`
4. 重写 `config.py`（简化参数）
5. 重写 `preprocess.py`（只保留清洗函数）
6. 新建 `atomic_splitter.py`
7. 新建 `sub_chunk_builder.py`
8. 新建 `section_block_builder.py`
9. 新建 `structural_signal_extractor.py`
10. 重写 `routes/documents.py`
11. 重写 `tests/test_smoke.py`
12. 删除迁移脚本（从零开始，无需迁移旧数据）

---

### 七、约束

1. **不调用任何Embedding API在分块决策中**——分块只基于文本自身特征。Embedding只在存储时调用。
2. **不依赖任何外部库的"语义切分"功能**——不使用`SemanticChunker`或类似方案。
3. **不存储任何冗余字段**——只存储必要的内容、位置、关联关系。
4. **不保留任何废弃代码**——如果某个文件只有部分函数被使用，也整个删除再重写。
5. **不写兼容层**——旧M1.x代码不再使用，无须兼容。

---

### 八、验收标准

- [ ] `docker-compose up -d --build` 正常运行
- [ ] 上传2000字符纯文本 → 至少产生1个SectionBlock和至少2个SubChunk
- [ ] 上传带有 `##` 标题的文本 → SectionBlock在标题位置切分
- [ ] 任何SubChunk的切分位置都在原子单元边界（即不切在句子中间）
- [ ] 任何SectionBlock的切分位置都在SubChunk边界
- [ ] 数据库中三个表（documents, sub_chunks, section_blocks）结构正确
- [ ] 前端展示两层结构
- [ ] 5个测试全部通过

---

### 九、输出要求

- **只写代码，不写解释文档**
- 所有文件编码为 UTF-8
- Backend端口为 `7480`

---

## CC，请立即开始执行完整重写。完成后告诉我「M1 重写已完成，请验收」。