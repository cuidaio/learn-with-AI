<template>
  <Teleport to="body">
    <div v-if="visible" class="eed-overlay" @click.self="$emit('close')">
      <div class="eed-dialog">
        <div class="eed-header">
          <h4>导出实体列表</h4>
          <button class="eed-close" @click="$emit('close')">✕</button>
        </div>
        <div class="eed-body">
          <!-- 导出范围 -->
          <div class="eed-field">
            <label class="eed-label">导出范围</label>
            <div class="eed-radio-group">
              <label class="eed-radio">
                <input v-model="scope" type="radio" value="current" />
                <span>当前筛选结果 ({{ filteredCount }})</span>
              </label>
              <label class="eed-radio">
                <input v-model="scope" type="radio" value="all" />
                <span>全部实体 ({{ totalCount }})</span>
              </label>
            </div>
          </div>
          <!-- 导出格式 -->
          <div class="eed-field">
            <label class="eed-label">导出格式</label>
            <div class="eed-radio-group">
              <label class="eed-radio">
                <input v-model="fileFormat" type="radio" value="markdown" />
                <span>Markdown (.md)</span>
              </label>
              <label class="eed-radio">
                <input v-model="fileFormat" type="radio" value="json" />
                <span>JSON (.json)</span>
              </label>
            </div>
          </div>
          <!-- 包含字段 (仅限 JSON 格式) -->
          <div v-if="fileFormat === 'json'" class="eed-field">
            <label class="eed-label">包含字段</label>
            <div class="eed-checkbox-group">
              <label v-for="f in allFields" :key="f.key" class="eed-checkbox">
                <input v-model="f.selected" type="checkbox" />
                <span>{{ f.label }}</span>
              </label>
            </div>
          </div>
        </div>
        <div class="eed-footer">
          <button class="eed-btn eed-btn-cancel" @click="$emit('close')">取消</button>
          <button class="eed-btn eed-btn-save" :disabled="exporting" @click="handleExport">
            {{ exporting ? '导出中...' : '导出' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, reactive } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  documentId: { type: String, default: '' },
  currentFilterAction: { type: String, default: null },
  filteredCount: { type: Number, default: 0 },
  totalCount: { type: Number, default: 0 },
})

const emit = defineEmits(['close'])

const API_BASE = ''
const scope = ref('current')
const fileFormat = ref('markdown')
const exporting = ref(false)

const allFields = reactive([
  { key: 'name', label: '名称', selected: true },
  { key: 'type', label: '类型', selected: true },
  { key: 'description', label: '描述', selected: true },
  { key: 'introduction_context', label: '上下文', selected: true },
  { key: 'filter_action', label: '状态', selected: true },
  { key: 'source', label: '来源', selected: true },
  { key: 'created_at', label: '创建时间', selected: true },
])

async function handleExport() {
  exporting.value = true
  try {
    const params = new URLSearchParams()
    params.set('document_id', props.documentId)
    params.set('format', fileFormat.value)
    if (scope.value === 'current' && props.currentFilterAction) {
      params.set('filter_action', props.currentFilterAction)
    }

    const res = await fetch(`${API_BASE}/api/entities/export?${params}`)
    if (!res.ok) return

    if (fileFormat.value === 'markdown') {
      const text = await res.text()
      downloadBlob(text, 'entities.md', 'text/markdown')
    } else {
      const data = await res.json()
      // 按选中字段筛选
      const selected = allFields.filter(f => f.selected).map(f => f.key)
      if (selected.length < allFields.length) {
        data.entities = data.entities.map(e => {
          const filtered = {}
          for (const k of selected) {
            if (k in e) filtered[k] = e[k]
          }
          return filtered
        })
      }
      downloadBlob(JSON.stringify(data, null, 2), 'entities.json', 'application/json')
    }
    emit('close')
  } catch {
    // ignore
  } finally {
    exporting.value = false
  }
}

function downloadBlob(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.eed-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9998;
}

.eed-dialog {
  background: var(--p-surface);
  border-radius: var(--r-xl);
  width: 440px;
  max-width: 90vw;
  box-shadow: 0 8px 32px rgba(0,0,0,0.18);
  animation: eedIn 0.15s ease-out;
}

@keyframes eedIn {
  from { opacity: 0; transform: translateY(6px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.eed-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--p-border);
}

.eed-header h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--p-text);
}

.eed-close {
  background: none;
  border: none;
  font-size: 15px;
  color: var(--p-text-muted);
  cursor: pointer;
  width: 26px;
  height: 26px;
  border-radius: var(--r-sm);
  display: flex;
  align-items: center;
  justify-content: center;
}

.eed-close:hover {
  background: var(--p-surface-muted);
}

.eed-body {
  padding: 16px 20px;
}

.eed-field {
  margin-bottom: 14px;
}

.eed-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--p-text);
  margin-bottom: 6px;
}

.eed-radio-group,
.eed-checkbox-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.eed-radio,
.eed-checkbox {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--p-text-secondary);
  cursor: pointer;
}

.eed-radio input,
.eed-checkbox input {
  accent-color: var(--p-primary);
}

.eed-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid var(--p-border);
}

.eed-btn {
  padding: 7px 18px;
  border-radius: var(--r-md);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid transparent;
}

.eed-btn-cancel {
  background: var(--p-surface);
  border-color: var(--p-border);
  color: var(--p-text-secondary);
}

.eed-btn-cancel:hover {
  background: var(--p-surface-muted);
}

.eed-btn-save {
  background: var(--p-primary);
  color: #fff;
}

.eed-btn-save:hover {
  background: var(--p-primary-hover);
}

.eed-btn-save:disabled {
  background: #A5B4FC;
  cursor: not-allowed;
}
</style>