import { reactive } from 'vue'
import { defineStore } from 'pinia'

const API_BASE = ''

export const useTaskStore = defineStore('task', () => {
  const state = reactive({
    tasks: [],
    runningTaskIds: [],
    isCreating: false,
    errorMessage: '',
  })

  async function fetchTaskCard(taskId) {
    try {
      const res = await fetch(`${API_BASE}/api/tasks/${taskId}/card`)
      if (!res.ok) return null
      return await res.json()
    } catch {
      return null
    }
  }

  async function fetchCards(documentId) {
    try {
      const params = documentId ? `?document_id=${documentId}` : ''
      const res = await fetch(`${API_BASE}/api/tasks/cards${params}`)
      if (!res.ok) return
      const data = await res.json()
      state.tasks = data.tasks || []
      state.runningTaskIds = state.tasks.filter(t => t.status === 'running').map(t => t.task_id)
    } catch {
      // ignore
    }
  }

  async function createQuestionTask(documentId, params) {
    state.errorMessage = ''
    state.isCreating = true
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
      return data.task_id
    } catch (e) {
      state.errorMessage = '任务创建请求失败：' + e.message
      return null
    } finally {
      state.isCreating = false
    }
  }

  async function createGraphTask(documentId) {
    state.errorMessage = ''
    state.isCreating = true
    try {
      const res = await fetch(`${API_BASE}/api/tasks/graph?document_id=${documentId}`, {
        method: 'POST',
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        state.errorMessage = err.detail || '图谱创建失败'
        return null
      }
      const data = await res.json()
      return data.task_id
    } catch (e) {
      state.errorMessage = '图谱创建请求失败：' + e.message
      return null
    } finally {
      state.isCreating = false
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

  async function deleteCard(taskId) {
    try {
      const res = await fetch(`${API_BASE}/api/tasks/${taskId}/delete`, {
        method: 'DELETE',
      })
      return res.ok
    } catch {
      return false
    }
  }

  function recordTaskPoll(taskId) {
    if (!state.runningTaskIds.includes(taskId)) {
      state.runningTaskIds.push(taskId)
    }
  }

  function removeTaskPoll(taskId) {
    state.runningTaskIds = state.runningTaskIds.filter(id => id !== taskId)
  }

  return { state, fetchTaskCard, fetchCards, createQuestionTask, createGraphTask, fetchTaskResult, deleteCard, recordTaskPoll, removeTaskPoll }
})
