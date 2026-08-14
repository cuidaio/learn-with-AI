<template>
  <div v-if="docStore.state.showUploadDialog" class="dialog-overlay" @click.self="close">
    <div class="dialog">
      <div class="dialog-header">
        <h3>上传文档</h3>
        <button class="close-btn" @click="close">✕</button>
      </div>
      <div class="dialog-body">
        <!-- 拖放区 -->
        <div
          :class="['dropzone', { 'dropzone-active': isDragging }]"
          @dragover.prevent="isDragging = true"
          @dragleave.prevent="isDragging = false"
          @drop.prevent="onFileDrop"
          @click="triggerFileInput"
        >
          <div class="dropzone-icon">📤</div>
          <p class="dropzone-text">拖放文件到此处</p>
          <p class="dropzone-hint">或点击选择文件</p>
          <p class="dropzone-formats">支持 .txt .md</p>
          <input
            ref="fileInputRef"
            type="file"
            accept=".txt,.md,text/plain"
            class="file-input-hidden"
            @change="onFileSelect"
          />
        </div>

        <div class="field">
          <label>标题</label>
          <input
            v-model="localTitle"
            type="text"
            placeholder="文档标题（自动从文件名填充）"
            class="input"
          />
        </div>
        <div class="field">
          <label>正文</label>
          <textarea
            v-model="localText"
            placeholder="在此粘贴教材原文..."
            class="textarea"
            rows="12"
          ></textarea>
        </div>
      </div>
      <div class="dialog-footer">
        <button class="btn btn-cancel" @click="close">取消</button>
        <button class="btn btn-primary" :disabled="isUploading" @click="upload">
          {{ isUploading ? '上传中...' : '确认上传' }}
        </button>
      </div>
    </div>

    <!-- 重名冲突处理 -->
    <ConflictDialog
      :visible="conflictVisible"
      :message="conflictMessage"
      :suggestedTitle="conflictSuggestedTitle"
      @cancel="conflictVisible = false"
      @resolve="onConflictResolve"
    />
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useDocumentStore } from '../../stores/useDocumentStore'
import { useLearningStore } from '../../stores/useLearningStore'
import ConflictDialog from './ConflictDialog.vue'

const API_BASE = ''

const docStore = useDocumentStore()
const learningStore = useLearningStore()

const isDragging = ref(false)
const isUploading = ref(false)
const fileInputRef = ref(null)

// 本地状态（不从 store 读取，避免冲突）
const localTitle = ref('')
const localText = ref('')

// 重名冲突状态
const conflictVisible = ref(false)
const conflictMessage = ref('')
const conflictSuggestedTitle = ref('')
const pendingUpload = ref(null) // 保存上传参数用于重试

// 当 dialog 打开时重置
watch(() => docStore.state.showUploadDialog, (v) => {
  if (v) {
    localTitle.value = ''
    localText.value = ''
    conflictVisible.value = false
    pendingUpload.value = null
  }
})

function close() {
  docStore.state.showUploadDialog = false
}

function triggerFileInput() {
  fileInputRef.value?.click()
}

function onFileDrop(e) {
  isDragging.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) handleFile(file)
}

function onFileSelect(e) {
  const file = e.target?.files?.[0]
  if (file) handleFile(file)
  e.target.value = '' // 允许重复选择同文件
}

function handleFile(file) {
  // 自动生成标题：去扩展名
  const name = file.name.replace(/\.[^.]+$/, '')
  localTitle.value = name

  const reader = new FileReader()
  reader.onload = (e) => {
    localText.value = e.target?.result || ''
  }
  reader.readAsText(file, 'UTF-8')
}

async function upload() {
  const title = localTitle.value.trim()
  const text = localText.value.trim()
  if (!text) return
  isUploading.value = true
  conflictVisible.value = false
  pendingUpload.value = { title, text }

  try {
    const res = await fetch(`${API_BASE}/api/documents`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, raw_text: text }),
    })

    if (res.status === 409) {
      // 重名冲突
      const err = await res.json().catch(() => ({}))
      const detail = err.detail || {}
      conflictMessage.value = detail.message || `文档「${title}」已存在`
      conflictSuggestedTitle.value = detail.suggested_title || `${title} (2)`
      conflictVisible.value = true
      return
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      alert('上传失败：' + (err.detail || res.statusText))
      return
    }

    const data = await res.json()
    localTitle.value = ''
    localText.value = ''
    docStore.state.showUploadDialog = false
    await docStore.fetchAll()
    await learningStore.record('document_uploaded', {
      document_id: data.document_id,
      context: { title },
    })
  } catch (e) {
    alert('上传请求失败：' + e.message)
  } finally {
    isUploading.value = false
  }
}

async function onConflictResolve(action) {
  conflictVisible.value = false
  if (action === 'cancel') return

  const params = pendingUpload.value
  if (!params) return

  if (action === 'rename') {
    // 使用建议标题重试
    localTitle.value = conflictSuggestedTitle.value
    pendingUpload.value.title = conflictSuggestedTitle.value
    await upload()
  } else if (action === 'overwrite') {
    // 覆盖：先删除现有文档，再上传
    try {
      // 需要找到现有的文档 ID
      const listRes = await fetch(`${API_BASE}/api/documents`)
      if (listRes.ok) {
        const listData = await listRes.json()
        const existing = listData.documents?.find(d => d.title === params.title)
        if (existing) {
          await fetch(`${API_BASE}/api/documents/${existing.id}`, { method: 'DELETE' })
        }
      }
    } catch { /* ignore */ }
    await upload()
  }
}
</script>

<style scoped>
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.dialog {
  background: var(--p-surface);
  border-radius: var(--r-xl);
  width: 600px;
  max-width: 90vw;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-lg);
  animation: dialogIn 0.18s ease-out;
}

@keyframes dialogIn {
  from { opacity: 0; transform: translateY(8px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 24px;
  border-bottom: 1px solid var(--p-border);
}

.dialog-header h3 {
  font-size: 15px;
  font-weight: 600;
  color: var(--p-text);
  margin: 0;
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

.dialog-body {
  padding: 20px 24px;
  overflow-y: auto;
  flex: 1;
}

/* ── 拖放区 ── */

.dropzone {
  border: 2px dashed var(--p-border);
  border-radius: var(--r-lg);
  padding: 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.15s;
  margin-bottom: 20px;
  background: var(--p-surface-subtle);
}

.dropzone:hover,
.dropzone-active {
  border-color: var(--p-primary);
  background: var(--p-primary-light);
}

.dropzone-icon {
  font-size: 32px;
  margin-bottom: 6px;
}

.dropzone-text {
  font-size: 14px;
  font-weight: 500;
  color: var(--p-text-secondary);
  margin-bottom: 2px;
}

.dropzone-hint {
  font-size: 12px;
  color: var(--p-text-muted);
}

.dropzone-formats {
  font-size: 11px;
  color: var(--p-text-muted);
  margin-top: 6px;
}

.file-input-hidden {
  display: none;
}

/* ── 表单字段 ── */

.field {
  margin-bottom: 16px;
}

.field label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--p-text-secondary);
  margin-bottom: 6px;
  letter-spacing: 0.01em;
  text-transform: uppercase;
}

.input {
  width: 100%;
  padding: 9px 12px;
  border: 1px solid var(--p-border);
  border-radius: var(--r-md);
  font-size: 14px;
  color: var(--p-text);
  background: var(--p-surface);
  outline: none;
  box-sizing: border-box;
}

.input:focus {
  border-color: var(--p-primary);
  box-shadow: 0 0 0 3px rgba(79, 106, 240, 0.12);
}

.textarea {
  width: 100%;
  padding: 9px 12px;
  border: 1px solid var(--p-border);
  border-radius: var(--r-md);
  font-size: 13px;
  color: var(--p-text);
  background: var(--p-surface);
  resize: vertical;
  font-family: inherit;
  line-height: 1.6;
  outline: none;
  box-sizing: border-box;
}

.textarea:focus {
  border-color: var(--p-primary);
  box-shadow: 0 0 0 3px rgba(79, 106, 240, 0.12);
}

.textarea::placeholder, .input::placeholder {
  color: var(--p-text-muted);
}

.dialog-footer {
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
</style>