<template>
  <div class="knowledge-graph">
    <div v-if="!hasData" class="kg-empty">暂无图谱数据</div>
    <div v-else class="kg-layout">
      <div class="kg-toolbar">
        <div class="kg-mode-toggle">
          <button :class="['kg-mode-btn', { active: graphStore.state.mode === 'browse' }]" @click="setBrowseMode">🔍 浏览</button>
          <button :class="['kg-mode-btn', { active: graphStore.state.mode === 'edit' }]" @click="setEditMode">✏️ 编辑</button>
        </div>
        <span class="kg-hint">{{ modeHint }}</span>
        <span class="kg-counts" v-if="graphStore.state.mode === 'browse'">展示 {{ displayedCount }}/{{ totalCount }}</span>
        <button v-if="graphStore.state.highlightedPathNodes.length" class="kg-clear-btn" @click="clearPathResult">清除路径</button>
      </div>
      <div class="kg-canvas-wrap">
        <div ref="containerRef" class="kg-canvas"></div>
        <Transition name="slide-down">
          <div v-if="tooltipVisible" class="kg-info-bar">
            <div class="kg-ib-row">
              <span class="kg-ib-name">{{ tooltipData.name }}</span>
              <span class="kg-ib-type" :style="{ background: COLORS[tooltipData.type] || '#94a3b8' }">{{ typeLabel(tooltipData.type) }}</span>
            </div>
            <div v-if="tooltipData.desc" class="kg-ib-desc">{{ tooltipData.desc }}</div>
          </div>
        </Transition>
      </div>
      <Transition name="slide-up">
        <div v-if="pathText" class="kg-status-bar" @click="clearPathResult">
          <span class="kg-path-icon">🔗</span>
          <span class="kg-path-text">{{ pathText }}</span>
          <span class="kg-path-dismiss">✕</span>
        </div>
      </Transition>
      <RelationEditor
        v-if="editor.visible"
        :source-name="editor.sourceName"
        :target-name="editor.targetName"
        :relation-type="editor.relationType"
        :description="editor.description"
        :has-existing-relation="editor.hasExisting"
        :mode="editor.mode"
        @save="onEditorSave"
        @delete="onEditorDelete"
        @cancel="onEditorCancel"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted, onUnmounted, onActivated, onDeactivated, nextTick } from 'vue'
import { useContentStore } from '../../stores/useContentStore'
import { useGraphStore } from '../../stores/graphStore'
import { Graph } from '@antv/g6'
import RelationEditor from './RelationEditor.vue'
import { COLORS, LAYOUT_CFG, computeRootsFromData, queryNeighborIds, typeLabel } from './graph-utils.js'

const contentStore = useContentStore()
const graphStore = useGraphStore()

const containerRef = ref(null)
const loadingNodeId = ref(null)
const pathText = ref('')
const displayedCount = ref(0)
const totalCount = ref(0)

// ── 悬停提示 ──
const tooltipVisible = ref(false)
const tooltipData = ref({ name: '', type: '', score: 0, desc: '' })
let tooltipTimer = null

// ── 编辑器状态（单个 reactive → 10 个 ref 的等价替代） ──
const editor = reactive({
  visible: false,
  sourceName: '',
  targetName: '',
  relationType: '',
  description: '',
  hasExisting: false,
  mode: 'node',
  relationId: null,
  sourceId: null,
  targetId: null,
})

function closeEditor() {
  editor.visible = false
  editor.relationId = null
  editor.sourceId = null
  editor.targetId = null
}

// ── 模块级状态（非响应式） ──
let graph = null
let shift = false
let pathFrom = null
let _rootsCache = null
let _leafIds = new Set()
let _freshGraphData = null

const modeHint = computed(() => {
  if (graphStore.state.mode === 'edit') return '单击节点选择 · 选两个节点编辑关系 · 单击连线编辑 · Esc 取消 · Ctrl+Z 撤销'
  return '单击展开 · Shift+单击查路径 · Ctrl+Z 撤销'
})

const raw = computed(() => {
  const d = contentStore.state.contentData
  return d ? (d.data || d) : null
})
const hasData = computed(() => raw.value?.entities?.length > 0)

// ── 关系数据合并（任务快照 + API 实时） ──
function getMergedRelations() {
  const base = raw.value?.relations || []
  if (!_freshGraphData) return base
  const seen = new Set(base.map((r) => r.id))
  const merged = [...base]
  for (const r of _freshGraphData.relations || []) {
    if (!seen.has(r.id)) {
      seen.add(r.id)
      merged.push(r)
    }
  }
  return merged
}

function hasHiddenNeighbors(entityId) {
  const allNb = queryNeighborIds(entityId, getMergedRelations())
  return allNb.some((id) => !graph.hasNode(id))
}

function refreshCounts() {
  if (!graph) {
    displayedCount.value = 0
    return
  }
  try {
    displayedCount.value = graph.getNodeData().filter((n) => !n.data?.isVirtual).length
  } catch {
    displayedCount.value = 0
  }
}

function syncTotalCount() {
  totalCount.value = raw.value?.entities?.length || 0
  if (_freshGraphData && _freshGraphData.entities?.length !== totalCount.value) {
    console.warn('graph: contentData has %d entities, live API has %d', totalCount.value, _freshGraphData.entities.length)
  }
}

// ── 预取最新图谱数据 ──
function _resolveDocId() {
  const gd = raw.value
  let id = gd?.document_id || gd?.data?.document_id
  if (!id) {
    const cd = contentStore.state.contentData
    id = cd?.document_id || cd?.data?.document_id
  }
  return id
}

async function preloadGraphData() {
  const docId = _resolveDocId()
  if (!docId) return
  try {
    const res = await fetch(`/api/documents/${docId}/knowledge-graph`)
    if (res.ok) _freshGraphData = await res.json()
  } catch {
    // 静默失败，任务快照是最低保障
  }
}

// ============= G6 渲染 =============

function createGraph() {
  if (!containerRef.value) return
  _rootsCache = computeRootsFromData(raw.value?.entities || [], getMergedRelations())
  if (!_rootsCache.length) return
  const box = containerRef.value.getBoundingClientRect()
  const cx = box.width / 2
  const cy = box.height / 2

  const initNodes = _rootsCache.map((e, i) => {
    const a = (i / _rootsCache.length) * 2 * Math.PI
    return {
      id: e.id,
      data: { label: e.name, entityType: e.entity_type, score: e.confidence || 0 },
      style: { x: cx + Math.cos(a) * 150, y: cy + Math.sin(a) * 150 },
    }
  })

  graph = new Graph({
    container: containerRef.value,
    data: { nodes: initNodes, edges: [] },
    node: {
      type: 'circle',
      style: {
        size: (d) => (d.data?.isVirtual ? 24 : 36),
        fill: (d) => COLORS[d.data?.entityType] || '#94a3b8',
        stroke: '#fff',
        lineWidth: 2,
        cursor: 'pointer',
        labelText: (d) => d.data?.label || d.id,
        labelFontSize: (d) => (d.data?.isVirtual ? 11 : 12),
        labelFill: (d) => (d.data?.isVirtual ? '#94a3b8' : '#334155'),
        labelPlacement: 'bottom',
        labelOffsetY: (d) => (d.data?.isVirtual ? 6 : 10),
        labelMaxWidth: 120,
        labelWordWrap: true,
        labelOverflow: 'ellipsis',
      },
      state: {
        selected: { fill: '#f97316', stroke: '#ea580c', lineWidth: 3 },
        highlighted: { fill: '#f97316', stroke: '#ea580c', lineWidth: 3 },
        expandable: { halo: true, haloOpacity: 0.25, haloLineWidth: 10, haloStroke: '#4F6AF0' },
      },
    },
    edge: {
      type: 'line',
      style: {
        stroke: '#94a3b8',
        lineWidth: 1.5,
        endArrow: true,
        labelText: (d) => d.data?.label || '',
        labelFontSize: 10,
        labelFill: '#64748b',
        labelBackground: true,
        labelBackgroundFill: '#fff',
        labelBackgroundOpacity: 0.85,
      },
      state: { highlighted: { stroke: '#f97316', lineWidth: 3 } },
    },
    layout: LAYOUT_CFG,
    behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element-force'],
  })

  graph.render()
  graph.fitCenter()
  graph.draw()
  bindEvents()
  refreshNodeStates()
  syncTotalCount()
  refreshCounts()
}

// ============= 事件绑定 =============

function bindEvents() {
  graph.on('node:click', (e) => {
    const id = e.target.id
    if (!id) return
    if (graphStore.state.mode === 'edit') {
      handleEditNodeClick(id)
      return
    }
    if (shift) {
      handlePath(id)
      return
    }
    graph.getNodeData(id)?.data?.isVirtual ? handleVirtual(id) : expandNode(id)
  })
  graph.on('edge:click', (e) => {
    if (graphStore.state.mode !== 'edit') return
    handleEditEdgeClick(e)
  })
  graph.on('canvas:click', () => {
    hideTooltip()
    if (graphStore.state.mode === 'edit') {
      clearEditSelection()
      return
    }
    clearPathResult()
  })
  graph.on('node:pointerenter', (e) => {
    const id = e.target.id
    if (!id || id.startsWith('more-') || graphStore.state.mode === 'edit') return
    const nd = graph.getNodeData(id)
    if (!nd) return
    tooltipTimer = setTimeout(() => {
      let desc = ''
      try {
        const rawEntity = raw.value?.entities?.find((en) => en.id === id)
        if (rawEntity) desc = rawEntity.description || rawEntity.introduction_context || ''
      } catch {
        // 查找失败不阻塞
      }
      tooltipData.value = {
        name: nd.data?.label || id,
        type: nd.data?.entityType || '',
        score: nd.data?.score || 0,
        desc,
      }
      tooltipVisible.value = true
    }, 200)
  })
  graph.on('node:pointerleave', hideTooltip)
}

function hideTooltip() {
  if (tooltipTimer) {
    clearTimeout(tooltipTimer)
    tooltipTimer = null
  }
  tooltipVisible.value = false
}

// ============= F1: 展开 =============

async function refreshNodeStates(ids) {
  if (!ids) {
    try {
      ids = graph.getNodeData().map((n) => n.id)
    } catch {
      return
    }
  }
  for (const id of ids) {
    if (_leafIds.has(id) || graphStore.isExpanded(id)) continue
    try {
      if (hasHiddenNeighbors(id)) {
        graph.setElementState(id, ['expandable'])
      } else {
        _leafIds.add(id)
        graph.setElementState(id, [])
      }
    } catch {
      // 节点可能已被删除
    }
  }
}

/**
 * 展开节点邻域。
 * @param {string} nodeId
 * @param {number} [offset=0] 分页偏移（0 为首批，>0 为"更多"续载）
 */
async function expandNode(nodeId, offset = 0) {
  // 并发保护
  if (loadingNodeId.value) return

  // offset=0：首次展开，需检查已展开 / 叶子标记
  if (offset === 0) {
    if (graphStore.isExpanded(nodeId)) return
    if (_leafIds.has(nodeId)) {
      graphStore.markExpanded(nodeId)
      return
    }
  }

  loadingNodeId.value = nodeId
  try {
    const qs = `entity_id=${nodeId}&limit=10${offset > 0 ? `&offset=${offset}` : ''}`
    const res = await fetch(`/api/graph/neighbors?${qs}`)
    if (!res.ok) return
    const d = await res.json()
    if (!d.neighbors?.length) {
      if (offset === 0) {
        graph.setElementState(nodeId, [])
        _leafIds.add(nodeId)
        graphStore.markExpanded(nodeId)
      }
      return
    }

    let p
    try {
      p = graph.getElementPosition(nodeId)
    } catch {
      // 用默认值
    }
    const px = p ? p[0] : 400
    const py = p ? p[1] : 300
    const g6n = []
    const g6e = []
    const ids = []

    d.neighbors.forEach((n, i) => {
      // 首次展开用均匀排列，续载用螺旋排列
      const angle =
        offset === 0
          ? (i / d.neighbors.length) * 2 * Math.PI + (nodeId.charCodeAt(0) % 60) * 0.1
          : i * 0.8 + (nodeId.charCodeAt(0) % 60) * 0.1
      const dist = offset === 0 ? 60 + (i % 3) * 15 : 70 + (i % 4) * 15

      if (!graph.hasNode(n.entity.id)) {
        g6n.push({
          id: n.entity.id,
          data: { label: n.entity.name, entityType: n.entity.entity_type, score: n.entity.score },
          style: { x: px + Math.cos(angle) * dist, y: py + Math.sin(angle) * dist },
        })
        ids.push(n.entity.id)
      }
      if (!graph.hasEdge(n.relation.id)) {
        g6e.push({
          id: n.relation.id,
          source: n.relation.source_entity_id || nodeId,
          target: n.relation.target_entity_id || n.entity.id,
          data: { label: n.relation.relation_type },
        })
      }
    })

    if (d.has_more) {
      const nextOffset = offset + 10
      g6n.push({
        id: `more-${nodeId}`,
        data: {
          label: `更多... (${d.total_count - nextOffset})`,
          entityType: 'virtual',
          isVirtual: true,
          nextOffset,
        },
        style: { x: px, y: py },
      })
      g6e.push({ id: `more-edge-${nodeId}`, source: nodeId, target: `more-${nodeId}`, data: { label: '' } })
    }

    graphStore.state.history.push({ type: 'expand', nodeId, addedNodeIds: ids, addedEdgeIds: g6e.map((e) => e.id) })
    if (g6n.length) graph.addNodeData(g6n)
    if (g6e.length) graph.addEdgeData(g6e)
    if (g6n.length || g6e.length) graph.render()

    if (offset === 0) {
      graphStore.markExpanded(nodeId)
      graph.setElementState(nodeId, [])
    }
    refreshNodeStates([nodeId, ...ids])
    refreshCounts()
    try {
      await graph.focusElement(nodeId, { duration: 150 })
    } catch {
      // 聚焦失败不阻塞
    }
  } catch (e) {
    console.error(e)
  } finally {
    loadingNodeId.value = null
  }
}

function handleVirtual(vid) {
  const orig = vid.replace(/^more-/, '')
  const nd = graph.getNodeData(vid)
  const nextOffset = nd?.data?.nextOffset || 10
  if (graph.hasNode(vid)) graph.removeNodeData([vid])
  expandNode(orig, nextOffset)
}

// ============= 编辑模式 =============

function clearEditSelection() {
  const sid = graphStore.state.selectedNodeId
  if (sid && graph.hasNode(sid)) {
    try {
      graph.setElementState(sid, [])
    } catch {
      // 忽略
    }
  }
  graphStore.setSelectedNode(null)
  closeEditor()
}

function setBrowseMode() {
  hideTooltip()
  clearEditSelection()
  graphStore.setMode('browse')
}

function setEditMode() {
  hideTooltip()
  clearPathResult()
  graphStore.setMode('edit')
}

function getNodeName(id) {
  const d = graph.getNodeData(id)
  return d?.data?.label || id
}

function handleEditNodeClick(id) {
  if (id.startsWith('more-')) return
  const sid = graphStore.state.selectedNodeId

  if (!sid) {
    // 第一击：选中
    graph.setElementState(id, 'selected')
    graphStore.setSelectedNode(id)
  } else if (sid === id) {
    // 再次单击同一节点：取消选中
    graph.setElementState(id, [])
    graphStore.setSelectedNode(null)
  } else {
    // 第二击（不同节点）：弹出编辑浮窗
    const edgeId = findEdgeBetween(sid, id)
    let hasExisting = false
    let relType = ''
    let desc = ''
    let relId = null

    if (edgeId) {
      const edgeData = graph.getEdgeData(edgeId)
      if (edgeData) {
        hasExisting = true
        relType = edgeData.data?.label || ''
        desc = edgeData.data?.description || ''
        relId = edgeData.id
        // 已有关系决定方向，不依赖点击顺序
        editor.sourceName = getNodeName(edgeData.source)
        editor.targetName = getNodeName(edgeData.target)
        editor.sourceId = edgeData.source
        editor.targetId = edgeData.target
      }
    }

    if (!hasExisting) {
      // 无已有关系，点击顺序决定方向
      editor.sourceName = getNodeName(sid)
      editor.targetName = getNodeName(id)
      editor.sourceId = sid
      editor.targetId = id
    }

    editor.relationType = relType
    editor.description = desc
    editor.hasExisting = hasExisting
    editor.mode = 'node'
    editor.relationId = relId
    editor.visible = true

    // 取消选中
    graph.setElementState(sid, [])
    graphStore.setSelectedNode(null)
  }
}

function handleEditEdgeClick(e) {
  const edgeId = e.itemId || e.target?.id
  if (!edgeId || !graph.hasEdge(edgeId)) return
  const edgeData = graph.getEdgeData(edgeId)
  if (!edgeData) return

  editor.sourceName = getNodeName(edgeData.source)
  editor.targetName = getNodeName(edgeData.target)
  editor.relationType = edgeData.data?.label || ''
  editor.description = edgeData.data?.description || ''
  editor.hasExisting = true
  editor.mode = 'edge'
  editor.relationId = edgeId
  editor.sourceId = edgeData.source
  editor.targetId = edgeData.target
  editor.visible = true
}

function findEdgeBetween(a, b) {
  try {
    const edges = graph.getEdgeData()
    for (const e of edges) {
      if ((e.source === a && e.target === b) || (e.source === b && e.target === a)) {
        return e.id
      }
    }
  } catch {
    // 查询失败返回 null
  }
  return null
}

function onEditorSave({ relationType, description }) {
  const srcId = editor.sourceId
  const tgtId = editor.targetId
  const relId = editor.relationId
  const prevType = editor.relationType
  const prevDesc = editor.description

  if (relId && graph.hasEdge(relId)) {
    // ── 更新已有关系 ──
    const existingId = relId.startsWith('manual-') ? null : relId
    graphStore.pushEditHistory({
      type: 'update',
      relationId: relId,
      previousType: prevType,
      previousDescription: prevDesc,
    })
    if (existingId) {
      fetch(`/api/graph/relations/${existingId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ relation_type: relationType, description }),
      }).catch(() => {})
    }
    graph.updateEdgeData([{ id: relId, data: { label: relationType, description } }])
    graph.draw()
  } else {
    // ── 创建新关系 ──
    const fromId = srcId
    const toId = tgtId
    const tempId = `creating-${fromId}-${toId}-${Date.now()}`

    graphStore.pushEditHistory({ type: 'create', sourceId: fromId, targetId: toId, relationId: tempId })
    graph.addEdgeData([{ id: tempId, source: fromId, target: toId, data: { label: relationType, description } }])
    graph.draw()

    fetch('/api/graph/relations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_entity_id: fromId, target_entity_id: toId, relation_type: relationType, description }),
    })
      .then((res) => {
        if (!res.ok) throw new Error('保存失败')
        return res.json()
      })
      .then((data) => {
        graph.removeEdgeData([tempId])
        graph.addEdgeData([
          {
            id: data.id,
            source: data.source_entity_id,
            target: data.target_entity_id,
            data: { label: data.relation_type, description },
          },
        ])
        graph.draw()
        // 注入 contentData 使下次 computeRoots 能识别合并后的连通分量
        try {
          const gd = contentStore.state.contentData
          const rels = (gd.data || gd).relations
          if (rels) rels.push({ id: data.id, source_entity_id: data.source_entity_id, target_entity_id: data.target_entity_id, relation_type: data.relation_type })
        } catch {}
        // 更新 undo history 中的 relationId
        const last = graphStore.state.editHistory[graphStore.state.editHistory.length - 1]
        if (last) last.relationId = data.id
        // 清除两端节点的叶子标记，使它们重新可展开
        _leafIds.delete(data.source_entity_id)
        _leafIds.delete(data.target_entity_id)
        refreshNodeStates([data.source_entity_id, data.target_entity_id])
      })
      .catch(() => {
        // 保留临时边作为本地 fallback
        graph.updateEdgeData([{ id: tempId, data: { label: `${relationType} (离线)` } }])
      })
  }
  closeEditor()
}

function onEditorDelete() {
  const relId = editor.relationId
  if (!relId || !graph.hasEdge(relId)) {
    closeEditor()
    return
  }
  const edgeData = graph.getEdgeData(relId)

  graphStore.pushEditHistory({
    type: 'delete',
    relationId: relId,
    sourceId: edgeData.source,
    targetId: edgeData.target,
    relationType: edgeData.data?.label || '',
    description: edgeData.data?.description || '',
  })

  const existingId = relId.startsWith('manual-') ? null : relId
  if (existingId) {
    fetch(`/api/graph/relations/${existingId}`, { method: 'DELETE' }).catch(() => {})
  }

  graph.removeEdgeData([relId])

  // 从 contentData 移除该关系，使叶子判定正确
  try {
    const gd = contentStore.state.contentData
    const rels = (gd.data || gd).relations
    if (rels) {
      const idx = rels.findIndex((r) => r.id === relId)
      if (idx !== -1) rels.splice(idx, 1)
    }
  } catch {}

  // 刷新两端节点的展开状态
  _leafIds.delete(edgeData.source)
  _leafIds.delete(edgeData.target)
  graph.render()
  refreshNodeStates([edgeData.source, edgeData.target])
  closeEditor()
}

function onEditorCancel() {
  const sid = graphStore.state.selectedNodeId
  if (sid && graph.hasNode(sid)) {
    try {
      graph.setElementState(sid, [])
    } catch {
      // 忽略
    }
  }
  graphStore.setSelectedNode(null)
  closeEditor()
}

// ============= F2: 路径 =============

function handlePath(id) {
  if (id.startsWith('more-')) return
  clearHighlight()
  if (!pathFrom) {
    pathFrom = id
    graph.setElementState(id, 'selected')
  } else if (pathFrom === id) {
    graph.setElementState(id, [])
    pathFrom = null
  } else {
    const f = pathFrom
    pathFrom = null
    findPath(f, id)
  }
}

async function findPath(a, b) {
  try {
    const res = await fetch(`/api/graph/path?from_id=${a}&to_id=${b}`)
    if (!res.ok) {
      pathText.value = '未找到路径'
      return
    }
    const d = await res.json()
    d.path.forEach((id) => {
      if (graph.hasNode(id)) graph.setElementState(id, 'highlighted')
    })
    d.edges.forEach((e) => {
      if (e.relation_id && graph.hasEdge(e.relation_id)) graph.setElementState(e.relation_id, 'highlighted')
    })
    graphStore.state.highlightedPathNodes = d.path
    graphStore.state.highlightedPathEdges = d.edges
    pathText.value = d.text
  } catch (e) {
    pathText.value = '路径查询失败'
  }
}

function clearHighlight() {
  graphStore.state.highlightedPathNodes.forEach((id) => {
    try {
      graph.setElementState(id, [])
    } catch {
      // 忽略
    }
  })
  graphStore.state.highlightedPathEdges.forEach((e) => {
    if (e.relation_id)
      try {
        graph.setElementState(e.relation_id, [])
      } catch {
        // 忽略
      }
  })
  graphStore.clearHighlight()
}

function clearPathResult() {
  clearHighlight()
  pathText.value = ''
  if (pathFrom) {
    graph.setElementState(pathFrom, [])
    pathFrom = null
  }
}

// ============= 键盘 / 撤销 =============

function onKeyDown(e) {
  if (e.key === 'Shift') shift = true
  if (e.key === 'Escape') {
    if (editor.visible) {
      onEditorCancel()
      return
    }
    if (graphStore.state.mode === 'edit') {
      clearEditSelection()
      return
    }
  }
  if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
    e.preventDefault()
    undo()
  }
}
function onKeyUp(e) {
  if (e.key === 'Shift') {
    shift = false
    if (pathFrom) {
      graph?.setElementState(pathFrom, [])
      pathFrom = null
    }
  }
}

function undo() {
  graphStore.state.mode === 'edit' ? undoEdit() : undoBrowse()
}

function undoBrowse() {
  const entry = graphStore.popHistory()
  if (!entry || entry.type !== 'expand') return
  const { addedNodeIds: nids, addedEdgeIds: eids } = entry
  if (nids.length) graph.removeNodeData(nids)
  if (eids.length) graph.removeEdgeData(eids)
  graph.render()
  graphStore.state.expandedIds = graphStore.state.expandedIds.filter((id) => id !== entry.nodeId)
  refreshCounts()
}

function undoEdit() {
  const entry = graphStore.popEditHistory()
  if (!entry) return

  if (entry.type === 'create') {
    if (entry.relationId && graph.hasEdge(entry.relationId)) {
      graph.removeEdgeData([entry.relationId])
    }
    try {
      const gd = contentStore.state.contentData
      const rels = (gd.data || gd).relations
      if (rels) {
        const idx = rels.findIndex((r) => r.id === entry.relationId)
        if (idx !== -1) rels.splice(idx, 1)
      }
    } catch {}
    _leafIds.delete(entry.sourceId)
    _leafIds.delete(entry.targetId)
    graph.draw()
    refreshNodeStates([entry.sourceId, entry.targetId])
    if (entry.relationId && !entry.relationId.startsWith('manual-')) {
      fetch(`/api/graph/relations/${entry.relationId}`, { method: 'DELETE' }).catch(() => {})
    }
  } else if (entry.type === 'update') {
    if (entry.relationId && graph.hasEdge(entry.relationId)) {
      graph.updateEdgeData([{ id: entry.relationId, data: { label: entry.previousType, description: entry.previousDescription } }])
      graph.draw()
    }
    if (entry.relationId && !entry.relationId.startsWith('manual-')) {
      fetch(`/api/graph/relations/${entry.relationId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ relation_type: entry.previousType, description: entry.previousDescription }),
      }).catch(() => {})
    }
  } else if (entry.type === 'delete') {
    const fromId = entry.sourceId
    const toId = entry.targetId
    fetch('/api/graph/relations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_entity_id: fromId, target_entity_id: toId, relation_type: entry.relationType, description: entry.description }),
    })
      .then((res) => {
        if (!res.ok) throw new Error()
        return res.json()
      })
      .then((data) => {
        graph.addEdgeData([
          {
            id: data.id,
            source: data.source_entity_id,
            target: data.target_entity_id,
            data: { label: data.relation_type, description: entry.description },
          },
        ])
        try {
          const gd = contentStore.state.contentData
          const rels = (gd.data || gd).relations
          if (rels) rels.push({ id: data.id, source_entity_id: data.source_entity_id, target_entity_id: data.target_entity_id, relation_type: data.relation_type })
        } catch {}
        _leafIds.delete(data.source_entity_id)
        _leafIds.delete(data.target_entity_id)
        graph.draw()
        refreshNodeStates([data.source_entity_id, data.target_entity_id])
      })
      .catch(() => {
        const fallbackId = `manual-${fromId}-${toId}`
        graph.addEdgeData([{ id: fallbackId, source: fromId, target: toId, data: { label: entry.relationType, description: entry.description } }])
        graph.draw()
      })
  }
}

// ============= 生命周期 =============

function init() {
  if (graph) return
  if (!containerRef.value || !hasData.value) {
    syncTotalCount()
    return
  }
  createGraph()
}

function destroy() {
  hideTooltip()
  _rootsCache = null
  _leafIds = new Set()
  graphStore.state.expandedIds = []
  graphStore.state.history = []
  graphStore.state.mode = 'browse'
  graphStore.state.selectedNodeId = null
  graphStore.state.editHistory = []
  pathFrom = null
  shift = false
  closeEditor()
  if (graph) {
    graph.destroy()
    graph = null
  }
  refreshCounts()
  totalCount.value = 0
}

onMounted(async () => {
  await preloadGraphData()
  nextTick(init)
  addEventListener('keydown', onKeyDown)
  addEventListener('keyup', onKeyUp)
})
onActivated(async () => {
  await preloadGraphData()
  nextTick(init)
  addEventListener('keydown', onKeyDown)
  addEventListener('keyup', onKeyUp)
})
onDeactivated(() => {
  removeEventListener('keydown', onKeyDown)
  removeEventListener('keyup', onKeyUp)
  destroy()
})
onUnmounted(() => {
  removeEventListener('keydown', onKeyDown)
  removeEventListener('keyup', onKeyUp)
  destroy()
})
</script>

<style scoped>
.knowledge-graph { height: 100%; display: flex; flex-direction: column; background: #f8fafc; }
.kg-empty { text-align: center; color: var(--p-text-muted); padding: 60px 24px; font-size: 13px; flex: 1; display: flex; align-items: center; justify-content: center; }
.kg-layout { flex: 1; display: flex; flex-direction: column; min-height: 0; position: relative; }
.kg-toolbar { display: flex; align-items: center; gap: 10px; padding: 8px 16px; border-bottom: 1px solid var(--p-border); background: #fff; flex-shrink: 0; z-index: 1; }
.kg-hint { font-size: 11px; color: var(--p-text-muted); flex: 1; }
.kg-counts { font-size: 11px; color: #94a3b8; white-space: nowrap; flex-shrink: 0; letter-spacing: 0.02em; }
.kg-clear-btn { font-size: 11px; padding: 3px 10px; border: 1px solid var(--p-border); border-radius: 12px; background: #fff; color: var(--p-text-muted); cursor: pointer; }
.kg-clear-btn:hover { border-color: #f97316; color: #f97316; }
.kg-mode-toggle { display: flex; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; flex-shrink: 0; }
.kg-mode-btn { font-size: 11px; padding: 3px 12px; border: none; background: #fff; color: #64748b; cursor: pointer; transition: background 0.15s, color 0.15s; }
.kg-mode-btn:first-child { border-right: 1px solid #e2e8f0; }
.kg-mode-btn.active { background: #4F6AF0; color: #fff; }
.kg-mode-btn:not(.active):hover { background: #f8fafc; color: #1e293b; }
.kg-status-bar { display: flex; align-items: center; gap: 8px; padding: 8px 16px; background: #fff7ed; border-top: 1px solid #fed7aa; font-size: 12px; color: #9a3412; cursor: pointer; }
.kg-status-bar:hover { background: #ffedd5; }
.kg-path-icon { font-size: 14px; flex-shrink: 0; }
.kg-path-text { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kg-path-dismiss { flex-shrink: 0; font-size: 14px; opacity: .5; }
.kg-canvas-wrap { flex: 1; min-height: 0; position: relative; }
.kg-canvas { width: 100%; height: 100%; }
.kg-info-bar { position: absolute; top: 0; left: 0; right: 0; padding: 6px 16px; background: rgba(255,255,255,0.95); border-bottom: 1px solid #e2e8f0; font-size: 12px; min-height: 32px; z-index: 15; pointer-events: none; }
.kg-ib-row { display: flex; align-items: center; gap: 8px; }
.kg-ib-name { font-weight: 600; color: #0f172a; }
.kg-ib-type { padding: 1px 6px; border-radius: 4px; color: #fff; font-size: 10px; font-weight: 500; flex-shrink: 0; }
.kg-ib-desc { color: #64748b; font-size: 11px; line-height: 1.4; margin-top: 2px; }
.slide-up-enter-active { transition: transform .2s ease-out,opacity .2s; }
.slide-up-leave-active { transition: transform .15s ease-in,opacity .15s; }
.slide-up-enter-from { transform: translateY(100%); opacity: 0; }
.slide-up-leave-to { transform: translateY(100%); opacity: 0; }
.slide-down-enter-active { transition: transform .15s ease-out,opacity .15s; }
.slide-down-leave-active { transition: transform .1s ease-in,opacity .1s; }
.slide-down-enter-from { transform: translateY(-100%); opacity: 0; }
.slide-down-leave-to { transform: translateY(-100%); opacity: 0; }
</style>
