<template>
  <div class="content-renderer">
    <!-- 空状态 -->
    <div v-if="!hasTabs && !contentStore.state.isLoading" class="empty-state">
      <div class="empty-icon">📚</div>
      <p class="empty-text">从左侧选中文档开始学习</p>
      <p class="empty-hint">或点击右栏中的快捷操作</p>
    </div>

    <!-- 加载中 -->
    <div v-else-if="contentStore.state.isLoading" class="loading-state">
      加载中...
    </div>

    <!-- 标签页 + 内容 -->
    <div v-else-if="hasTabs" class="content-area">
      <TabBar
        :tabs="contentStore.state.tabs"
        :activeTabId="contentStore.state.activeTabId"
        @activate="contentStore.activateTab"
        @close="contentStore.closeTab"
        @add="openNewTab"
      />

      <div class="content-body">
        <keep-alive>
          <component :is="renderer" />
        </keep-alive>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, shallowRef, watch } from 'vue'
import { useContentStore } from '../../stores/useContentStore'
import { getRenderer } from '../../registry/RendererRegistry'
import TabBar from './TabBar.vue'

const contentStore = useContentStore()

const hasTabs = computed(() => contentStore.state.tabs.length > 0)

function openNewTab() {
  contentStore.setChat()
}

const renderer = shallowRef(null)

watch(() => contentStore.state.contentType, (type) => {
  renderer.value = type ? getRenderer(type) : null
}, { immediate: true })
</script>

<style scoped>
.content-renderer {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px;
}

.empty-icon {
  font-size: 44px;
  opacity: 0.6;
  margin-bottom: 4px;
}

.empty-text {
  font-size: 15px;
  color: var(--p-text-secondary);
  font-weight: 500;
}

.empty-hint {
  font-size: 13px;
  color: var(--p-text-muted);
}

.loading-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--p-text-muted);
  font-size: 14px;
  gap: 8px;
}

.loading-state::after {
  content: '';
  width: 16px;
  height: 16px;
  border: 2px solid var(--p-border);
  border-top-color: var(--p-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.content-area {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.content-body {
  flex: 1;
  min-height: 0;
  position: relative;
}
</style>
