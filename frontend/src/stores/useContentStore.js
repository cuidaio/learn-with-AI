import { reactive } from 'vue'
import { defineStore } from 'pinia'

const API_BASE = ''

let TAB_COUNTER = 0
function nextTabId() {
  return `tab-${++TAB_COUNTER}`
}

export const useContentStore = defineStore('content', () => {
  const state = reactive({
    contentType: null,      // 兼容旧引用，指向 activeTab
    contentData: null,
    contentTitle: '',
    contentTimestamp: null,
    isLoading: false,
    // M3.1: 标签页
    tabs: [],
    activeTabId: null,
    // 每个 tab 的元数据（如题目作答状态），tabId → {}
    tabMeta: {},
    // M3.8: 文档阅读滚动位置，docId → 像素值
    documentScrollPositions: {},
  })

  // ── 兼容桥接：确保单页模式仍可用 ──
  function _syncFromTab(tab) {
    if (tab) {
      state.contentType = tab.contentType
      state.contentData = tab.contentData
      state.contentTitle = tab.title
    } else {
      state.contentType = null
      state.contentData = null
      state.contentTitle = ''
    }
  }

  function _activeTab() {
    return state.tabs.find(t => t.id === state.activeTabId) || null
  }

  // ── 标签页管理 ──

  function addTab(contentType, contentData, title, opts = {}) {
    // dedupKey 用于区分不同任务生成的同类型标签页（如多份训练题）
    const dedupKey = opts.dedupKey
    const existing = dedupKey
      ? state.tabs.find(t => t.dedupKey === dedupKey)
      : state.tabs.find(t => t.contentType === contentType && t.title === title)
    if (existing) {
      state.activeTabId = existing.id
      _syncFromTab(existing)
      return existing.id
    }
    const tab = {
      id: nextTabId(),
      contentType,
      contentData,
      title: title || '',
      dedupKey: dedupKey || null,
      isPinned: opts.isPinned || false,
    }
    state.tabs.push(tab)
    state.activeTabId = tab.id
    _syncFromTab(tab)
    return tab.id
  }

  function closeTab(tabId) {
    const idx = state.tabs.findIndex(t => t.id === tabId)
    if (idx === -1) return
    if (state.tabs.length <= 1) return  // 保留最后一个 tab
    // 清理 tab 元数据
    delete state.tabMeta[tabId]
    state.tabs.splice(idx, 1)
    // 激活邻近 tab
    const nextIdx = Math.min(idx, state.tabs.length - 1)
    state.activeTabId = state.tabs[nextIdx]?.id || null
    _syncFromTab(_activeTab())
  }

  function activateTab(tabId) {
    state.activeTabId = tabId
    _syncFromTab(_activeTab())
  }

  function updateTab(tabId, updates) {
    const tab = state.tabs.find(t => t.id === tabId)
    if (!tab) return
    Object.assign(tab, updates)
    if (tabId === state.activeTabId) {
      _syncFromTab(tab)
    }
  }

  // ── 加载方法（自动创建/激活 tab） ──

  async function loadDocument(id) {
    state.isLoading = true
    try {
      const res = await fetch(`${API_BASE}/api/documents/${id}/default`)
      if (!res.ok) throw new Error('Failed to load document')
      const data = await res.json()
      const title = data.title || ''
      addTab('document', data, title, { isPinned: true })
      state.contentTimestamp = null
    } catch {
      // ignore
    } finally {
      state.isLoading = false
    }
  }

  async function loadTaskResult(taskId) {
    // 不设 isLoading — 已完成的任务加载很快，设 loading 反而导致中栏闪烁
    try {
      const res = await fetch(`${API_BASE}/api/tasks/${taskId}/result`)
      if (!res.ok) throw new Error('Failed to load result')
      const data = await res.json()
      const result = data.result
      if (result && result.content_type) {
        const title = result.title || ''
        addTab(result.content_type, result.data || result, title, { dedupKey: taskId })
        state.contentTimestamp = data.completed_at || null
      }
    } catch {
      // ignore — tab not added
    }
  }

  function setChat() {
    addTab('chat', null, 'AI对话')
    state.contentTimestamp = null
  }

  async function loadEntities(documentId) {
    try {
      const res = await fetch(`${API_BASE}/api/documents/${documentId}/entities`)
      if (!res.ok) throw new Error('Failed to load entities')
      const data = await res.json()
      addTab('entities', data, '实体一览')
      state.contentTimestamp = null
    } catch {
      // ignore
    }
  }

  function clear() {
    state.tabs = []
    state.activeTabId = null
    state.contentType = null
    state.contentData = null
    state.contentTitle = ''
    state.contentTimestamp = null
    state.tabMeta = {}
  }

  // ── 文档滚动位置 ──

  function saveScrollPosition(tabId, scrollTop) {
    if (tabId) state.documentScrollPositions[tabId] = scrollTop
  }

  function getScrollPosition(tabId) {
    return tabId ? (state.documentScrollPositions[tabId] || null) : null
  }

  // ── 高亮刷新（重新抓取当前文档数据） ──

  async function refreshCurrentDocument() {
    const tab = state.tabs.find(t => t.contentType === 'document')
    if (!tab) return
    const docId = typeof tab.contentData === 'object' ? tab.contentData?.id || null : null
    if (!docId) return
    try {
      const res = await fetch(`${API_BASE}/api/documents/${docId}/default`)
      if (!res.ok) return
      const data = await res.json()
      tab.contentData = data
      if (state.activeTabId === tab.id) {
        state.contentData = data
      }
    } catch {
      // ignore
    }
  }

  // ── Tab 元数据（训练状态等） ──

  function setTabMeta(tabId, key, value) {
    if (!state.tabMeta[tabId]) state.tabMeta[tabId] = {}
    state.tabMeta[tabId][key] = value
  }

  function getTabMeta(tabId, key, defaultValue = undefined) {
    return state.tabMeta[tabId]?.[key] ?? defaultValue
  }

  return { state, loadDocument, loadTaskResult, setChat, loadEntities, clear, addTab, closeTab, activateTab, updateTab, setTabMeta, getTabMeta, saveScrollPosition, getScrollPosition, refreshCurrentDocument }
})
