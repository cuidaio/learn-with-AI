<template>
  <div class="task-stack">
    <div class="stack-title">任务列表</div>

    <div v-if="!tasks.length" class="stack-empty">暂无任务</div>

    <div v-else class="stack-list">
      <TaskCard
        v-for="t in tasks"
        :key="t.task_id"
        :task-id="t.task_id"
        :initial-status="t"
        @deleted="onDeleted(t.task_id)"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, watch, onMounted, onUnmounted } from 'vue'
import { useDocumentStore } from '../../stores/useDocumentStore'
import { useTaskStore } from '../../stores/useTaskStore'
import TaskCard from './TaskCard.vue'

const docStore = useDocumentStore()
const taskStore = useTaskStore()
// 使用 taskStore.state.tasks 作为数据源，CreateTaskModal 创建任务后也更新它
const tasks = computed(() => taskStore.state.tasks)
let pollTimer = null

function hasActiveTasks() {
  return taskStore.state.tasks.some(t => t.status === 'running' || t.status === 'pending')
}

// 文档切换时立即刷新，不等下一次轮询
watch(() => docStore.state.selectedDocumentId, (docId) => {
  if (docId) taskStore.fetchCards(docId)
})

// 当有新任务时重新启动轮询
watch(() => taskStore.state.tasks, () => {
  if (hasActiveTasks() && !pollTimer) startPoll()
}, { deep: true })

onMounted(async () => {
  const docId = docStore.state.selectedDocumentId
  if (docId) await taskStore.fetchCards(docId)
  if (hasActiveTasks()) startPoll()
})

onUnmounted(stopPoll)

function startPoll() {
  if (pollTimer) return
  pollTimer = setInterval(() => {
    const docId = docStore.state.selectedDocumentId
    if (docId) taskStore.fetchCards(docId)
    if (!hasActiveTasks()) stopPoll()
  }, 3000)
}

function stopPoll() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function onDeleted(taskId) {
  taskStore.state.tasks = taskStore.state.tasks.filter(t => t.task_id !== taskId)
  if (!hasActiveTasks()) stopPoll()
}
</script>

<style scoped>
.task-stack { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.stack-title { font-size: 11px; font-weight: 600; color: var(--p-text-muted); text-transform: uppercase; letter-spacing: 0.04em; padding: 12px 16px 8px; }
.stack-empty { text-align: center; color: var(--p-text-muted); font-size: 12px; padding: 32px 20px; line-height: 1.6; }
.stack-list { flex: 1; overflow-y: auto; padding: 0 12px 12px; }
.stack-list > * { margin-bottom: 8px; }
.stack-list::-webkit-scrollbar { width: 4px; }
.stack-list::-webkit-scrollbar-thumb { background: transparent; border-radius: 2px; }
.stack-list:hover::-webkit-scrollbar-thumb { background: var(--p-border); }
</style>
