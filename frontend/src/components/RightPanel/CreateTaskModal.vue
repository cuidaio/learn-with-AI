<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="modal">
      <div class="modal-header">
        <h3>创建任务</h3>
        <button class="close-btn" @click="$emit('close')">✕</button>
      </div>

      <div class="modal-body">
        <!-- 任务类型 -->
        <div class="section">
          <label class="section-label">任务类型</label>
          <div class="type-options">
            <label class="type-option" :class="{ active: taskType === 'questions' }">
              <input type="radio" v-model="taskType" value="questions" />
              <span>📝 出题</span>
            </label>
            <label class="type-option" :class="{ active: taskType === 'graph' }">
              <input type="radio" v-model="taskType" value="graph" />
              <span>📊 知识图谱</span>
            </label>
          </div>
        </div>

        <!-- 出题配置 -->
        <template v-if="taskType === 'questions'">
          <div class="section">
            <label class="section-label">场景</label>
            <select v-model="scenario" class="select">
              <option value="section_review">章节自测</option>
              <option value="weakness_focus">薄弱专项</option>
              <option value="comprehensive">综合模拟</option>
            </select>
          </div>

          <div class="section">
            <label class="section-label">
              知识点
              <span class="hint">（{{ selectedEntities.length }} 个已选）</span>
            </label>
            <TransferTree
              v-model="selectedEntities"
              :tree-data="knowledgeTree"
            />
          </div>

          <div class="section">
            <label class="section-label">题型</label>
            <div class="type-checkboxes">
              <label v-for="t in typeOptions" :key="t.key" class="checkbox-label">
                <input type="checkbox" :value="t.key" v-model="selectedTypes" />
                {{ t.label }}
              </label>
            </div>
          </div>

          <div class="section">
            <span class="section-label">预计生成：{{ estimatedCount }} 题</span>
          </div>
        </template>

        <!-- 图谱提示 -->
        <template v-if="taskType === 'graph'">
          <div class="section">
            <p class="graph-hint">知识图谱将基于选中文档的内容自动提取实体和关系。</p>
          </div>
        </template>
      </div>

      <div class="modal-footer">
        <button class="btn btn-cancel" @click="$emit('close')">取消</button>
        <button class="btn btn-primary" :disabled="!canCreate || taskStore.state.isCreating" @click="confirmCreate">
          {{ taskStore.state.isCreating ? '创建中...' : '确认创建' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useDocumentStore } from '../../stores/useDocumentStore'
import { useTaskStore } from '../../stores/useTaskStore'
import { useContentStore } from '../../stores/useContentStore'
import { useLearningStore } from '../../stores/useLearningStore'
import TransferTree from '../TransferTree.vue'

const emit = defineEmits(['close'])

const API_BASE = ''

const docStore = useDocumentStore()
const taskStore = useTaskStore()
const contentStore = useContentStore()
const learningStore = useLearningStore()

const taskType = ref('questions')
const scenario = ref('section_review')
const selectedEntities = ref([])
const selectedTypes = ref(['choice', 'multi_choice', 'fill', 'short_answer', 'essay'])
const entities = ref([])

const typeLabels = { concept: '概念', theorist: '理论家', theory: '理论', method: '方法', fact: '事实' }

// 将扁平实体列表转为按类型分组的树结构
const knowledgeTree = computed(() => {
  const groups = {}
  for (const e of entities.value) {
    const t = e.entity_type || 'concept'
    if (!groups[t]) groups[t] = { id: `type-${t}`, label: typeLabels[t] || t, type: 'folder', children: [] }
    groups[t].children.push({ id: e.id, label: e.name, type: 'entity' })
  }
  return Object.values(groups)
})

const typeOptions = [
  { key: 'choice', label: '单选' },
  { key: 'multi_choice', label: '多选' },
  { key: 'fill', label: '填空' },
  { key: 'short_answer', label: '简答' },
  { key: 'essay', label: '论述' },
]

const estimatedCount = computed(() => {
  const count = selectedEntities.value.length
  const typeCount = selectedTypes.value.length
  if (count === 0 || typeCount === 0) return 0
  return Math.min(count * typeCount * 2, 50)
})

const canCreate = computed(() => {
  if (taskType.value === 'graph') return !!docStore.state.selectedDocumentId
  return docStore.state.selectedDocumentId && selectedEntities.value.length > 0 && selectedTypes.value.length > 0
})

onMounted(async () => {
  const docId = docStore.state.selectedDocumentId
  if (docId) {
    try {
      const res = await fetch(`${API_BASE}/api/documents/${docId}/entities`)
      if (res.ok) {
        entities.value = await res.json()
      }
    } catch {
      // ignore
    }
  }
})

async function confirmCreate() {
  const docId = docStore.state.selectedDocumentId
  if (!docId) return

  let taskId = null
  if (taskType.value === 'questions') {
    taskId = await taskStore.createQuestionTask(docId, {
      entityIds: selectedEntities.value,
      types: selectedTypes.value,
      totalCount: estimatedCount.value,
      scenario: scenario.value,
    })
  } else {
    taskId = await taskStore.createGraphTask(docId)
  }

  if (taskId) {
    taskStore.recordTaskPoll(taskId)
    await taskStore.fetchCards(docId)
    await learningStore.record('task_created', {
      document_id: docId,
      context: { task_type: taskType.value, task_id: taskId },
    })
    emit('close')
  }
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}

.modal {
  background: var(--p-surface);
  border-radius: var(--r-xl);
  width: 480px;
  max-width: 90vw;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-lg);
  animation: modalIn 0.18s ease-out;
}

@keyframes modalIn {
  from { opacity: 0; transform: translateY(8px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 24px;
  border-bottom: 1px solid var(--p-border);
}

.modal-header h3 {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
  color: var(--p-text);
}

.close-btn {
  background: none;
  border: none;
  font-size: 16px;
  color: var(--p-text-muted);
  cursor: pointer;
  width: 28px;
  height: 28px;
  border-radius: var(--r-sm);
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn:hover {
  background: var(--p-surface-muted);
  color: var(--p-text-secondary);
}

.modal-body {
  padding: 20px 24px;
  overflow-y: auto;
  flex: 1;
}

.section {
  margin-bottom: 16px;
}

.section:last-child {
  margin-bottom: 0;
}

.section-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--p-text);
  margin-bottom: 8px;
  letter-spacing: 0.01em;
}

.hint {
  color: var(--p-text-muted);
  font-weight: 400;
}

.type-options {
  display: flex;
  gap: 8px;
}

.type-option {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 12px;
  border: 1px solid var(--p-border);
  border-radius: var(--r-md);
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  color: var(--p-text-secondary);
  transition: all 0.12s ease;
  background: var(--p-surface);
}

.type-option:hover {
  border-color: #cbd5e1;
  background: var(--p-surface-subtle);
}

.type-option.active {
  border-color: var(--p-primary);
  background: var(--p-primary-light);
  color: var(--p-primary);
}

.type-option input { display: none; }

.select {
  width: 100%;
  padding: 9px 12px;
  border: 1px solid var(--p-border);
  border-radius: var(--r-md);
  font-size: 13px;
  color: var(--p-text);
  background: var(--p-surface);
  outline: none;
  cursor: pointer;
}

.select:focus {
  border-color: var(--p-primary);
  box-shadow: 0 0 0 3px rgba(79, 106, 240, 0.12);
}

.graph-hint {
  font-size: 13px;
  color: var(--p-text-secondary);
  line-height: 1.6;
  padding: 8px 0;
}

.type-checkboxes {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.type-checkboxes label {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border: 1px solid var(--p-border);
  border-radius: var(--r-sm);
  font-size: 13px;
  cursor: pointer;
  color: var(--p-text-secondary);
  transition: all 0.12s ease;
}

.type-checkboxes label:hover {
  border-color: #cbd5e1;
  background: var(--p-surface-subtle);
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 24px;
  border-top: 1px solid var(--p-border);
}

.btn {
  padding: 8px 20px;
  border-radius: var(--r-md);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid transparent;
  line-height: 1.4;
}

.btn-cancel {
  background: var(--p-surface);
  border-color: var(--p-border);
  color: var(--p-text-secondary);
}

.btn-cancel:hover {
  background: var(--p-surface-muted);
  border-color: #cbd5e1;
}

.btn-primary {
  background: var(--p-primary);
  color: #fff;
}

.btn-primary:hover {
  background: var(--p-primary-hover);
}

.btn-primary:disabled {
  background: #A5B4FC;
  cursor: not-allowed;
}

/* 滚动条 */
.modal-body::-webkit-scrollbar {
  width: 4px;
}
.modal-body::-webkit-scrollbar-thumb {
  background: transparent;
  border-radius: 2px;
}
.modal-body:hover::-webkit-scrollbar-thumb {
  background: var(--p-border);
}
</style>
