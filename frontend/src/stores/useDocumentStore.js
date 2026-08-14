import { reactive } from 'vue'
import { defineStore } from 'pinia'

const API_BASE = ''

export const useDocumentStore = defineStore('document', () => {
  const state = reactive({
    folders: [],
    documents: [],
    selectedDocumentId: null,
    expandedFolders: [],
    isLoading: false,
    showUploadDialog: false,
    uploadTitle: '',
    uploadText: '',
    isUploading: false,
    // M3.8: 高亮刷新触发器（递增计数触发 DocumentReader 重载）
    highlightRefreshTrigger: 0,
  })

  async function fetchAll() {
    // 不设 isLoading，避免每次刷新导致左栏闪烁
    // 初始加载由 MainLayout onMounted 调用，此时已有空状态占位
    try {
      const [docRes, folderRes] = await Promise.all([
        fetch(`${API_BASE}/api/documents`),
        fetch(`${API_BASE}/api/folders`),
      ])
      if (docRes.ok) {
        const data = await docRes.json()
        state.documents = data.documents || []
      }
      if (folderRes.ok) {
        const data = await folderRes.json()
        state.folders = data.folders || []
      }
    } catch {
      // ignore
    }
  }

  async function uploadDocument() {
    const text = state.uploadText.trim()
    if (!text) return
    state.isUploading = true
    try {
      const res = await fetch(`${API_BASE}/api/documents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: state.uploadTitle.trim(),
          raw_text: text,
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        state.errorMessage = '上传失败：' + (err.detail || res.statusText)
        return
      }
      state.uploadTitle = ''
      state.uploadText = ''
      state.showUploadDialog = false
      await fetchAll()
    } catch (e) {
      state.errorMessage = '上传请求失败：' + e.message
    } finally {
      state.isUploading = false
    }
  }

  function selectDocument(id) {
    state.selectedDocumentId = id
  }

  function toggleFolderExpand(id) {
    const idx = state.expandedFolders.indexOf(id)
    if (idx === -1) {
      state.expandedFolders.push(id)
    } else {
      state.expandedFolders.splice(idx, 1)
    }
  }

  function getDocument(id) {
    return state.documents.find(d => d.id === id) || null
  }

  function refreshHighlights() {
    state.highlightRefreshTrigger++
  }

  return { state, fetchAll, uploadDocument, selectDocument, toggleFolderExpand, getDocument, refreshHighlights }
})
