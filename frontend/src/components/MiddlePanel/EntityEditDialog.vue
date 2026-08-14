<template>
  <Teleport to="body">
    <div v-if="visible" class="eed-overlay" @click.self="$emit('close')">
      <div class="eed-dialog">
        <div class="eed-header">
          <h4>编辑实体</h4>
          <button class="eed-close" @click="$emit('close')">✕</button>
        </div>
        <div class="eed-body">
          <!-- 名称 -->
          <div class="eed-field">
            <label class="eed-label">名称</label>
            <input v-model="form.name" class="eed-input" placeholder="实体名称" />
          </div>
          <!-- 类型 -->
          <div class="eed-field">
            <label class="eed-label">类型</label>
            <select v-model="form.entity_type" class="eed-select">
              <option value="concept">概念</option>
              <option value="theorist">理论家</option>
              <option value="theory">理论</option>
              <option value="method">方法</option>
              <option value="fact">事实</option>
            </select>
          </div>
          <!-- 描述 -->
          <div class="eed-field">
            <label class="eed-label">描述</label>
            <textarea v-model="form.description" class="eed-textarea" placeholder="描述该知识点" rows="2"></textarea>
          </div>
          <!-- 上下文 -->
          <div class="eed-field">
            <label class="eed-label">上下文</label>
            <textarea v-model="form.introduction_context" class="eed-textarea" placeholder="被介绍时的上下文" rows="3"></textarea>
          </div>
          <!-- 状态 -->
          <div class="eed-field">
            <label class="eed-label">状态</label>
            <select v-model="form.filter_action" class="eed-select">
              <option value="keep">✅ 已确认</option>
              <option value="review">⏳ 待审核</option>
              <option value="discard">🗑️ 已过滤</option>
            </select>
          </div>
          <!-- 元信息 -->
          <div class="eed-meta">
            <span class="eed-meta-item">创建于：{{ formatDate(entity.created_at) }}</span>
            <span class="eed-meta-item">来源：{{ entity.source === 'manual' ? '手动添加' : 'LLM' }}</span>
          </div>
        </div>
        <div class="eed-footer">
          <button class="eed-btn eed-btn-cancel" @click="$emit('close')">取消</button>
          <button class="eed-btn eed-btn-save" :disabled="saving || !form.name.trim()" @click="handleSave">
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { reactive, watch, ref } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  entity: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['close', 'saved'])

const API_BASE = ''
const saving = ref(false)

const form = reactive({
  name: '',
  entity_type: 'concept',
  description: '',
  introduction_context: '',
  filter_action: 'keep',
})

watch(() => props.visible, (v) => {
  if (v && props.entity) {
    form.name = props.entity.name || ''
    form.entity_type = props.entity.entity_type || 'concept'
    form.description = props.entity.description || ''
    form.introduction_context = props.entity.introduction_context || ''
    form.filter_action = props.entity.filter_action || 'keep'
  }
})

function formatDate(d) {
  if (!d) return '—'
  try {
    return new Date(d).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch {
    return '—'
  }
}

async function handleSave() {
  if (!form.name.trim()) return
  saving.value = true
  try {
    const res = await fetch(`${API_BASE}/api/entities/${props.entity.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: form.name.trim(),
        entity_type: form.entity_type,
        description: form.description.trim(),
        introduction_context: form.introduction_context.trim(),
        filter_action: form.filter_action,
      }),
    })
    if (res.ok) {
      const updated = await res.json()
      emit('saved', updated)
    }
  } catch {
    // ignore
  } finally {
    saving.value = false
  }
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
  width: 480px;
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
  margin-bottom: 12px;
}

.eed-field:last-child {
  margin-bottom: 0;
}

.eed-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--p-text);
  margin-bottom: 5px;
}

.eed-input,
.eed-select,
.eed-textarea {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--p-border);
  border-radius: var(--r-sm);
  font-size: 13px;
  color: var(--p-text);
  background: var(--p-surface);
  outline: none;
  box-sizing: border-box;
  font-family: inherit;
}

.eed-input:focus,
.eed-select:focus,
.eed-textarea:focus {
  border-color: var(--p-primary);
  box-shadow: 0 0 0 3px rgba(79, 106, 240, 0.12);
}

.eed-textarea {
  resize: vertical;
  min-height: 50px;
}

.eed-meta {
  display: flex;
  gap: 16px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--p-border);
}

.eed-meta-item {
  font-size: 11px;
  color: var(--p-text-muted);
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
