import { reactive } from 'vue'

const API_BASE = import.meta.env.DEV ? 'http://localhost:7480' : ''

const state = reactive({
  documents: [],
  selectedDocumentIds: [],
  messages: [],
  isThinking: false,
  showUploadDialog: false,
  uploadTitle: '',
  uploadText: '',
  isUploading: false,
  errorMessage: '',

  // M2.8 知识图谱
  activeTab: 'chat',
  graphData: null,
  graphLoading: false,

  // M2.8 题目
  questions: [],
  questionsLoading: false,
  generatingQuestions: false,

  // M2.8.2 异步任务
  entities: [],
  entitiesLoading: false,
  tasks: [],
  activeTaskId: null,
  taskPollTimer: null,
})

async function fetchDocuments() {
  try {
    const res = await fetch('/api/documents')
    const data = await res.json()
    state.documents = data.documents || []
  } catch {
    state.documents = []
  }
}

async function uploadDocument() {
  const text = state.uploadText.trim()
  if (!text) return
  state.isUploading = true
  try {
    const res = await fetch('/api/documents', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: state.uploadTitle.trim(),
        raw_text: text,
      }),
    })
    if (!res.ok) {
      const err = await res.json()
      state.errorMessage = '上传失败：' + (err.detail || res.statusText)
      return
    }
    state.uploadTitle = ''
    state.uploadText = ''
    state.showUploadDialog = false
    await fetchDocuments()
  } catch (e) {
    state.errorMessage = '请求失败：' + e.message
  } finally {
    state.isUploading = false
  }
}

async function askQuestion(question) {
  state.isThinking = true
  state.errorMessage = ''
  const userMsg = { role: 'user', content: question }
  state.messages.push(userMsg)

  let aiMsg = null

  try {
    const res = await fetch(`${API_BASE}/api/ask/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        document_ids: state.selectedDocumentIds,
        question,
        top_k: 5,
      }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      state.errorMessage = err.detail || '回答生成失败'
      state.isThinking = false
      return
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const data = JSON.parse(line.slice(6))
          if (data.type === 'start') {
            aiMsg = { role: 'assistant', content: '', sources: [] }
            state.messages.push(aiMsg)
          } else if (data.type === 'token' && aiMsg) {
            aiMsg.content += data.content
            state.messages[state.messages.length - 1] = { ...aiMsg }
          } else if (data.type === 'done' && aiMsg) {
            aiMsg.sources = data.sources || []
            state.messages[state.messages.length - 1] = { ...aiMsg }
          } else if (data.type === 'error') {
            state.errorMessage = data.message || 'LLM 生成失败'
          }
        } catch (e) {
          // skip malformed SSE lines
        }
      }
    }
  } catch {
    state.errorMessage = '网络连接失败，请重试'
  } finally {
    state.isThinking = false
  }
}

// ===== M2.8 知识图谱 =====

async function fetchKnowledgeGraph(documentId) {
  if (!documentId) return
  state.graphLoading = true
  try {
    const res = await fetch(`${API_BASE}/api/documents/${documentId}/knowledge-graph`)
    if (!res.ok) throw new Error('Failed to fetch graph')
    state.graphData = await res.json()
  } catch {
    state.graphData = null
  } finally {
    state.graphLoading = false
  }
}

// ===== M2.8.2 异步出题 =====

async function fetchEntities(documentId) {
  if (!documentId) return
  state.entitiesLoading = true
  try {
    const res = await fetch(`${API_BASE}/api/documents/${documentId}/entities`)
    if (!res.ok) throw new Error('Failed to fetch entities')
    state.entities = await res.json()
  } catch {
    state.entities = []
  } finally {
    state.entitiesLoading = false
  }
}

async function createQuestionTask(documentId, params) {
  state.errorMessage = ''
  try {
    const res = await fetch(`${API_BASE}/api/tasks/questions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        document_id: documentId,
        entity_ids: params.entityIds,
        total_count: params.totalCount || 18,
        types: params.types || ['choice', 'multi_choice', 'fill', 'short_answer', 'essay'],
        scenario: params.scenario || 'section_review',
      }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      state.errorMessage = err.detail || '任务创建失败'
      return null
    }
    const data = await res.json()
    // 轮询任务状态
    state.activeTaskId = data.task_id
    _startTaskPoll(data.task_id)
    return data.task_id
  } catch (e) {
    state.errorMessage = '任务创建请求失败：' + e.message
    return null
  }
}

function _startTaskPoll(taskId) {
  // 清除旧轮询
  _stopTaskPoll()
  state.taskPollTimer = setInterval(async () => {
    const task = await _fetchTaskStatus(taskId)
    if (!task) return
    // 更新 task list 中的对应项
    const idx = state.tasks.findIndex(t => t.task_id === taskId)
    if (idx !== -1) {
      state.tasks[idx] = { ...state.tasks[idx], ...task }
    }
    if (task.status === 'completed' || task.status === 'failed') {
      _stopTaskPoll()
      state.activeTaskId = null
      // 刷新全部任务列表
      const ids = state.selectedDocumentIds
      if (ids.length === 1) {
        await fetchTasks(ids[0])
        if (task.status === 'completed') {
          await fetchQuestions(ids[0])
        }
      }
    }
  }, 3000)
}

function _stopTaskPoll() {
  if (state.taskPollTimer) {
    clearInterval(state.taskPollTimer)
    state.taskPollTimer = null
  }
}

async function _fetchTaskStatus(taskId) {
  try {
    const res = await fetch(`${API_BASE}/api/tasks/${taskId}/status`)
    if (!res.ok) return null
    return await res.json()
  } catch {
    return null
  }
}

async function fetchTaskResult(taskId) {
  try {
    const res = await fetch(`${API_BASE}/api/tasks/${taskId}/result`)
    if (!res.ok) return null
    return await res.json()
  } catch {
    return null
  }
}

async function fetchTasks(documentId) {
  try {
    const params = new URLSearchParams({ task_type: 'question_generation' })
    if (documentId) params.set('document_id', documentId)
    const res = await fetch(`${API_BASE}/api/tasks?${params}`)
    if (!res.ok) return
    const data = await res.json()
    state.tasks = data.tasks || []
  } catch {
    // ignore
  }
}

function getLastTaskParams() {
  // 从已完成/失败的任务中获取参数，用于重试
  const task = state.tasks.find(t => t.params)
  return task ? task.params : null
}

// ===== M2.8 题目查询 =====

async function fetchQuestions(documentId) {
  if (!documentId) return
  state.questionsLoading = true
  try {
    const res = await fetch(`${API_BASE}/api/questions?document_id=${documentId}`)
    if (!res.ok) throw new Error('Failed to fetch questions')
    const data = await res.json()
    state.questions = data.questions || []
  } catch {
    state.questions = []
  } finally {
    state.questionsLoading = false
  }
}

function setActiveTab(tab) {
  state.activeTab = tab
}

function toggleDocument(id) {
  const idx = state.selectedDocumentIds.indexOf(id)
  if (idx === -1) {
    state.selectedDocumentIds.push(id)
  } else {
    state.selectedDocumentIds.splice(idx, 1)
  }
}

export function useAppStore() {
  return {
    state,
    fetchDocuments,
    uploadDocument,
    askQuestion,
    toggleDocument,
    fetchKnowledgeGraph,
    fetchEntities,
    createQuestionTask,
    fetchTaskResult,
    fetchTasks,
    fetchQuestions,
    getLastTaskParams,
    setActiveTab,
    _stopTaskPoll,
  }
}
