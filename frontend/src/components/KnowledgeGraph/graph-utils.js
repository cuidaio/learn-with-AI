/**
 * Knowledge Graph 工具函数
 * 纯计算函数，无 G6 / Vue 依赖，可独立测试。
 */

export const TYPE_LABELS = {
  concept: '概念',
  theorist: '理论家',
  theory: '理论',
  method: '方法',
  fact: '事实',
}

export const COLORS = {
  concept: '#4F6AF0',
  theorist: '#d97706',
  theory: '#16a34a',
  method: '#be185d',
  fact: '#7c3aed',
  virtual: '#94a3b8',
}

export const LAYOUT_CFG = {
  type: 'd3-force',
  link: { distance: 120, strength: 0.5 },
  manyBody: { strength: -500, distanceMax: 500 },
  collide: { radius: 35, strength: 0.8 },
  center: { strength: 0.3 },
  alpha: 0.3,
  alphaDecay: 0.1,
  alphaMin: 0.01,
}

/** 构建无向邻接表（source/target 双向入表） */
export function buildAdjacencyMap(relations) {
  const adj = {}
  for (const r of relations) {
    const s = r.source_entity_id
    const t = r.target_entity_id
    ;(adj[s] || (adj[s] = [])).push(t)
    ;(adj[t] || (adj[t] = [])).push(s)
  }
  return adj
}

/** BFS 切分连通分量，返回分量列表（每项为 id[]） */
export function computeComponents(entities, adj) {
  const visited = new Set()
  const comps = []
  for (const e of entities) {
    if (visited.has(e.id)) continue
    const comp = []
    const stack = [e.id]
    while (stack.length) {
      const id = stack.pop()
      if (visited.has(id)) continue
      visited.add(id)
      comp.push(id)
      for (const nb of adj[id] || []) {
        if (!visited.has(nb)) stack.push(nb)
      }
    }
    comps.push(comp)
  }
  return comps
}

/**
 * 特征向量中心性（幂迭代）
 * @param {Object<string, string[]>} adj 无向邻接表
 * @param {string[]} nodeIds 子集节点 ID
 * @returns {Object<string, number>} 节点 → 中心性分数
 */
export function computeEigenvectorCentrality(adj, nodeIds) {
  const n = nodeIds.length
  if (!n) return {}
  const idx = {}
  nodeIds.forEach((id, i) => {
    idx[id] = i
  })
  // 构建子集内的邻居索引列表（稀疏矩阵）
  const neighbors = nodeIds.map(
    (id) => (adj[id] || []).map((nb) => idx[nb]).filter((i) => i !== undefined),
  )
  let x = new Float64Array(n).fill(1)
  for (let iter = 0; iter < 100; iter++) {
    const y = new Float64Array(n)
    for (let i = 0; i < n; i++) {
      for (const j of neighbors[i]) y[i] += x[j]
    }
    const norm = Math.max(...y) || 1
    let diff = 0
    for (let i = 0; i < n; i++) {
      y[i] /= norm
      diff = Math.max(diff, Math.abs(y[i] - x[i]))
    }
    x = y
    if (diff < 1e-8) break
  }
  const result = {}
  nodeIds.forEach((id, i) => {
    result[id] = x[i]
  })
  return result
}

/**
 * 从实体列表和关系中计算根节点（每个连通分量选取特征向量中心性最高的实体）。
 * @param {Array} entities 实体列表（需含 .id）
 * @param {Array} relations 关系列表（需含 source_entity_id / target_entity_id）
 * @returns {Array} 根节点实体列表
 */
export function computeRootsFromData(entities, relations) {
  if (!entities?.length) return []
  const adj = buildAdjacencyMap(relations)
  const comps = computeComponents(entities, adj)
  const map = {}
  for (const e of entities) map[e.id] = e
  return comps.map((comp) => {
    const ec = computeEigenvectorCentrality(adj, comp)
    let best = comp[0]
    for (const id of comp) {
      if ((ec[id] || 0) > (ec[best] || 0)) best = id
    }
    return map[best]
  })
}

/**
 * 查询某实体的所有邻接实体 ID（双向）。
 * @param {string} entityId
 * @param {Array} relations
 * @returns {string[]}
 */
export function queryNeighborIds(entityId, relations) {
  const ids = new Set()
  for (const r of relations) {
    if (r.source_entity_id === entityId) ids.add(r.target_entity_id)
    if (r.target_entity_id === entityId) ids.add(r.source_entity_id)
  }
  return [...ids]
}

/** 实体类型中文标签 */
export function typeLabel(t) {
  return TYPE_LABELS[t] || t || '未知'
}
