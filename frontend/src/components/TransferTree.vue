<template>
  <div class="transfer-tree">
    <!-- 左侧：知识树 -->
    <div class="tt-left">
      <div class="tt-header">
        <span class="tt-header-title">{{ leftTitle }}</span>
        <span class="tt-header-count">{{ leafCount(treeData) }} 个</span>
      </div>
      <div class="tt-search">
        <span class="tt-search-icon">🔍</span>
        <input
          v-model="searchQuery"
          class="tt-search-input"
          :placeholder="placeholder"
        />
      </div>
      <div class="tt-tree-scroll">
        <TreeSubNode
          v-for="node in filteredTree"
          :key="node.id"
          :node="node"
          :depth="0"
          :pending-set="pendingSet"
          :selected-set="selectedSet"
          :expanded-set="expandedSet"
          @toggle-expand="toggleExpand"
          @toggle-check="toggleCheck"
        />
        <div v-if="filteredTree.length === 0" class="tt-empty">
          {{ searchQuery ? '无匹配结果' : '暂无知识点' }}
        </div>
      </div>
    </div>

    <!-- 中间：操作按钮 -->
    <div class="tt-actions">
      <button
        class="tt-btn tt-btn-add"
        :disabled="pendingSet.size === 0"
        title="添加到已选"
        @click="moveToRight"
      >
        →
      </button>
      <button
        class="tt-btn tt-btn-remove"
        :disabled="selectedSet.size === 0"
        title="移回全部"
        @click="removeAll"
      >
        ←
      </button>
    </div>

    <!-- 右侧：已选列表 -->
    <div class="tt-right">
      <div class="tt-header">
        <span class="tt-header-title">{{ rightTitle }}</span>
        <span class="tt-header-count">{{ selectedSet.size }} 个</span>
      </div>
      <div class="tt-right-scroll">
        <div
          v-for="id in modelValue"
          :key="id"
          class="tt-right-item"
          :title="entityLabels[id] || id"
        >
          <span class="tt-right-label">{{ entityLabels[id] || id }}</span>
          <button class="tt-right-remove" @click="removeOne(id)" title="移出">✕</button>
        </div>
        <div v-if="modelValue.length === 0" class="tt-empty">暂无已选</div>
      </div>
      <div v-if="modelValue.length > 0" class="tt-right-footer">
        <button class="tt-clear-btn" @click="updateModelValue([])">清空全部</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import TreeSubNode from './TreeSubNode.vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  treeData: { type: Array, default: () => [] },
  leftTitle: { type: String, default: '全部知识点' },
  rightTitle: { type: String, default: '已选' },
  placeholder: { type: String, default: '搜索知识点...' },
})

const emit = defineEmits(['update:modelValue'])

// ── 内部状态 ──

const searchQuery = ref('')
const expandedSet = ref(new Set())
const pendingSet = ref(new Set())

// ── 派生 ──

const selectedSet = computed(() => new Set(props.modelValue))

const entityLabels = computed(() => {
  const map = {}
  function walk(nodes) {
    for (const n of nodes) {
      if (n.type === 'entity') map[n.id] = n.label
      if (n.children) walk(n.children)
    }
  }
  walk(props.treeData)
  return map
})

// ── 搜索过滤 ──

const filteredTree = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return props.treeData
  return filterTree(props.treeData, q)
})

function filterTree(nodes, q) {
  const result = []
  for (const n of nodes) {
    const labelMatch = n.label.toLowerCase().includes(q)
    const matchedChildren = n.children ? filterTree(n.children, q) : []
    if (labelMatch || matchedChildren.length > 0) {
      result.push({
        ...n,
        children: n.children ? matchedChildren : undefined,
        _match: labelMatch,
      })
    }
  }
  return result
}

function leafCount(nodes) {
  let c = 0
  for (const n of nodes) {
    if (n.type === 'entity') c++
    if (n.children) c += leafCount(n.children)
  }
  return c
}

// ── 辅助 ──

function collectEntityIds(node) {
  const ids = []
  if (node.type === 'entity') ids.push(node.id)
  if (node.children) for (const c of node.children) ids.push(...collectEntityIds(c))
  return ids
}

// ── 展开/折叠 ──

function toggleExpand(id) {
  const s = new Set(expandedSet.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  expandedSet.value = s
}

// ── 勾选（左树） ──

function toggleCheck(node) {
  const ids = collectEntityIds(node)
  const s = new Set(pendingSet.value)
  const selectable = ids.filter(id => !selectedSet.value.has(id))
  const allSelected = selectable.every(id => s.has(id))
  if (allSelected) {
    for (const id of selectable) s.delete(id)
  } else {
    for (const id of selectable) s.add(id)
  }
  pendingSet.value = s
}

// ── 转移到右侧 ──

function moveToRight() {
  if (pendingSet.value.size === 0) return
  const current = new Set(props.modelValue)
  for (const id of pendingSet.value) current.add(id)
  updateModelValue(Array.from(current))
  pendingSet.value = new Set()
}

// ── 移除 ──

function removeOne(id) {
  updateModelValue(props.modelValue.filter(v => v !== id))
}

function removeAll() {
  updateModelValue([])
}

function updateModelValue(val) {
  emit('update:modelValue', val)
}
</script>

<style scoped>
.transfer-tree {
  display: flex;
  gap: 8px;
  height: 260px;
}

.tt-left,
.tt-right {
  flex: 1;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--p-border);
  border-radius: var(--r-md);
  background: var(--p-surface);
  overflow: hidden;
}

.tt-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-bottom: 1px solid var(--p-border);
  flex-shrink: 0;
}

.tt-header-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--p-text);
}

.tt-header-count {
  font-size: 11px;
  color: var(--p-text-muted);
}

.tt-search {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 8px;
  border-bottom: 1px solid var(--p-border);
  flex-shrink: 0;
}

.tt-search-icon {
  font-size: 12px;
  opacity: 0.5;
}

.tt-search-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 12px;
  color: var(--p-text);
  background: transparent;
}

.tt-search-input::placeholder {
  color: var(--p-text-muted);
}

.tt-tree-scroll,
.tt-right-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}

.tt-right-scroll {
  padding: 6px 8px;
}

.tt-empty {
  text-align: center;
  color: var(--p-text-muted);
  font-size: 12px;
  padding: 24px 12px;
}

.tt-actions {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  flex-shrink: 0;
  padding: 0 2px;
}

.tt-btn {
  width: 32px;
  height: 32px;
  border: 1px solid var(--p-border);
  border-radius: var(--r-md);
  background: var(--p-surface);
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--p-text-secondary);
  transition: all 0.1s ease;
}

.tt-btn:hover:not(:disabled) {
  border-color: var(--p-primary);
  color: var(--p-primary);
  background: var(--p-primary-light);
}

.tt-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.tt-right-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 6px;
  border-radius: var(--r-sm);
  font-size: 12px;
  color: var(--p-text-secondary);
  transition: background 0.08s ease;
}

.tt-right-item:hover {
  background: var(--p-surface-muted);
}

.tt-right-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tt-right-remove {
  width: 18px;
  height: 18px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 11px;
  color: var(--p-text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  visibility: hidden;
  flex-shrink: 0;
}

.tt-right-item:hover .tt-right-remove {
  visibility: visible;
}

.tt-right-remove:hover {
  background: #fef2f2;
  color: #dc2626;
}

.tt-right-footer {
  flex-shrink: 0;
  padding: 6px 8px;
  border-top: 1px solid var(--p-border);
}

.tt-clear-btn {
  width: 100%;
  padding: 4px 0;
  border: 1px dashed var(--p-border);
  border-radius: var(--r-sm);
  background: transparent;
  cursor: pointer;
  font-size: 11px;
  color: var(--p-text-muted);
  transition: all 0.1s ease;
}

.tt-clear-btn:hover {
  border-color: #fecaca;
  color: #dc2626;
  background: #fef2f2;
}

.tt-tree-scroll::-webkit-scrollbar,
.tt-right-scroll::-webkit-scrollbar {
  width: 3px;
}

.tt-tree-scroll::-webkit-scrollbar-thumb,
.tt-right-scroll::-webkit-scrollbar-thumb {
  background: transparent;
  border-radius: 2px;
}

.tt-tree-scroll:hover::-webkit-scrollbar-thumb,
.tt-right-scroll:hover::-webkit-scrollbar-thumb {
  background: var(--p-border);
}
</style>
