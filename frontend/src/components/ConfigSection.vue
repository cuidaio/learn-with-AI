<template>
  <div class="config-section">
    <div class="section-header">
      <h3 class="section-title">{{ title }}</h3>
      <button class="test-btn" @click="$emit('test')" :disabled="isTesting" :title="'测试连接'">
        <svg v-if="isTesting" class="spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
        <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
        <span>测试</span>
      </button>
      <span v-if="testStatus && testStatus.success" class="test-result ok">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
        {{ testStatus.latency }}s
      </span>
      <span v-else-if="testStatus && !testStatus.success" class="test-result fail">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        失败
      </span>
    </div>

    <div class="field-row">
      <label class="field-label">Base URL</label>
      <input
        class="field-input"
        type="text"
        :value="baseUrl"
        @input="$emit('update:baseUrl', $event.target.value)"
        placeholder="https://api.example.com/v1/"
      />
    </div>

    <div class="field-row">
      <label class="field-label">API Key</label>
      <div class="key-input-wrap">
        <input
          class="field-input key-input"
          :type="showKey ? 'text' : 'password'"
          :value="showKey ? apiKey : maskedKey || apiKey"
          @input="$emit('update:apiKey', $event.target.value)"
          placeholder="sk-..."
          autocomplete="off"
        />
        <button class="toggle-key" @click="showKey = !showKey" :title="showKey ? '隐藏' : '显示'" type="button" tabindex="-1">
          <svg v-if="showKey" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
        </button>
      </div>
    </div>

    <div class="field-row">
      <label class="field-label">模型</label>
      <div class="model-field-wrap" ref="modelFieldWrap">
        <div class="model-input-wrapper">
          <input
            class="field-input"
            type="text"
            :value="model"
            @input="$emit('update:model', $event.target.value)"
            placeholder="model-name"
          />
          <button
            class="fetch-btn"
            :disabled="!canFetch || isFetchingModels"
            :title="fetchDisabledReason || ''"
            @click="handleFetch"
          >
            <svg v-if="isFetchingModels" class="spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
            <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
            <span>{{ isFetchingModels ? '获取中…' : '获取模型' }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- Floating dropdown (Teleported to body for overflow safety) -->
  <Teleport to="body">
    <div
      v-if="showModelDropdown"
      :data-dropdown="`model-dropdown-${type}`"
      class="model-dropdown"
      :style="dropdownPosition"
    >
      <div v-if="fetchError" class="model-error">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        {{ fetchError }}
      </div>
      <template v-else>
        <div
          v-for="m in modelList"
          :key="m"
          class="model-option"
          @click.stop="selectModel(m)"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
          {{ m }}
        </div>
        <div v-if="modelList.length === 0" class="model-empty">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
          暂无可用模型
        </div>
      </template>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useConfigStore } from '../stores/useConfigStore'

const props = defineProps({
  title: { type: String, required: true },
  testStatus: { type: Object, default: null },
  isTesting: { type: Boolean, default: false },
  baseUrl: { type: String, default: '' },
  apiKey: { type: String, default: '' },
  model: { type: String, default: '' },
  maskedKey: { type: String, default: '' },
  type: { type: String, required: true },  // 'embedding' | 'llm'
})

const emit = defineEmits(['update:baseUrl', 'update:apiKey', 'update:model', 'test'])

const store = useConfigStore()
const showKey = ref(false)

// ── Model fetch state ──
const modelList = ref([])
const isFetchingModels = ref(false)
const showModelDropdown = ref(false)
const fetchError = ref('')
const dropdownPosition = ref({ top: '0px', left: '0px', width: '0px' })
const modelFieldWrap = ref(null)

const canFetch = computed(() => props.baseUrl.trim() !== '' && props.apiKey.trim() !== '')
const fetchDisabledReason = computed(() => {
  if (!props.baseUrl.trim()) return '请先填写 Base URL'
  if (!props.apiKey.trim()) return '请先填写 API Key'
  return ''
})

async function handleFetch() {
  if (isFetchingModels.value) return
  isFetchingModels.value = true
  fetchError.value = ''
  modelList.value = []
  showModelDropdown.value = false
  try {
    const data = await store.fetchModels(props.type, props.baseUrl, props.apiKey)
    modelList.value = data.models || []
    showModelDropdown.value = true
  } catch (e) {
    fetchError.value = e.message
    showModelDropdown.value = true
  } finally {
    isFetchingModels.value = false
  }
  if (showModelDropdown.value) {
    await nextTick()
    positionDropdown()
  }
}

function positionDropdown() {
  if (!modelFieldWrap.value) return
  const rect = modelFieldWrap.value.getBoundingClientRect()
  dropdownPosition.value = {
    top: rect.bottom + 4 + 'px',
    left: rect.left + 'px',
    width: rect.width + 'px',
  }
}

function selectModel(name) {
  emit('update:model', name)
  showModelDropdown.value = false
}

// ── Close on outside click / ESC ──
function onDocumentClick(e) {
  if (!showModelDropdown.value) return
  const dropdown = document.querySelector(`[data-dropdown="model-dropdown-${props.type}"]`)
  if (dropdown?.contains(e.target)) return
  if (modelFieldWrap.value?.contains(e.target)) return
  showModelDropdown.value = false
}

function onKeyDown(e) {
  if (e.key === 'Escape' && showModelDropdown.value) {
    showModelDropdown.value = false
  }
}

function onWindowResize() {
  if (showModelDropdown.value) {
    showModelDropdown.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
  document.addEventListener('keydown', onKeyDown)
  window.addEventListener('resize', onWindowResize)
})

onUnmounted(() => {
  document.removeEventListener('click', onDocumentClick)
  document.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('resize', onWindowResize)
})
</script>

<style scoped>
.config-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 2px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--p-text);
  flex: 1;
}

.test-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  font-size: 12px;
  font-weight: 500;
  border: 1px solid var(--p-border);
  border-radius: var(--r-xs);
  background: var(--p-surface);
  color: var(--p-text-secondary);
  cursor: pointer;
  transition: all 0.15s ease;
}

.test-btn:hover:not(:disabled) {
  border-color: var(--p-primary);
  color: var(--p-primary);
}

.test-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.test-result {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}

.test-result.ok {
  color: var(--p-success);
}

.test-result.fail {
  color: var(--p-error);
}

.field-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.field-label {
  width: 72px;
  font-size: 12px;
  font-weight: 500;
  color: var(--p-text-secondary);
  flex-shrink: 0;
}

.field-input {
  flex: 1;
  height: 34px;
  padding: 0 10px;
  font-size: 13px;
  font-family: inherit;
  color: var(--p-text);
  background: var(--p-surface);
  border: 1px solid var(--p-border);
  border-radius: var(--r-xs);
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.field-input:focus {
  border-color: var(--p-primary);
  box-shadow: 0 0 0 2px rgba(79, 106, 240, 0.12);
}

.field-input::placeholder {
  color: var(--p-text-muted);
}

.key-input-wrap {
  flex: 1;
  display: flex;
  position: relative;
}

.key-input {
  flex: 1;
  padding-right: 36px;
}

.toggle-key {
  position: absolute;
  right: 4px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: var(--r-xs);
  background: transparent;
  color: var(--p-text-muted);
  cursor: pointer;
  transition: color 0.15s ease;
}

.toggle-key:hover {
  color: var(--p-text-secondary);
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.spin {
  animation: spin 1s linear infinite;
}

/* ── Model fetch button ── */
.model-field-wrap {
  flex: 1;
  position: relative;
}

.model-input-wrapper {
  display: flex;
  flex: 1;
  gap: 6px;
  align-items: center;
}

.model-input-wrapper .field-input {
  flex: 1;
}

.fetch-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 0 10px;
  height: 34px;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  border: 1px solid var(--p-border);
  border-radius: var(--r-xs);
  background: var(--p-surface);
  color: var(--p-text-secondary);
  cursor: pointer;
  transition: all 0.15s ease;
  flex-shrink: 0;
}

.fetch-btn:hover:not(:disabled) {
  border-color: var(--p-primary);
  color: var(--p-primary);
}

.fetch-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* ── Floating dropdown (Teleported to body) ── */
.model-dropdown {
  position: fixed;
  z-index: 1001;
  background: var(--p-surface);
  border: 1px solid var(--p-border);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-lg);
  max-height: 200px;
  overflow-y: auto;
  padding: 4px;
}

.model-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  font-size: 13px;
  color: var(--p-text);
  cursor: pointer;
  border-radius: var(--r-xs);
  transition: background 0.1s;
}

.model-option:hover {
  background: var(--p-surface-muted);
}

.model-empty {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px;
  font-size: 12px;
  color: var(--p-text-muted);
}

.model-error {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  font-size: 12px;
  color: var(--p-error);
  line-height: 1.4;
}
</style>
