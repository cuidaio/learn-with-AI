<template>
  <div class="quick-actions">
    <div class="qa-title">常驻快捷区</div>
    <div class="qa-item" @click="openChat">
      <span class="qa-icon">💬</span>
      <span class="qa-label">AI对话</span>
    </div>
    <div class="qa-item" @click="openEntities">
      <span class="qa-icon">📋</span>
      <span class="qa-label">实体一览</span>
    </div>
  </div>
</template>

<script setup>
import { useDocumentStore } from '../../stores/useDocumentStore'
import { useContentStore } from '../../stores/useContentStore'
import { useLearningStore } from '../../stores/useLearningStore'

const docStore = useDocumentStore()
const contentStore = useContentStore()
const learningStore = useLearningStore()

async function openChat() {
  const docId = docStore.state.selectedDocumentId
  if (!docId) {
    alert('请先选择一个文档')
    return
  }
  contentStore.setChat()
  await learningStore.record('quick_action_clicked', { context: { action_type: 'chat', document_id: docId } })
}

async function openEntities() {
  const docId = docStore.state.selectedDocumentId
  if (!docId) {
    alert('请先选择一个文档')
    return
  }
  await contentStore.loadEntities(docId)
  await learningStore.record('quick_action_clicked', { context: { action_type: 'entities', document_id: docId } })
}
</script>

<style scoped>
.quick-actions {
  padding: 6px 16px 10px;
  flex-shrink: 0;
  border-bottom: 1px solid var(--p-border);
}

.qa-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--p-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 8px;
  padding: 0 4px;
}

.qa-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: var(--r-md);
  cursor: pointer;
  transition: background 0.1s ease;
  margin-bottom: 3px;
}

.qa-item:hover {
  background: var(--p-surface-muted);
}

.qa-icon {
  font-size: 16px;
  opacity: 0.7;
}

.qa-label {
  font-size: 13px;
  color: var(--p-text-secondary);
  font-weight: 500;
}

.qa-item:hover .qa-label {
  color: var(--p-text);
}
</style>
