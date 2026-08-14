<template>
  <div
    :class="['task-card', statusClass, { clickable: status === 'completed' || status === 'failed' }]"
    @click="handleClick"
  >
    <div class="card-top">
      <span class="card-icon">{{ icon }}</span>
      <span class="card-title">{{ title }}</span>
      <span class="card-status">{{ statusLabel }}</span>
    </div>
    <div class="card-time">{{ timeStr }}</div>

    <!-- 进度条 -->
    <div v-if="status === 'running'" class="card-progress-bar">
      <div class="card-progress-fill" :style="{ transform: 'scaleX(' + (progress / 100) + ')' }"></div>
    </div>

    <div v-if="progressText && status === 'running'" class="card-progress-text">
      {{ progressText }}
    </div>

    <!-- 错误信息 -->
    <div v-if="status === 'failed' && error" class="card-error">
      {{ error }}
    </div>

    <!-- 删除按钮 -->
    <button class="card-delete" @click.stop="handleDelete" title="删除卡片">✕</button>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useContentStore } from '../../stores/useContentStore'
import { useLearningStore } from '../../stores/useLearningStore'
import { useTaskStore } from '../../stores/useTaskStore'

const props = defineProps({
  taskId: { type: String, required: true },
  initialStatus: { type: Object, default: null },
})

const emit = defineEmits(['deleted'])

const contentStore = useContentStore()
const learningStore = useLearningStore()
const taskStore = useTaskStore()

// 自身状态
const status = ref('pending')
const title = ref('任务')
const icon = ref('📋')
const progress = ref(0)
const progressText = ref('')
const error = ref(null)
const createdAt = ref(null)
const result = ref(null)

let pollTimer = null
let mounted = true

// 状态标签
const statusLabel = computed(() => {
  const map = {
    pending: '排队中...',
    running: '运行中...',
    completed: '✅ 已完成',
    failed: '❌ 失败',
  }
  return map[status.value] || status.value
})

const statusClass = computed(() => `status-${status.value}`)

const timeStr = computed(() => {
  const t = createdAt.value
  if (!t) return ''
  const d = new Date(t)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
})

// 加载状态
async function loadStatus() {
  try {
    const data = await taskStore.fetchTaskCard(props.taskId)
    if (!data || !mounted) return
    status.value = data.status || 'pending'
    title.value = data.card_title || data.title || '任务'
    icon.value = data.card_icon || '📋'
    progress.value = data.progress || 0
    progressText.value = data.progress_text || ''
    error.value = data.error || data.error_message || null
    createdAt.value = data.created_at || null
    result.value = data.result || null
  } catch (e) {
    // ignore
  }
}

// 轮询
function startPolling() {
  if (pollTimer) return
  pollTimer = setInterval(async () => {
    await loadStatus()
    if (status.value === 'completed' || status.value === 'failed') {
      stopPolling()
    }
  }, 3000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

// 交互
function handleClick() {
  if (status.value === 'completed' && result.value) {
    const r = result.value
    // result 已通过 loadStatus 预加载，直接添加标签页，跳过 API 请求
    if (r.content_type) {
      contentStore.addTab(r.content_type, r.data || r, r.title || '', { dedupKey: props.taskId })
    }
    learningStore.record('task_card_clicked', {
      context: { task_id: props.taskId },
    })
  } else if (status.value === 'failed') {
    handleRetry()
  }
}

async function handleRetry() {
  status.value = 'pending'
  progress.value = 0
  progressText.value = '重试中...'
  try {
    const res = await fetch(`/api/tasks/${props.taskId}/retry`, { method: 'POST' })
    if (res.ok) {
      const data = await res.json()
      taskStore.recordTaskPoll(data.task_id)
      startPolling()
    }
  } catch {
    // ignore
  }
}

async function handleDelete() {
  if (confirm('确定要删除此任务卡片吗？')) {
    try {
      const res = await fetch(`/api/tasks/${props.taskId}/delete`, { method: 'DELETE' })
      if (res.ok) emit('deleted')
    } catch {
      // ignore
    }
  }
}

// 生命周期
onMounted(async () => {
  if (props.initialStatus) {
    const s = props.initialStatus
    status.value = s.status || 'pending'
    title.value = s.card_title || s.title || '任务'
    icon.value = s.card_icon || '📋'
    progress.value = s.progress || 0
    progressText.value = s.progress_text || ''
    error.value = s.error || s.error_message || null
    createdAt.value = s.created_at || null
  }

  // 总是调一次 loadStatus 获取含 result 的完整数据
  // initialStatus 来自卡片列表 GET /api/tasks/cards，不含 result
  // 页面刷新后已完成卡片不轮询，若不主动获取则 result=null → 点击无响应
  await loadStatus()

  if (status.value === 'pending' || status.value === 'running') {
    startPolling()
  }
})

onUnmounted(() => {
  mounted = false
  stopPolling()
})
</script>

<style scoped>
.task-card {
  position: relative;
  background: var(--p-surface);
  border: 1px solid var(--p-border);
  border-radius: var(--r-md);
  padding: 12px 14px;
  transition: box-shadow 0.15s ease, border-color 0.15s ease;
}

.task-card.clickable { cursor: pointer; }

.task-card.clickable:hover {
  border-color: #cbd5e1;
  box-shadow: var(--shadow-sm);
}

.task-card.status-running { border-color: #fde68a; background: #fffbeb; }
.task-card.status-completed { border-color: #bbf7d0; }
.task-card.status-failed { border-color: #fecaca; background: #fef2f2; }
.status-pending { opacity: 0.75; }

.card-top { display: flex; align-items: center; gap: 8px; }
.card-icon { font-size: 14px; flex-shrink: 0; }
.card-title { flex: 1; font-size: 13px; font-weight: 500; color: var(--p-text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.card-status { font-size: 10px; font-weight: 500; white-space: nowrap; padding: 2px 8px; border-radius: 10px; background: var(--p-surface-muted); }

.status-running .card-status { background: #fef3c7; color: #d97706; }
.status-completed .card-status { background: #f0fdf4; color: #16a34a; }
.status-failed .card-status { background: #fef2f2; color: #dc2626; }

.card-time { font-size: 11px; color: var(--p-text-muted); margin-top: 4px; }

.card-progress-bar { margin-top: 8px; height: 4px; background: var(--p-border); border-radius: 2px; overflow: hidden; position: relative; }
.card-progress-fill { position: absolute; inset: 0; background: #f59e0b; border-radius: 2px; transform-origin: left center; transition: transform 0.3s ease; }
.card-progress-text { font-size: 10px; color: #d97706; margin-top: 3px; }

.card-error { font-size: 11px; color: #dc2626; margin-top: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.card-delete {
  position: absolute; top: 6px; right: 6px; display: none;
  width: 20px; height: 20px; line-height: 20px; text-align: center;
  background: var(--p-surface); border: 1px solid var(--p-border); border-radius: 50%;
  font-size: 11px; color: var(--p-text-muted); cursor: pointer; padding: 0;
  transition: all 0.1s ease;
}
.card-delete:hover { background: #fef2f2; border-color: #fecaca; color: #dc2626; }
.task-card:hover .card-delete { display: block; }
</style>
