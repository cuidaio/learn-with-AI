<template>
  <div class="task-list">
    <div class="tl-header">
      <span class="tl-title">任务列表</span>
    </div>

    <div v-if="tasks.length === 0" class="tl-empty">暂无任务</div>

    <div v-else class="tl-items">
      <div
        v-for="task in tasks"
        :key="task.task_id"
        class="tl-item"
        :class="'tl-status-' + task.status"
      >
        <div class="tl-left">
          <span class="tl-status-icon">
            <span v-if="task.status === 'pending'" class="icon-pending">⏳</span>
            <span v-else-if="task.status === 'running'" class="icon-running">🟡</span>
            <span v-else-if="task.status === 'completed'" class="icon-completed">🟢</span>
            <span v-else-if="task.status === 'failed'" class="icon-failed">🔴</span>
          </span>
          <div class="tl-info">
            <div class="tl-meta">
              {{ formatTime(task.created_at) }}
              <span v-if="task.completed_steps" class="tl-step">
                {{ task.completed_steps }}/{{ task.total_steps }}题
              </span>
              <span v-if="task.current_step" class="tl-step-desc">{{ task.current_step }}</span>
            </div>
            <div v-if="task.status === 'running' && task.total_steps" class="tl-progress">
              <div class="tl-progress-bar">
                <div
                  class="tl-progress-fill"
                  :style="{ width: (task.completed_steps / task.total_steps * 100) + '%' }"
                ></div>
              </div>
            </div>
            <div v-if="task.status === 'failed' && task.error_message" class="tl-error">
              {{ task.error_message }}
            </div>
          </div>
        </div>
        <div class="tl-right">
          <button
            v-if="task.status === 'completed'"
            class="tl-btn"
            @click="$emit('viewResult', task.task_id)"
          >查看</button>
          <button
            v-if="task.status === 'failed'"
            class="tl-btn tl-btn-retry"
            @click="$emit('retry', task)"
          >重试</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  tasks: { type: Array, default: () => [] },
})

defineEmits(['viewResult', 'retry'])

function formatTime(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const h = String(d.getHours()).padStart(2, '0')
  const m = String(d.getMinutes()).padStart(2, '0')
  return `${h}:${m}`
}
</script>

<style scoped>
.task-list {
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
}

.tl-header {
  padding: 10px 24px;
  border-bottom: 1px solid #f3f4f6;
}

.tl-title {
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
}

.tl-empty {
  padding: 12px 24px;
  font-size: 12px;
  color: #9ca3af;
}

.tl-items {
  max-height: 240px;
  overflow-y: auto;
}

.tl-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 24px;
  border-bottom: 1px solid #f3f4f6;
}

.tl-left {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.tl-status-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.tl-info {
  flex: 1;
  min-width: 0;
}

.tl-meta {
  font-size: 12px;
  color: #374151;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.tl-step {
  color: #3b82f6;
  font-weight: 500;
}

.tl-step-desc {
  color: #9ca3af;
  font-size: 11px;
}

.tl-progress {
  margin-top: 4px;
}

.tl-progress-bar {
  height: 4px;
  background: #e5e7eb;
  border-radius: 2px;
  max-width: 200px;
}

.tl-progress-fill {
  height: 100%;
  background: #3b82f6;
  border-radius: 2px;
  transition: width 0.3s;
}

.tl-error {
  font-size: 11px;
  color: #ef4444;
  margin-top: 2px;
}

.tl-right {
  flex-shrink: 0;
}

.tl-btn {
  padding: 3px 10px;
  font-size: 12px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  background: #fff;
  color: #374151;
  cursor: pointer;
}

.tl-btn-retry {
  color: #ef4444;
  border-color: #fca5a5;
}
</style>
