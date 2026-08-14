import { reactive } from 'vue'
import { defineStore } from 'pinia'

const API_BASE = ''

export const useLearningStore = defineStore('learning', () => {
  const state = reactive({
    events: [],
    pendingEvents: [],
  })

  async function record(eventType, payload = {}) {
    const event = {
      event_type: eventType,
      ...payload,
    }
    state.events.push(event)
    state.pendingEvents.push(event)
    // 立即上报
    try {
      await fetch(`${API_BASE}/api/learning-events`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(event),
      })
      state.pendingEvents = state.pendingEvents.filter(e => e !== event)
    } catch {
      // 留在 pendingEvents 中，下次批量上报
    }
  }

  async function flush() {
    if (state.pendingEvents.length === 0) return
    try {
      await fetch(`${API_BASE}/api/learning-events/batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(state.pendingEvents),
      })
      state.pendingEvents = []
    } catch {
      // keep for next attempt
    }
  }

  return { state, record, flush }
})
