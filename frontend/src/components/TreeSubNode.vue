<template>
  <div class="tsn-wrapper" :class="{ 'tsn-match': node._match }">
    <div
      class="tsn-row"
      :class="{ 'tsn-row-folder': node.type === 'folder', 'tsn-row-entity': node.type === 'entity' }"
      :style="{ paddingLeft: depth * 16 + 8 + 'px' }"
    >
      <!-- 展开/折叠 (仅 folder) -->
      <span
        v-if="node.children && node.children.length > 0"
        class="tsn-expand"
        @click="$emit('toggleExpand', node.id)"
      >
        {{ expandedSet.has(node.id) ? '▾' : '▸' }}
      </span>
      <span v-else class="tsn-expand tsn-expand-spacer" />

      <!-- 复选框 – entity -->
      <span
        v-if="node.type === 'entity'"
        :class="['tsn-check', { 'tsn-check-disabled': selectedSet.has(node.id) }]"
        @click="selectedSet.has(node.id) ? null : $emit('toggleCheck', node)"
      >
        {{ selectedSet.has(node.id) ? '✅' : pendingSet.has(node.id) ? '☑' : '☐' }}
      </span>

      <!-- 复选框 – folder (三态) -->
      <span
        v-else
        class="tsn-check tsn-check-folder"
        @click="$emit('toggleCheck', node)"
      >
        {{ folderIcon }}
      </span>

      <!-- 标签 -->
      <span
        :class="['tsn-label', {
          'tsn-label-selected': selectedSet.has(node.id),
          'tsn-label-highlight': node._match,
        }]"
        @click="node.children && node.children.length > 0 ? $emit('toggleExpand', node.id) : $emit('toggleCheck', node)"
      >
        {{ node.label }}
        <span v-if="node.type === 'folder' && node.children" class="tsn-count">
          ({{ node.children.length }})
        </span>
      </span>
    </div>

    <!-- 子节点 -->
    <div v-if="node.children && expandedSet.has(node.id)" class="tsn-children">
      <TreeSubNode
        v-for="child in node.children"
        :key="child.id"
        :node="child"
        :depth="depth + 1"
        :pending-set="pendingSet"
        :selected-set="selectedSet"
        :expanded-set="expandedSet"
        @toggle-expand="$emit('toggleExpand', $event)"
        @toggle-check="$emit('toggleCheck', $event)"
      />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  node: Object,
  depth: { type: Number, default: 0 },
  pendingSet: { type: Set, required: true },
  selectedSet: { type: Set, required: true },
  expandedSet: { type: Set, required: true },
})

defineEmits(['toggleExpand', 'toggleCheck'])

function collectEntityIds(node) {
  const ids = []
  if (node.type === 'entity') ids.push(node.id)
  if (node.children) for (const c of node.children) ids.push(...collectEntityIds(c))
  return ids
}

const folderIcon = computed(() => {
  const ids = collectEntityIds(props.node)
  const selectable = ids.filter(id => !props.selectedSet.has(id))
  if (selectable.length === 0) return '☑'
  const checked = selectable.filter(id => props.pendingSet.has(id))
  if (checked.length === 0) return '☐'
  if (checked.length === selectable.length) return '☑'
  return '☒'
})
</script>

<style scoped>
.tsn-wrapper {
  user-select: none;
}

.tsn-row {
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 3px 8px 3px 0;
  cursor: pointer;
  border-radius: var(--r-sm);
  transition: background 0.08s ease;
  font-size: 12px;
}

.tsn-row:hover {
  background: var(--p-surface-muted);
}

.tsn-row-folder {
  font-weight: 500;
  color: var(--p-text);
}

.tsn-row-entity {
  color: var(--p-text-secondary);
}

.tsn-expand {
  width: 14px;
  flex-shrink: 0;
  font-size: 10px;
  color: var(--p-text-muted);
  text-align: center;
}

.tsn-expand-spacer {
  visibility: hidden;
}

.tsn-count {
  font-weight: 400;
  color: var(--p-text-muted);
  font-size: 11px;
}

.tsn-check {
  font-size: 13px;
  flex-shrink: 0;
  user-select: none;
  line-height: 1;
}

.tsn-check-folder {
  opacity: 0.8;
}

.tsn-check-disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.tsn-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tsn-label-selected {
  text-decoration: line-through;
  opacity: 0.5;
}

.tsn-label-highlight {
  font-weight: 600;
  color: var(--p-primary);
}

.tsn-children {
  /* indent via padding on rows */
}
</style>
