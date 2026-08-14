<template>
  <Teleport to="body">
    <Transition name="panel">
      <div v-if="visible" class="panel-overlay" @click.self="onClose">
        <div class="panel" role="dialog" aria-label="API 配置" aria-modal="true">
          <!-- Header -->
          <div class="panel-header">
            <h2 class="panel-title">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="3"></circle>
                <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"></path>
              </svg>
              API 配置
            </h2>
            <button class="close-btn" @click="onClose" aria-label="关闭">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>

          <div class="panel-body">
            <!-- Embedding Section -->
            <ConfigSection
              title="Embedding 服务"
              type="embedding"
              :testStatus="store.state.testStatus.embedding"
              :isTesting="store.state.isTesting"
              :baseUrl="localEmbedding.base_url"
              :apiKey="localEmbedding.api_key"
              :model="localEmbedding.model"
              :maskedKey="store.state.embedding.api_key_masked"
              @update:baseUrl="localEmbedding.base_url = $event"
              @update:apiKey="localEmbedding.api_key = $event"
              @update:model="localEmbedding.model = $event"
              @test="handleTest('embedding')"
            />

            <div class="section-divider"></div>

            <!-- LLM Section -->
            <ConfigSection
              title="LLM 服务"
              type="llm"
              :testStatus="store.state.testStatus.llm"
              :isTesting="store.state.isTesting"
              :baseUrl="localLLM.base_url"
              :apiKey="localLLM.api_key"
              :model="localLLM.model"
              :maskedKey="store.state.llm.api_key_masked"
              @update:baseUrl="localLLM.base_url = $event"
              @update:apiKey="localLLM.api_key = $event"
              @update:model="localLLM.model = $event"
              @test="handleTest('llm')"
            />
          </div>

          <!-- Footer actions -->
          <div class="panel-footer">
            <div class="footer-messages">
              <span v-if="store.state.saveMessage" class="msg-success">{{ store.state.saveMessage }}</span>
              <span v-if="store.state.errorMessage" class="msg-error">{{ store.state.errorMessage }}</span>
            </div>
            <div class="footer-actions">
              <button class="btn btn-outline" @click="handleReset" :disabled="store.state.isSaving">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>
                重置为默认
              </button>
              <button class="btn btn-primary" @click="handleSave" :disabled="store.state.isSaving">
                <svg v-if="store.state.isSaving" class="spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
                <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
                {{ store.state.isSaving ? '保存中…' : '保存配置' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { reactive, watch, onMounted } from 'vue'
import { useConfigStore } from '../stores/useConfigStore'
import ConfigSection from './ConfigSection.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
})
const emit = defineEmits(['close'])
const store = useConfigStore()

const localEmbedding = reactive({ base_url: '', api_key: '', model: '' })
const localLLM = reactive({ base_url: '', api_key: '', model: '' })

// Populate local state when panel opens
watch(() => props.visible, async (v) => {
  if (v) {
    store.state.saveMessage = ''
    store.state.errorMessage = ''
    store.state.testStatus = { embedding: null, llm: null }
    // 确保从服务器加载最新配置后再填充本地编辑状态
    await store.fetchConfig()
    localEmbedding.base_url = store.state.embedding.base_url || ''
    localEmbedding.api_key = store.state.rawKeys.embedding || ''
    localEmbedding.model = store.state.embedding.model || ''
    localLLM.base_url = store.state.llm.base_url || ''
    localLLM.api_key = store.state.rawKeys.llm || ''
    localLLM.model = store.state.llm.model || ''
  }
})

function onClose() {
  emit('close')
}

async function handleTest(type) {
  const cfg = type === 'embedding' ? localEmbedding : localLLM
  await store.testConnection(type, cfg.base_url, cfg.api_key, cfg.model)
}

async function handleSave() {
  const emb = { ...localEmbedding }
  const llm = { ...localLLM }
  // Only send api_key if user entered one (otherwise keep existing)
  if (!emb.api_key) delete emb.api_key
  if (!llm.api_key) delete llm.api_key
  await store.saveConfig(emb, llm)
}

async function handleReset() {
  await store.resetConfig()
  // Reload local state from fresh config
  localEmbedding.base_url = store.state.embedding.base_url || ''
  localEmbedding.api_key = ''
  localEmbedding.model = store.state.embedding.model || ''
  localLLM.base_url = store.state.llm.base_url || ''
  localLLM.api_key = ''
  localLLM.model = store.state.llm.model || ''
}
</script>

<style scoped>
.panel-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(2px);
}

.panel {
  width: 540px;
  max-width: calc(100vw - 48px);
  max-height: calc(100vh - 48px);
  background: var(--p-surface);
  border-radius: var(--r-lg);
  box-shadow: 0 20px 60px rgba(15, 23, 42, 0.18);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--p-border);
  flex-shrink: 0;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--p-text);
}

.close-btn {
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
  transition: all 0.15s ease;
}

.close-btn:hover {
  background: var(--p-surface-muted);
  color: var(--p-text);
}

.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.section-divider {
  height: 1px;
  background: var(--p-border);
  margin: 20px 0;
}

.panel-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  border-top: 1px solid var(--p-border);
  background: var(--p-surface-subtle);
  flex-shrink: 0;
  gap: 12px;
}

.footer-messages {
  flex: 1;
  min-width: 0;
}

.msg-success {
  font-size: 12px;
  color: var(--p-success);
  font-weight: 500;
}

.msg-error {
  font-size: 12px;
  color: var(--p-error);
  font-weight: 500;
}

.footer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  font-size: 13px;
  font-weight: 500;
  border-radius: var(--r-sm);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--p-primary);
  color: #fff;
  border-color: var(--p-primary);
}

.btn-primary:hover:not(:disabled) {
  background: var(--p-primary-hover);
}

.btn-outline {
  background: var(--p-surface);
  color: var(--p-text-secondary);
  border-color: var(--p-border);
}

.btn-outline:hover:not(:disabled) {
  border-color: var(--p-text-muted);
  color: var(--p-text);
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.spin {
  animation: spin 1s linear infinite;
}

/* Transition */
.panel-enter-active,
.panel-leave-active {
  transition: opacity 0.2s ease;
}

.panel-enter-active .panel,
.panel-leave-active .panel {
  transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.2s ease;
}

.panel-enter-from,
.panel-leave-to {
  opacity: 0;
}

.panel-enter-from .panel {
  transform: scale(0.95) translateY(8px);
  opacity: 0;
}

.panel-leave-to .panel {
  transform: scale(0.97);
  opacity: 0;
}
</style>
