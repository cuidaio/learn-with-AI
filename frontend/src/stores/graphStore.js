import { reactive } from 'vue'
import { defineStore } from 'pinia'

/**
 * 图谱浏览器状态管理（M3.9 / M3.10）
 *
 * 存储展开历史、路径选择状态、编辑模式状态。
 * 不存储 G6 实例（硬红线：G6 实例不允许用 ref/reactive 包装）。
 */
export const useGraphStore = defineStore('graph', () => {
  const state = reactive({
    /** 已展开过的节点 ID 数组（不再重复请求） */
    expandedIds: [],
    /** 展开历史栈，用于 Ctrl+Z */
    history: [],
    /** 路径选择状态 */
    pathSelection: {
      from: null,
      to: null,
    },
    /** 当前高亮路径节点 ID 数组 */
    highlightedPathNodes: [],
    /** 当前高亮路径边 ID 数组 */
    highlightedPathEdges: [],

    // ── M3.10 编辑模式 ──
    /** 当前模式: 'browse' | 'edit' */
    mode: 'browse',
    /** 编辑模式下选中的源节点 ID */
    selectedNodeId: null,
    /** 编辑操作历史栈（创建/更新/删除），用于 Ctrl+Z */
    editHistory: [],
  })

  function isExpanded(nodeId) {
    return state.expandedIds.includes(nodeId)
  }

  function markExpanded(nodeId) {
    if (!isExpanded(nodeId)) {
      state.expandedIds.push(nodeId)
    }
  }

  function pushHistory(entry) {
    state.history.push(entry)
  }

  function popHistory() {
    return state.history.pop() || null
  }

  function setPathSelection(from, to) {
    state.pathSelection.from = from
    state.pathSelection.to = to
  }

  function clearPathSelection() {
    state.pathSelection.from = null
    state.pathSelection.to = null
  }

  function clearHighlight() {
    state.highlightedPathNodes = []
    state.highlightedPathEdges = []
  }

  // ── M3.10 编辑模式 ──

  function setMode(mode) {
    state.mode = mode
  }

  function setSelectedNode(id) {
    state.selectedNodeId = id
  }

  function pushEditHistory(entry) {
    state.editHistory.push(entry)
  }

  function popEditHistory() {
    return state.editHistory.pop() || null
  }

  function clearEditHistory() {
    state.editHistory = []
  }

  return {
    state,
    isExpanded,
    markExpanded,
    pushHistory,
    popHistory,
    setPathSelection,
    clearPathSelection,
    clearHighlight,
    setMode,
    setSelectedNode,
    pushEditHistory,
    popEditHistory,
    clearEditHistory,
  }
})
