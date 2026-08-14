<template>
  <div v-if="visible" class="conflict-overlay" @click.self="$emit('cancel')">
    <div class="conflict-dialog">
      <div class="conflict-header">
        <span class="conflict-icon">⚠️</span>
        <span class="conflict-title">文件已存在</span>
      </div>
      <p class="conflict-msg">{{ message }}</p>
      <div class="conflict-options">
        <label class="conflict-option" :class="{ selected: selected === 'rename' }">
          <input type="radio" v-model="selected" value="rename" />
          <span class="option-text">自动重命名 → <strong>{{ suggestedTitle }}</strong></span>
        </label>
        <label class="conflict-option" :class="{ selected: selected === 'overwrite' }">
          <input type="radio" v-model="selected" value="overwrite" />
          <span class="option-text">覆盖现有文件</span>
        </label>
        <label class="conflict-option" :class="{ selected: selected === 'cancel' }">
          <input type="radio" v-model="selected" value="cancel" />
          <span class="option-text">取消上传</span>
        </label>
      </div>
      <div class="conflict-actions">
        <button class="btn btn-cancel" @click="$emit('cancel')">取消</button>
        <button class="btn btn-primary" @click="confirm">确认</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  message: { type: String, default: '' },
  suggestedTitle: { type: String, default: '' },
})

const emit = defineEmits(['cancel', 'resolve'])
const selected = ref('rename')

function confirm() {
  emit('resolve', selected.value)
}
</script>

<style scoped>
.conflict-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.5);
  backdrop-filter: blur(2px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 110;
}

.conflict-dialog {
  background: var(--p-surface);
  border-radius: var(--r-xl);
  width: 420px;
  max-width: 90vw;
  padding: 24px;
  box-shadow: var(--shadow-lg);
}

.conflict-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.conflict-icon {
  font-size: 20px;
}

.conflict-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--p-text);
}

.conflict-msg {
  font-size: 13px;
  color: var(--p-text-secondary);
  margin-bottom: 16px;
  line-height: 1.5;
}

.conflict-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 20px;
}

.conflict-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid var(--p-border);
  border-radius: var(--r-md);
  cursor: pointer;
  transition: all 0.1s;
  font-size: 13px;
  color: var(--p-text-secondary);
}

.conflict-option:hover {
  border-color: #cbd5e1;
}

.conflict-option.selected {
  border-color: var(--p-primary);
  background: var(--p-primary-light);
  color: var(--p-text);
}

.option-text { line-height: 1.4; }

.conflict-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.btn {
  padding: 8px 20px;
  border-radius: var(--r-md);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid transparent;
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
</style>