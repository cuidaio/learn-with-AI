<template>
  <div class="app">
    <!-- Header -->
    <header class="header">
      <h1 class="title">learn-with-AI</h1>
      <p :class="connected ? 'connected' : 'disconnected'">
        后端：{{ connected ? '已连接' : '未连接' }}
      </p>
    </header>

    <!-- Two-pane layout -->
    <div class="layout">
      <!-- Left: Document List (30%) -->
      <div class="pane-left">
        <DocumentList
          :documents="state.documents"
          :selected-ids="state.selectedDocumentIds"
          :loading="loading"
          @toggle="handleToggle"
          @upload="state.showUploadDialog = true"
        />
      </div>

      <!-- Right: Chat / Graph / Questions (70%) -->
      <div class="pane-right">
        <!-- Tab bar (visible when exactly 1 document selected) -->
        <div v-if="state.selectedDocumentIds.length === 1" class="tab-bar">
          <button
            :class="['tab', { active: state.activeTab === 'chat' }]"
            @click="store.setActiveTab('chat')"
          >对话</button>
          <button
            :class="['tab', { active: state.activeTab === 'graph' }]"
            @click="switchTab('graph')"
          >知识图谱</button>
          <button
            :class="['tab', { active: state.activeTab === 'questions' }]"
            @click="switchTab('questions')"
          >题目</button>
        </div>

        <!-- Chat -->
        <div v-if="state.activeTab === 'chat'" class="tab-content">
          <ChatArea
            ref="chatAreaRef"
            :messages="state.messages"
            :is-thinking="state.isThinking"
            :selected-count="state.selectedDocumentIds.length"
            :selected-doc-title="selectedDocTitle"
            :error-message="state.errorMessage"
            @send="handleSend"
          />
        </div>

        <!-- Knowledge Graph -->
        <div v-if="state.activeTab === 'graph'" class="tab-content">
          <GraphView
            :graph-data="state.graphData"
            :loading="state.graphLoading"
            :generating="state.generatingQuestions"
            @generate="handleGenerateQuestions"
            @refresh="handleGraphRefresh"
          />
        </div>

        <!-- Questions (M2.8.2: control + tasks + list) -->
        <div v-if="state.activeTab === 'questions'" class="tab-content questions-tab">
          <QuestionControl
            :entities="state.entities"
            :generating="!!state.activeTaskId"
            @generate="handleQuestionGenerate"
          />
          <TaskList
            :tasks="state.tasks"
            @view-result="handleViewTaskResult"
            @retry="handleTaskRetry"
          />
          <div v-if="state.errorMessage" class="questions-error">{{ state.errorMessage }}</div>
          <QuestionList
            :questions="state.questions"
            :loading="state.questionsLoading"
          />
        </div>
      </div>
    </div>

    <!-- Upload Dialog -->
    <UploadDialog
      :show="state.showUploadDialog"
      :uploading="state.isUploading"
      @close="state.showUploadDialog = false"
      @upload="handleUpload"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAppStore } from './stores/useAppStore.js'
import DocumentList from './components/DocumentList.vue'
import ChatArea from './components/ChatArea.vue'
import UploadDialog from './components/UploadDialog.vue'
import GraphView from './components/GraphView.vue'
import QuestionControl from './components/QuestionControl.vue'
import TaskList from './components/TaskList.vue'
import QuestionList from './components/QuestionList.vue'

const store = useAppStore()
const { state } = store

const connected = ref(false)
const loading = ref(false)
const chatAreaRef = ref(null)

const selectedDocTitle = computed(() => {
  const ids = state.selectedDocumentIds
  if (ids.length === 0) return ''
  const doc = state.documents.find(d => d.id === ids[0])
  return doc ? doc.title : ''
})

onMounted(async () => {
  await checkHealth()
  loading.value = true
  await store.fetchDocuments()
  loading.value = false
})

async function checkHealth() {
  try {
    const res = await fetch('/api/health')
    const data = await res.json()
    connected.value = data.status === 'healthy'
  } catch {
    connected.value = false
  }
}

async function handleSend(question) {
  await store.askQuestion(question)
  if (chatAreaRef.value) {
    await chatAreaRef.value.scrollToBottom()
  }
}

async function handleUpload({ title, text }) {
  state.uploadTitle = title
  state.uploadText = text
  await store.uploadDocument()
}

function handleToggle(id) {
  store.toggleDocument(id)
  const selected = state.selectedDocumentIds
  if (selected.length === 1) {
    state.activeTab = 'chat'
  }
}

async function switchTab(tab) {
  store.setActiveTab(tab)
  const ids = state.selectedDocumentIds
  if (ids.length !== 1) return
  const docId = ids[0]
  if (tab === 'graph') {
    await store.fetchKnowledgeGraph(docId)
  } else if (tab === 'questions') {
    await Promise.all([
      store.fetchEntities(docId),
      store.fetchQuestions(docId),
      store.fetchTasks(docId),
    ])
  }
}

async function handleGenerateQuestions(entityIds) {
  const ids = state.selectedDocumentIds
  if (ids.length !== 1) return
  // Redirect to questions tab and create task
  store.setActiveTab('questions')
  await handleQuestionGenerate({ entityIds, types: ['choice', 'multi_choice', 'fill', 'short_answer', 'essay'], totalCount: 18, scenario: 'section_review' })
}

async function handleGraphRefresh() {
  const ids = state.selectedDocumentIds
  if (ids.length !== 1) return
  await store.fetchKnowledgeGraph(ids[0])
}

// M2.8.2: 异步出题任务
async function handleQuestionGenerate(params) {
  const ids = state.selectedDocumentIds
  if (ids.length !== 1) return
  const docId = ids[0]
  await store.createQuestionTask(docId, params)
  // 刷新任务列表
  await store.fetchTasks(docId)
}

async function handleViewTaskResult(taskId) {
  try {
    const result = await store.fetchTaskResult(taskId)
    if (result && result.result && result.result.questions) {
      // task result 中字段名是 type，UI 组件需要 question_type
      state.questions = result.result.questions.map(q => ({
        ...q,
        question_type: q.question_type || q.type,
      }))
      store.setActiveTab('questions')
    } else {
      state.errorMessage = '查看题目失败：结果数据格式错误'
    }
  } catch (e) {
    state.errorMessage = '查看题目失败：' + (e.message || e)
  }
}

function handleTaskRetry(task) {
  const p = task.params || store.getLastTaskParams() || {}
  handleQuestionGenerate({
    entityIds: p.entity_ids || [],
    types: p.types || ['choice', 'multi_choice', 'fill', 'short_answer', 'essay'],
    totalCount: p.total_count || 18,
    scenario: p.scenario || 'section_review',
  })
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #f0f2f5;
  color: #333;
  height: 100vh;
  overflow: hidden;
}

#app {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.app {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

/* Header */
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 24px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  flex-shrink: 0;
}

.title {
  font-size: 1.2rem;
  font-weight: 600;
}

.connected {
  color: #22c55e;
  font-weight: 500;
  font-size: 13px;
}

.disconnected {
  color: #ef4444;
  font-weight: 500;
  font-size: 13px;
}

/* Two-pane layout */
.layout {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.pane-left {
  width: 30%;
  min-width: 260px;
  max-width: 400px;
  border-right: 1px solid #e5e7eb;
}

.pane-right {
  flex: 1;
  display: flex;
  flex-direction: column;
}

/* Tab bar */
.tab-bar {
  display: flex;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  flex-shrink: 0;
}

.tab {
  padding: 10px 20px;
  font-size: 13px;
  font-weight: 500;
  color: #6b7280;
  background: none;
  border: none;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.15s;
}

.tab:hover {
  color: #374151;
  background: #f9fafb;
}

.tab.active {
  color: #3b82f6;
  border-bottom-color: #3b82f6;
}

.tab-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.questions-tab {
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}
.questions-tab > .question-panel {
  flex: 1;
  min-height: 200px;
}

.questions-error {
  padding: 8px 24px;
  font-size: 12px;
  color: #ef4444;
  background: #fef2f2;
  border-bottom: 1px solid #fecaca;
}
</style>
