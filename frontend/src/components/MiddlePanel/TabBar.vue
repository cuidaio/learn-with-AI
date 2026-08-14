<template>
  <div class="tab-bar" ref="barRef">
    <div class="tab-list" ref="tabListRef">
      <div
        v-for="tab in tabs"
        :key="tab.id"
        :ref="(el) => { if (el) tabRefs[tab.id] = el }"
        :class="['tab-item', { active: tab.id === activeTabId }]"
        @click="$emit('activate', tab.id)"
        @mousedown.middle.prevent="$emit('close', tab.id)"
        :title="tab.title"
      >
        <span class="tab-icon">{{ iconFor(tab.contentType) }}</span>
        <span class="tab-title">{{ tab.title }}</span>
        <button
          v-if="tabs.length > 1 && shouldShowClose(tab.id)"
          class="tab-close"
          @click.stop="$emit('close', tab.id)"
          title="关闭标签页"
        >✕</button>
      </div>
    </div>
    <button class="tab-add" title="新标签页" @click="$emit('add')">+</button>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  tabs: { type: Array, required: true },
  activeTabId: { type: String, default: null },
})
defineEmits(['activate', 'close', 'add'])

const barRef = ref(null)
const tabRefs = ref({})

function iconFor(type) {
  const map = { document: '📄', chat: '💬', entities: '🏷️', questions: '📝', knowledge_graph: '📊' }
  return map[type] || '📄'
}

/** 判断是否显示关闭按钮：窗口足够宽 or 当前激活 tab */
function shouldShowClose(tabId) {
  const bar = barRef.value
  if (!bar) return tabId === props.activeTabId
  const totalWidth = bar.offsetWidth
  // 窗口较宽（> 每个tab约80px）或当前激活tab → 显示 ×
  const avgWidth = props.tabs.length > 0 ? totalWidth / props.tabs.length : 80
  return avgWidth > 60 || tabId === props.activeTabId
}
</script>

<style scoped>
.tab-bar {
  display: flex;
  align-items: center;
  background: var(--p-surface-subtle);
  border-bottom: 1px solid var(--p-border);
  flex-shrink: 0;
  height: 34px;
  padding: 0 4px;
  user-select: none;
}

.tab-list {
  display: flex;
  align-items: stretch;
  flex: 1;
  overflow-x: auto;
  overflow-y: hidden;
  gap: 1px;
  scrollbar-width: none;
  min-width: 0;
}

.tab-list::-webkit-scrollbar { display: none; }

.tab-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 6px 3px 8px;
  font-size: 12px;
  color: var(--p-text-secondary);
  border-radius: var(--r-sm) var(--r-sm) 0 0;
  cursor: pointer;
  white-space: nowrap;
  border: 1px solid transparent;
  border-bottom: none;
  margin-top: 2px;
  transition: background 0.1s, color 0.1s;
  min-width: 60px;
  max-width: 200px;
  flex: 0 1 150px;
}

.tab-item:hover {
  background: var(--p-surface);
  color: var(--p-text);
}

.tab-item.active {
  background: var(--p-surface);
  color: var(--p-text);
  font-weight: 500;
  border-color: var(--p-border);
  border-bottom-color: var(--p-surface);
  z-index: 1;
}

.tab-icon {
  font-size: 11px;
  flex-shrink: 0;
}

.tab-title {
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}

.tab-close {
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: 2px;
  font-size: 10px;
  color: var(--p-text-muted);
  cursor: pointer;
  padding: 0;
  flex-shrink: 0;
  transition: background 0.1s;
}

.tab-close:hover {
  background: var(--p-surface-muted);
  color: var(--p-text-secondary);
}

.tab-add {
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  color: var(--p-text-muted);
  background: none;
  border: none;
  border-radius: var(--r-sm);
  cursor: pointer;
  flex-shrink: 0;
  margin-left: 4px;
  transition: background 0.1s, color 0.1s;
}

.tab-add:hover {
  background: var(--p-surface);
  color: var(--p-text-secondary);
}
</style>