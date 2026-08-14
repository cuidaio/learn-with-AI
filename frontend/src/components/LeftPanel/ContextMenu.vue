<template>
  <teleport to="body">
    <div v-if="visible" class="ctx-overlay" @click.self="close" @contextmenu.prevent="close">
      <div class="ctx-menu" :style="{ left: x + 'px', top: y + 'px' }" @click.stop>
        <!-- 文档菜单 -->
        <template v-if="targetType === 'document'">
          <div class="ctx-item" @click="emitAction('rename')">
            <span class="ctx-icon">✏️</span>
            <span class="ctx-label">重命名</span>
          </div>
          <div class="ctx-item" @click="emitAction('delete')">
            <span class="ctx-icon">🗑️</span>
            <span class="ctx-label">删除</span>
          </div>
          <div class="ctx-divider"></div>
          <div
            v-for="folder in folders"
            :key="folder.id"
            :class="['ctx-item', { disabled: folder.id === currentFolderId }]"
            @click="moveToFolder(folder.id)"
          >
            <span class="ctx-icon">📂</span>
            <span class="ctx-label">移动到 {{ folder.name }}</span>
          </div>
          <div v-if="currentFolderId" class="ctx-item" @click="moveToFolder(null)">
            <span class="ctx-icon">📄</span>
            <span class="ctx-label">移出文件夹</span>
          </div>
        </template>
        <!-- 文件夹菜单 -->
        <template v-else-if="targetType === 'folder'">
          <div class="ctx-item" @click="emitAction('rename')">
            <span class="ctx-icon">✏️</span>
            <span class="ctx-label">重命名</span>
          </div>
          <div class="ctx-item" @click="emitAction('delete')">
            <span class="ctx-icon">🗑️</span>
            <span class="ctx-label">删除</span>
          </div>
        </template>
      </div>
    </div>
  </teleport>
</template>

<script setup>
const props = defineProps({
  visible: { type: Boolean, default: false },
  x: { type: Number, default: 0 },
  y: { type: Number, default: 0 },
  targetType: { type: String, default: 'document' }, // 'document' | 'folder'
  targetId: { type: String, default: null },
  documentId: { type: String, default: null },
  currentFolderId: { type: String, default: null },
  folders: { type: Array, default: () => [] },
})

const emit = defineEmits(['close', 'rename', 'delete', 'move-folder'])

function close() { emit('close') }

function emitAction(action) {
  const id = props.documentId || props.targetId
  if (id) emit(action, id)
  close()
}

function moveToFolder(folderId) {
  if (folderId === props.currentFolderId) return
  if (props.documentId) {
    emit('move-folder', { documentId: props.documentId, folderId })
  }
  close()
}
</script>

<style scoped>
.ctx-overlay {
  position: fixed;
  inset: 0;
  z-index: 200;
}

.ctx-menu {
  position: absolute;
  background: var(--p-surface);
  border: 1px solid var(--p-border);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-lg);
  min-width: 160px;
  padding: 4px 0;
  z-index: 201;
}

.ctx-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 14px;
  font-size: 13px;
  color: var(--p-text-secondary);
  cursor: pointer;
  transition: background 0.1s;
}

.ctx-item:hover { background: var(--p-surface-subtle); color: var(--p-text); }
.ctx-item.disabled { opacity: 0.4; cursor: default; }
.ctx-item.disabled:hover { background: transparent; }
.ctx-icon { font-size: 13px; flex-shrink: 0; }
.ctx-label { flex: 1; white-space: nowrap; }
.ctx-divider { height: 1px; background: var(--p-border); margin: 4px 0; }
</style>