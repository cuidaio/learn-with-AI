import { reactive } from 'vue'
import { defineStore } from 'pinia'

const API_BASE = ''

export const useConfigStore = defineStore('config', () => {
  const state = reactive({
    embedding: { base_url: '', api_key_masked: '', model: '' },
    llm: { base_url: '', api_key_masked: '', model: '' },
    rawKeys: { embedding: '', llm: '' },  // 未脱敏的 Key，用于 API 调用
    isLoading: false,
    isSaving: false,
    isTesting: false,
    isPanelOpen: false,
    testStatus: { embedding: null, llm: null },
    saveMessage: '',
    errorMessage: '',
  })

  /** 还原初始值（用于重置后刷新 UI） */
  let _defaults = null

  async function fetchConfig() {
    state.isLoading = true
    try {
      const res = await fetch(`${API_BASE}/api/config`)
      if (!res.ok) throw new Error('获取配置失败')
      const data = await res.json()
      state.embedding = data.embedding || { base_url: '', api_key_masked: '', model: '' }
      state.llm = data.llm || { base_url: '', api_key_masked: '', model: '' }
      if (!_defaults) _defaults = JSON.parse(JSON.stringify(state))
    } catch (e) {
      state.errorMessage = e.message
    } finally {
      state.isLoading = false
    }
  }

  async function saveConfig(embedding, llm) {
    state.isSaving = true
    state.saveMessage = ''
    state.errorMessage = ''
    try {
      const body = {}
      if (embedding) body.embedding = embedding
      if (llm) body.llm = llm
      const res = await fetch(`${API_BASE}/api/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error('保存失败')
      // 保存原始 Key 以供后续 API 调用复用
      if (embedding?.api_key) state.rawKeys.embedding = embedding.api_key
      if (llm?.api_key) state.rawKeys.llm = llm.api_key
      state.saveMessage = '配置已更新'
      await fetchConfig()
    } catch (e) {
      state.errorMessage = e.message
    } finally {
      state.isSaving = false
    }
  }

  async function testConnection(type, base_url, api_key, model) {
    state.isTesting = true
    state.testStatus[type] = null
    state.errorMessage = ''
    try {
      const res = await fetch(`${API_BASE}/api/config/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type, base_url, api_key, model }),
      })
      if (!res.ok) throw new Error('测试请求失败')
      const data = await res.json()
      state.testStatus[type] = data
    } catch (e) {
      state.testStatus[type] = { success: false, error: e.message }
    } finally {
      state.isTesting = false
    }
  }

  async function fetchModels(type, base_url, api_key) {
    const params = new URLSearchParams({ type, base_url, api_key })
    const res = await fetch(`${API_BASE}/api/config/models?${params}`)
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || err.error || '获取模型列表失败')
    }
    return await res.json()
  }

  async function resetConfig() {
    state.isSaving = true
    state.saveMessage = ''
    state.errorMessage = ''
    try {
      const res = await fetch(`${API_BASE}/api/config/reset`, { method: 'POST' })
      if (!res.ok) throw new Error('重置失败')
      state.saveMessage = '配置已重置为默认值'
      state.rawKeys.embedding = ''
      state.rawKeys.llm = ''
      await fetchConfig()
    } catch (e) {
      state.errorMessage = e.message
    } finally {
      state.isSaving = false
    }
  }

  function togglePanel() {
    state.isPanelOpen = !state.isPanelOpen
    if (state.isPanelOpen) {
      state.saveMessage = ''
      state.errorMessage = ''
      state.testStatus = { embedding: null, llm: null }
    }
  }

  function closePanel() {
    state.isPanelOpen = false
  }

  return {
    state,
    fetchConfig,
    saveConfig,
    testConnection,
    fetchModels,
    resetConfig,
    togglePanel,
    closePanel,
  }
})
