<template>
  <div class="app">
    <div class="layout">
      <!-- 左栏：文档区 ~20% -->
      <div class="pane pane-left">
        <DocumentTree />
      </div>

      <!-- 中栏：呈现区 ~55% -->
      <div class="pane pane-middle">
        <ContentRenderer />
      </div>

      <!-- 右栏：任务区 ~25% -->
      <div class="pane pane-right">
        <TaskEntry />
        <QuickActions />
        <TaskStack />
      </div>
    </div>

    <!-- Upload Dialog -->
    <UploadDialog />
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useDocumentStore } from '../stores/useDocumentStore'
import DocumentTree from '../components/LeftPanel/DocumentTree.vue'
import UploadDialog from '../components/LeftPanel/UploadDialog.vue'
import ContentRenderer from '../components/MiddlePanel/ContentRenderer.vue'
import TaskEntry from '../components/RightPanel/TaskEntry.vue'
import QuickActions from '../components/RightPanel/QuickActions.vue'
import TaskStack from '../components/RightPanel/TaskStack.vue'

const docStore = useDocumentStore()

onMounted(async () => {
  await docStore.fetchAll()
})
</script>

<style scoped>
.app {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--p-surface-muted);
}

.layout {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.pane {
  height: 100%;
  overflow-y: auto;
}

.pane-left {
  width: 20%;
  min-width: 220px;
  max-width: 300px;
  background: var(--p-surface);
  border-right: 1px solid var(--p-border);
}

.pane-middle {
  flex: 1;
  background: var(--p-surface);
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-xs);
  z-index: 1;
}

.pane-right {
  width: 25%;
  min-width: 260px;
  max-width: 380px;
  background: var(--p-surface-subtle);
  border-left: 1px solid var(--p-border);
  display: flex;
  flex-direction: column;
}

/* 隐藏 pane 滚动条，保持整洁 */
.pane::-webkit-scrollbar {
  width: 4px;
}
.pane::-webkit-scrollbar-thumb {
  background: transparent;
  border-radius: 2px;
}
.pane:hover::-webkit-scrollbar-thumb {
  background: var(--p-border);
}
</style>
