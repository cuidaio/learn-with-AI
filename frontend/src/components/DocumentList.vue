<template>
  <aside class="doc-list-panel">
    <div class="panel-header">
      <h2 class="panel-title">📚 我的资料库</h2>
    </div>

    <div class="doc-list" v-if="documents.length > 0">
      <div
        v-for="doc in documents"
        :key="doc.id"
        class="doc-item"
        :class="{ selected: isSelected(doc.id) }"
        @click="onToggle(doc.id)"
      >
        <input
          type="checkbox"
          :checked="isSelected(doc.id)"
          class="doc-checkbox"
          @click.stop="onToggle(doc.id)"
        />
        <div class="doc-info">
          <span class="doc-title">{{ doc.title }}</span>
          <div class="doc-meta">
            <span :class="'badge badge-' + doc.status">{{ statusLabel(doc.status) }}</span>
            <span class="doc-count">{{ doc.total_sub_chunks }} 子块</span>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="loading" class="empty-state">加载中...</div>
    <div v-else class="empty-state">暂无文档，点击下方按钮上传</div>

    <div class="panel-footer">
      <button class="btn btn-upload" @click="$emit('upload')">📤 上传新文档</button>
      <div class="selected-stats" v-if="selectedIds.length > 0">
        已选 {{ selectedIds.length }} 个文档
      </div>
    </div>
  </aside>
</template>

<script setup>
const props = defineProps({
  documents: { type: Array, default: () => [] },
  selectedIds: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['toggle', 'upload'])

function isSelected(id) {
  return props.selectedIds.includes(id)
}

function onToggle(id) {
  emit('toggle', id)
}

function statusLabel(status) {
  const map = { completed: '已完成', processing: '处理中', failed: '失败', pending: '等待' }
  return map[status] || status
}
</script>

<style scoped>
.doc-list-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
  border-right: 1px solid #e5e7eb;
  overflow: hidden;
}

.panel-header {
  padding: 20px 16px 12px;
  border-bottom: 1px solid #f0f0f0;
}

.panel-title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
}

.doc-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.doc-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 16px;
  cursor: pointer;
  transition: background 0.15s;
}
.doc-item:hover {
  background: #f8f9fa;
}
.doc-item.selected {
  background: #eff6ff;
}

.doc-checkbox {
  margin-top: 3px;
  flex-shrink: 0;
}

.doc-info {
  flex: 1;
  min-width: 0;
}

.doc-title {
  display: block;
  font-size: 14px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  font-size: 12px;
}

.badge {
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 10px;
}
.badge-completed { background: #dcfce7; color: #15803d; }
.badge-processing { background: #fef9c3; color: #a16207; }
.badge-failed { background: #fee2e2; color: #b91c1c; }
.badge-pending { background: #e5e7eb; color: #4b5563; }

.doc-count {
  color: #9ca3af;
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9ca3af;
  font-size: 14px;
  padding: 20px;
}

.panel-footer {
  padding: 12px 16px;
  border-top: 1px solid #e5e7eb;
}

.btn-upload {
  width: 100%;
  padding: 10px;
  border: 1px dashed #3b82f6;
  border-radius: 8px;
  background: #f0f7ff;
  color: #2563eb;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-upload:hover {
  background: #dbeafe;
}

.selected-stats {
  text-align: center;
  font-size: 12px;
  color: #6b7280;
  margin-top: 8px;
}
</style>
