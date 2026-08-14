<template>
  <div class="entities-view">
    <!-- Loading (仅首次加载显示，筛选项切换永不触发) -->
    <div v-if="isLoading && !hasLoadedOnce" class="ev-loading">加载中...</div>

    <div class="ev-layout">
      <!-- Toolbar: Search + Sort + Type Filter + Export -->
      <div class="ev-toolbar">
        <div class="ev-search-wrap">
          <input
            v-model="searchQuery"
            class="ev-search"
            placeholder="🔍 搜索实体名称或描述..."
            @input="onSearchInput"
          />
        </div>
        <select v-model="sortBy" class="ev-select" @change="fetchEntities">
          <option value="name_asc">名称 (A-Z)</option>
          <option value="name_desc">名称 (Z-A)</option>
          <option value="created_desc">创建时间 (最新)</option>
          <option value="created_asc">创建时间 (最早)</option>
        </select>
        <select v-model="typeFilter" class="ev-select" @change="fetchEntities">
          <option value="">全部类型</option>
          <option value="concept">概念</option>
          <option value="theorist">理论家</option>
          <option value="theory">理论</option>
          <option value="method">方法</option>
          <option value="fact">事实</option>
        </select>
        <button class="ev-btn ev-btn-export" @click="showExportDialog = true">📥 导出</button>
      </div>

      <!-- Filter Tabs -->
      <div class="ev-tabs">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          :class="['ev-tab', { active: activeTab === tab.key }]"
          @click="switchTab(tab.key)"
        >
          {{ tab.label }}
          <span class="ev-tab-count">{{ tab.count }}</span>
        </button>
      </div>

      <!-- Entity Cards -->
      <div class="ev-list">
        <div
          v-for="entity in entities"
          :key="entity.id"
          class="ev-card"
          @click="openEdit(entity)"
        >
          <div class="ev-card-header">
            <span class="ev-name">{{ entity.name }}</span>
            <span :class="['ev-type', 'type-' + (entity.entity_type || 'concept')]">
              {{ typeLabel(entity.entity_type) }}
            </span>
            <span v-if="entity.source === 'manual'" class="ev-source-tag">手动</span>
          </div>
          <div v-if="entity.description" class="ev-desc">{{ entity.description }}</div>
          <div v-if="entity.introduction_context" class="ev-ctx">
            <span class="ev-ctx-label">上下文：</span>{{ entity.introduction_context }}
          </div>

          <!-- Status toggle row -->
          <div class="ev-status-row" @click.stop>
            <span class="ev-status-label">状态：</span>
            <button
              v-for="opt in statusOptions"
              :key="opt.key"
              :class="['ev-status-btn', { active: (entity.filter_action || 'pending') === opt.key }]"
              @click="changeStatus(entity, opt.key)"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>

        <!-- Scroll bottom placeholder -->
        <div class="ev-placeholder"></div>

        <div v-if="entities.length === 0 && !isLoading" class="ev-empty">
          {{ activeTab === 'review' ? '暂无待审核实体' : '暂无实体' }}
        </div>
      </div>
    </div>

    <!-- Edit Dialog -->
    <EntityEditDialog
      :visible="editDialog.visible"
      :entity="editDialog.entity"
      @close="editDialog.visible = false"
      @saved="onEntitySaved"
    />

    <!-- Export Dialog -->
    <EntityExportDialog
      :visible="showExportDialog"
      :document-id="docId"
      :current-filter-action="activeTab === 'all' ? null : activeTab"
      :filtered-count="entities.length"
      :total-count="documentTotalCount"
      @close="showExportDialog = false"
    />
  </div>
</template>

<script setup>
import { ref, computed, reactive, watch, onMounted } from 'vue'
import { useDocumentStore } from '../../stores/useDocumentStore'
import EntityEditDialog from './EntityEditDialog.vue'
import EntityExportDialog from './EntityExportDialog.vue'

const API_BASE = ''
const docStore = useDocumentStore()

const docId = computed(() => docStore.state.selectedDocumentId)

const isLoading = ref(false)
const hasLoadedOnce = ref(false)
const entities = ref([])
const totalCount = ref(0)
const documentTotalCount = ref(0)
const activeTab = ref('all')

// Toolbar state
const searchQuery = ref('')
const sortBy = ref('name_asc')
const typeFilter = ref('')
const showExportDialog = ref(false)

const editDialog = reactive({
  visible: false,
  entity: {},
})

const statusOptions = [
  { key: 'keep', label: '✅ 已确认' },
  { key: 'review', label: '⏳ 待审核' },
  { key: 'discard', label: '🗑️ 已过滤' },
]

// ── Search debounce ──
let searchTimer = null
function onSearchInput() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    fetchEntities()
  }, 300)
}

// ── Tabs ──
const tabs = computed(() => [
  { key: 'all', label: '全部', count: documentTotalCount.value },
  { key: 'keep', label: '✅ 已确认' },
  { key: 'review', label: '⏳ 待审核' },
  { key: 'discard', label: '🗑️ 已过滤' },
])

function switchTab(key) {
  activeTab.value = key
  fetchEntities()
}

// ── Labels ──
const typeLabels = { concept: '概念', theorist: '理论家', theory: '理论', method: '方法', fact: '事实' }

function typeLabel(t) { return typeLabels[t] || t || '概念' }

// ── Fetch ──
async function fetchEntities() {
  const id = docId.value
  if (!id) {
    entities.value = []
    totalCount.value = 0
    return
  }
  isLoading.value = true
  try {
    const params = new URLSearchParams()
    params.set('document_id', id)
    if (activeTab.value !== 'all') params.set('filter_action', activeTab.value)
    if (searchQuery.value.trim()) params.set('search', searchQuery.value.trim())
    params.set('sort_by', sortBy.value)
    if (typeFilter.value) params.set('entity_type', typeFilter.value)
    params.set('limit', '500')

    const res = await fetch(`${API_BASE}/api/entities?${params}`)
    if (res.ok) {
      const data = await res.json()
      entities.value = data.entities || []
      totalCount.value = data.total || 0
      hasLoadedOnce.value = true
    }
  } catch {
    // ignore
  } finally {
    isLoading.value = false
  }
}

// ── Status Toggle ──
async function changeStatus(entity, newAction) {
  const current = entity.filter_action || 'pending'
  if (current === newAction) return

  try {
    const res = await fetch(`${API_BASE}/api/entities/${entity.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filter_action: newAction }),
    })
    if (res.ok) {
      const updated = await res.json()
      entity.filter_action = updated.filter_action
      docStore.refreshHighlights()
    }
  } catch {
    // ignore
  }
}

// ── Edit ──
function openEdit(entity) {
  editDialog.entity = { ...entity }
  editDialog.visible = true
}

function onEntitySaved(updated) {
  const idx = entities.value.findIndex(e => e.id === updated.id)
  if (idx !== -1) {
    entities.value[idx] = { ...entities.value[idx], ...updated }
  }
  editDialog.visible = false
  docStore.refreshHighlights()
  setTimeout(fetchEntities, 100)
}

// ── 文档实体总数（不受筛选影响） ──
async function fetchDocumentTotal() {
  const id = docId.value
  if (!id) { documentTotalCount.value = 0; return }
  try {
    const res = await fetch(`${API_BASE}/api/entities?document_id=${id}&limit=1`)
    if (res.ok) {
      const data = await res.json()
      documentTotalCount.value = data.total || 0
    }
  } catch {
    // ignore
  }
}

// ── Lifecycle ──
watch(docId, () => {
  searchQuery.value = ''
  activeTab.value = 'all'
  sortBy.value = 'name_asc'
  typeFilter.value = ''
  hasLoadedOnce.value = false
  documentTotalCount.value = 0
  fetchEntities()
  fetchDocumentTotal()
})

onMounted(() => {
  fetchEntities()
  fetchDocumentTotal()
})
</script>

<style scoped>
.entities-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  position: relative;
}

.ev-loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--p-surface);
  z-index: 2;
  color: var(--p-text-muted);
  font-size: 13px;
}

.ev-layout {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

/* ── Toolbar ── */
.ev-toolbar {
  display: flex;
  gap: 8px;
  padding: 10px 16px 6px;
  flex-shrink: 0;
  flex-wrap: wrap;
  align-items: center;
}

.ev-search-wrap {
  flex: 1;
  min-width: 140px;
}

.ev-search {
  width: 100%;
  padding: 6px 10px;
  border: 1px solid var(--p-border);
  border-radius: var(--r-sm);
  font-size: 12px;
  color: var(--p-text);
  background: var(--p-surface);
  outline: none;
  box-sizing: border-box;
  font-family: inherit;
}

.ev-search:focus {
  border-color: var(--p-primary);
  box-shadow: 0 0 0 3px rgba(79, 106, 240, 0.12);
}

.ev-search::placeholder {
  color: var(--p-text-muted);
}

.ev-select {
  padding: 6px 10px;
  border: 1px solid var(--p-border);
  border-radius: var(--r-sm);
  font-size: 12px;
  color: var(--p-text);
  background: var(--p-surface);
  outline: none;
  cursor: pointer;
  font-family: inherit;
  max-width: 150px;
}

.ev-select:focus {
  border-color: var(--p-primary);
}

/* ── Tabs ── */
.ev-tabs {
  display: flex;
  gap: 6px;
  padding: 6px 16px 8px;
  border-bottom: 1px solid var(--p-border);
  flex-shrink: 0;
  flex-wrap: wrap;
}

.ev-tab {
  font-size: 12px;
  font-weight: 500;
  padding: 5px 14px;
  border: 1px solid var(--p-border);
  border-radius: 16px;
  background: var(--p-surface);
  color: var(--p-text-secondary);
  cursor: pointer;
  transition: all 0.12s;
  display: flex;
  align-items: center;
  gap: 5px;
}

.ev-tab:hover {
  border-color: #cbd5e1;
  color: var(--p-text);
}

.ev-tab.active {
  background: var(--p-primary-light);
  border-color: var(--p-primary);
  color: var(--p-primary);
}

.ev-tab-count {
  font-size: 11px;
  opacity: 0.7;
}

/* ── List ── */
.ev-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px 20px 80px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ev-placeholder {
  height: 1px;
  flex-shrink: 0;
}

.ev-empty {
  text-align: center;
  color: var(--p-text-muted);
  padding: 40px 24px;
  font-size: 13px;
}

/* ── Card ── */
.ev-card {
  background: var(--p-surface);
  border: 1px solid var(--p-border);
  border-radius: var(--r-md);
  padding: 10px 14px;
  transition: border-color 0.12s ease, box-shadow 0.12s ease;
  cursor: pointer;
}

.ev-card:hover {
  border-color: #cbd5e1;
  box-shadow: var(--shadow-xs);
}

.ev-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  flex-wrap: wrap;
}

.ev-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--p-text);
}

.ev-type {
  font-size: 11px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 20px;
}

.type-concept { background: #EEF0FF; color: var(--p-primary); }
.type-theorist { background: #fef3c7; color: #d97706; }
.type-theory { background: #f0fdf4; color: #16a34a; }
.type-method { background: #fce7f3; color: #be185d; }
.type-fact { background: #ede9fe; color: #7c3aed; }

.ev-source-tag {
  font-size: 10px;
  color: var(--p-primary);
  background: var(--p-primary-light);
  padding: 1px 7px;
  border-radius: 8px;
  margin-left: 2px;
}

.ev-desc {
  font-size: 13px;
  color: var(--p-text-secondary);
  margin-top: 4px;
}

.ev-ctx {
  font-size: 12px;
  color: var(--p-text-muted);
  margin-top: 4px;
  padding: 5px 8px;
  background: var(--p-surface-subtle);
  border-radius: var(--r-sm);
  line-height: 1.5;
  max-height: 42px;
  overflow: hidden;
}

.ev-ctx-label {
  font-weight: 500;
  color: var(--p-text-secondary);
}

/* ── Status toggle row ── */
.ev-status-row {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px solid var(--p-border);
}

.ev-status-label {
  font-size: 11px;
  color: var(--p-text-muted);
  margin-right: 2px;
  flex-shrink: 0;
}

.ev-status-btn {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  border: 1px solid var(--p-border);
  background: var(--p-surface);
  color: var(--p-text-muted);
  cursor: pointer;
  transition: all 0.1s;
  font-family: inherit;
  line-height: 1.5;
}

.ev-status-btn:hover {
  border-color: #cbd5e1;
  color: var(--p-text-secondary);
}

.ev-status-btn.active {
  border-color: transparent;
  cursor: default;
}

.ev-status-btn[data-action="keep"].active,
.ev-status-btn.active:first-child { background: #dcfce7; color: #16a34a; }

.ev-status-btn[data-action="review"].active,
.ev-status-btn.active:nth-child(2) { background: #fef9c3; color: #ca8a04; }

.ev-status-btn[data-action="discard"].active,
.ev-status-btn.active:nth-child(3) { background: #fee2e2; color: #dc2626; }

/* ── Export button ── */
.ev-btn-export {
  font-size: 12px;
  padding: 6px 12px;
  border: 1px solid var(--p-border);
  border-radius: var(--r-sm);
  background: var(--p-surface);
  color: var(--p-text-secondary);
  cursor: pointer;
  transition: all 0.1s;
  white-space: nowrap;
}

.ev-btn-export:hover {
  background: var(--p-surface-muted);
  border-color: #cbd5e1;
}

/* ── Scrollbar ── */
.ev-list::-webkit-scrollbar { width: 4px; }
.ev-list::-webkit-scrollbar-thumb { background: transparent; border-radius: 2px; }
.ev-list:hover::-webkit-scrollbar-thumb { background: var(--p-border); }
</style>
