<template>
  <div v-if="show" class="dialog-overlay" @click.self="$emit('close')">
    <div class="dialog-content">
      <div class="dialog-header">
        <h3>📤 上传新文档</h3>
        <button class="btn-close" @click="$emit('close')">&times;</button>
      </div>

      <div class="dialog-body">
        <input
          v-model="title"
          placeholder="文档标题（可选）"
          class="input"
          :disabled="uploading"
        />
        <textarea
          v-model="text"
          placeholder="粘贴 Markdown / 纯文本..."
          rows="8"
          class="textarea"
          :disabled="uploading"
        ></textarea>

        <p v-if="error" class="error-msg">{{ error }}</p>

        <div class="dialog-actions">
          <button class="btn btn-cancel" @click="$emit('close')" :disabled="uploading">
            取消
          </button>
          <button
            class="btn btn-primary"
            @click="onUpload"
            :disabled="uploading || !text.trim()"
          >
            {{ uploading ? '处理中...' : '上传并处理' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  show: { type: Boolean, default: false },
  uploading: { type: Boolean, default: false },
})

const emit = defineEmits(['close', 'upload'])

const title = ref('')
const text = ref('')
const error = ref('')

watch(() => props.show, (val) => {
  if (val) {
    title.value = ''
    text.value = ''
    error.value = ''
  }
})

function onUpload() {
  if (!text.value.trim()) return
  emit('upload', { title: title.value.trim(), text: text.value.trim() })
}

function setError(msg) {
  error.value = msg
}

defineExpose({ setError })
</script>

<style scoped>
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.dialog-content {
  width: 520px;
  max-width: 90vw;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
  overflow: hidden;
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #e5e7eb;
}

.dialog-header h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
}

.btn-close {
  background: none;
  border: none;
  font-size: 22px;
  color: #9ca3af;
  cursor: pointer;
  padding: 0 4px;
}
.btn-close:hover {
  color: #374151;
}

.dialog-body {
  padding: 20px;
}

.input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  margin-bottom: 12px;
  box-sizing: border-box;
  font-size: 14px;
  outline: none;
}
.input:focus {
  border-color: #3b82f6;
}

.textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  resize: vertical;
  box-sizing: border-box;
  font-size: 14px;
  font-family: inherit;
  outline: none;
}
.textarea:focus {
  border-color: #3b82f6;
}

.error-msg {
  color: #b91c1c;
  font-size: 13px;
  margin: 8px 0 0;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 16px;
}

.btn {
  padding: 8px 20px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-cancel {
  background: #e5e7eb;
  color: #374151;
}
.btn-cancel:hover:not(:disabled) {
  background: #d1d5db;
}

.btn-primary {
  background: #3b82f6;
  color: #fff;
}
.btn-primary:hover:not(:disabled) {
  background: #2563eb;
}
</style>
