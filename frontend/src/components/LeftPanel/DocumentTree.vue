<template>
  <div class="document-tree">
    <div class="tree-header">
      <span class="tree-title">我的资料库</span>
      <div class="tree-actions">
        <button class="btn-icon" title="上传文档" @click="openUpload">＋ 上传</button>
        <button class="btn-icon" title="新建文件夹" @click="createFolder">＋ 新建</button>
      </div>
    </div>

    <div v-if="docStore.state.isLoading" class="tree-empty">加载中...</div>
    <div v-else-if="folders.length === 0 && documents.length === 0" class="tree-empty">
      暂无资料，点击「＋ 上传」添加文档
    </div>

    <div v-else class="tree-body" @drop.prevent="onTreeBodyDrop" @dragover.prevent>
      <!-- 文件夹列表 -->
      <div v-for="folder in folders" :key="folder.id" class="folder-section">
        <div
          :class="['folder-header', { 'drag-over': dragOverFolderId === folder.id }]"
          @click="toggleFolder(folder.id)"
          @contextmenu.prevent="openFolderContextMenu($event, folder)"
          @dragover.prevent="onFolderDragOver(folder.id)"
          @dragleave="onFolderDragLeave"
          @drop.prevent="onFolderDrop(folder.id)"
        >
          <span class="folder-icon">{{ isExpanded(folder.id) ? '📂' : '📁' }}</span>
          <span v-if="renamingFolderId !== folder.id" class="folder-name">{{ folder.name }}</span>
          <input
            v-else
            :ref="(el) => { if (el) renameInputEl = el }"
            v-model="renameValue"
            class="rename-input folder-rename"
            @blur="commitFolderRename(folder)"
            @keydown.enter="commitFolderRename(folder)"
            @keydown.escape="cancelRename"
            @click.stop
          />
          <span class="folder-count">{{ folderDocs(folder.id).length }}</span>
          <span class="folder-arrow">{{ isExpanded(folder.id) ? '▾' : '▸' }}</span>
        </div>

        <div v-if="isExpanded(folder.id)" class="folder-children">
          <div
            v-for="doc in folderDocs(folder.id)"
            :key="doc.id"
            :class="['tree-item', { selected: docStore.state.selectedDocumentId === doc.id, 'drag-over-top': dragInsertPos?.docId === doc.id && dragInsertPos?.pos === 'before', 'drag-over-bottom': dragInsertPos?.docId === doc.id && dragInsertPos?.pos === 'after' }]"
            draggable="true"
            :title="doc.user_title || doc.title"
            @click="selectDoc(doc)"
            @contextmenu.prevent="openDocContextMenu($event, doc)"
            @dragstart="onDragStart($event, doc)"
            @dragend="onDragEnd"
            @dragover.prevent="onDocDragOver(doc, $event)"
            @dragleave="onDocDragLeave"
            @drop.prevent="onDocDropOnDoc(doc)"
          >
            <span class="drag-handle">⠿</span>
            <span v-if="renamingDocId !== doc.id" class="item-name">{{ doc.user_title || doc.title }}</span>
            <input
              v-else
              :ref="(el) => { if (el) renameInputEl = el }"
              v-model="renameValue"
              class="rename-input"
              @blur="commitDocRename(doc)"
              @keydown.enter="commitDocRename(doc)"
              @keydown.escape="cancelRename"
              @click.stop
            />
          </div>
        </div>
      </div>

      <!-- 无文件夹的文档 -->
      <div v-if="rootDocuments.length" class="root-section-label">未分类</div>
      <div
        v-for="doc in rootDocuments"
        :key="doc.id"
        :class="['tree-item', { selected: docStore.state.selectedDocumentId === doc.id, 'drag-over-top': dragInsertPos?.docId === doc.id && dragInsertPos?.pos === 'before', 'drag-over-bottom': dragInsertPos?.docId === doc.id && dragInsertPos?.pos === 'after' }]"
        draggable="true"
        :title="doc.user_title || doc.title"
        @click="selectDoc(doc)"
        @contextmenu.prevent="openDocContextMenu($event, doc)"
        @dragstart="onDragStart($event, doc)"
        @dragend="onDragEnd"
        @dragover.prevent="onDocDragOver(doc, $event)"
        @dragleave="onDocDragLeave"
        @drop.prevent="onDocDropOnDoc(doc)"
      >
        <span class="drag-handle">⠿</span>
        <span v-if="renamingDocId !== doc.id" class="item-name">{{ doc.user_title || doc.title }}</span>
        <input
          v-else
          :ref="(el) => { if (el) renameInputEl = el }"
          v-model="renameValue"
          class="rename-input"
          @blur="commitDocRename(doc)"
          @keydown.enter="commitDocRename(doc)"
          @keydown.escape="cancelRename"
          @click.stop
        />
      </div>
    </div>

    <!-- 右键菜单 -->
    <ContextMenu
      :visible="ctxVisible"
      :x="ctxX"
      :y="ctxY"
      :targetType="ctxTargetType"
      :documentId="ctxTargetType === 'document' ? ctxTargetId : null"
      :targetId="ctxTargetId"
      :currentFolderId="ctxFolderId"
      :folders="folders"
      @close="ctxVisible = false"
      @rename="handleRename"
      @delete="handleDelete"
      @move-folder="moveToFolder"
    />
  </div>
</template>

<script setup>
import { computed, ref, nextTick } from 'vue'
import { useDocumentStore } from '../../stores/useDocumentStore'
import { useContentStore } from '../../stores/useContentStore'
import { useLearningStore } from '../../stores/useLearningStore'
import ContextMenu from './ContextMenu.vue'

const API_BASE = ''

const docStore = useDocumentStore()
const contentStore = useContentStore()
const learningStore = useLearningStore()

const folders = computed(() => docStore.state.folders)
const documents = computed(() => docStore.state.documents)

const rootDocuments = computed(() =>
  documents.value.filter(d => !d.folder_id).sort((a, b) => (a.position || 0) - (b.position || 0))
)

function folderDocs(folderId) {
  return documents.value.filter(d => d.folder_id === folderId).sort((a, b) => (a.position || 0) - (b.position || 0))
}

function isExpanded(id) { return docStore.state.expandedFolders.includes(id) }
function toggleFolder(id) { docStore.toggleFolderExpand(id) }
function openUpload() { docStore.state.showUploadDialog = true }

async function createFolder() {
  const name = prompt('请输入文件夹名称：')
  if (!name || !name.trim()) return
  try {
    const res = await fetch(`/api/folders`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name.trim() }),
    })
    if (res.ok) {
      await docStore.fetchAll()
      await learningStore.record('folder_created', { context: { name } })
    }
  } catch { /* ignore */ }
}

async function selectDoc(doc) {
  docStore.selectDocument(doc.id)
  await contentStore.loadDocument(doc.id)
  await learningStore.record('document_selected', { document_id: doc.id })
}

// ── 拖拽 ──

const draggedDocId = ref(null)
const dragOverFolderId = ref(null)
const dragInsertPos = ref(null)

function onDragStart(e, doc) {
  draggedDocId.value = doc.id
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData('text/plain', doc.id)
}
function onDragEnd() { draggedDocId.value = null; dragOverFolderId.value = null; dragInsertPos.value = null }
function onFolderDragOver(folderId) { dragOverFolderId.value = folderId }
function onFolderDragLeave() { dragOverFolderId.value = null }

async function onFolderDrop(folderId) {
  const docId = draggedDocId.value
  dragOverFolderId.value = null; draggedDocId.value = null
  if (!docId) return
  const doc = documents.value.find(d => d.id === docId)
  if (!doc || doc.folder_id === folderId) return
  await updateDocFolder(docId, folderId)
}

function onDocDragOver(doc, e) {
  if (doc.id === draggedDocId.value) return
  const rect = e.target.closest('.tree-item')?.getBoundingClientRect()
  if (!rect) return
  dragInsertPos.value = { docId: doc.id, pos: e.clientY < rect.top + rect.height / 2 ? 'before' : 'after' }
}

async function onDocDropOnDoc(targetDoc) {
  const srcId = draggedDocId.value
  if (!srcId || srcId === targetDoc.id) return
  const targetDocs = targetDoc.folder_id ? folderDocs(targetDoc.folder_id) : rootDocuments.value
  const targetIdx = targetDocs.findIndex(d => d.id === targetDoc.id)
  if (targetIdx === -1) return
  let newPos = targetDoc.position || 0
  if (dragInsertPos.value?.pos === 'after') {
    newPos = targetIdx < targetDocs.length - 1
      ? ((targetDocs[targetIdx].position || 0) + (targetDocs[targetIdx + 1].position || 0)) / 2
      : (targetDocs[targetIdx].position || 0) + 1
  }
  if (srcId) {
    const srcDoc = documents.value.find(d => d.id === srcId)
    if (srcDoc && srcDoc.folder_id !== targetDoc.folder_id) {
      await updateDocFolder(srcId, targetDoc.folder_id)
    }
    await updateDocPosition(srcId, Math.round(newPos))
  }
  draggedDocId.value = null; dragInsertPos.value = null
}

function onTreeBodyDrop() {} // 拖到空白区域不做操作

// ── API ──

async function updateDocPosition(docId, position) {
  try { await fetch(`${API_BASE}/api/documents/${docId}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ position }) }); await docStore.fetchAll() } catch { /* ignore */ }
}
async function updateDocFolder(docId, folderId) {
  try { await fetch(`${API_BASE}/api/documents/${docId}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ folder_id: folderId }) }); await docStore.fetchAll() } catch { /* ignore */ }
}

// ── 右键菜单 ──

const ctxVisible = ref(false)
const ctxX = ref(0)
const ctxY = ref(0)
const ctxTargetType = ref('document')
const ctxTargetId = ref(null)
const ctxFolderId = ref(null)

function openDocContextMenu(e, doc) {
  ctxTargetType.value = 'document'
  ctxTargetId.value = doc.id
  ctxFolderId.value = doc.folder_id
  ctxX.value = e.clientX; ctxY.value = e.clientY; ctxVisible.value = true
}

function openFolderContextMenu(e, folder) {
  ctxTargetType.value = 'folder'
  ctxTargetId.value = folder.id
  ctxFolderId.value = null
  ctxX.value = e.clientX; ctxY.value = e.clientY; ctxVisible.value = true
}

function handleRename(id) {
  if (ctxTargetType.value === 'document') startDocRename(id)
  else startFolderRename(id)
}

function handleDelete(id) {
  if (ctxTargetType.value === 'document') deleteDoc(id)
  else deleteFolder(id)
}

// ── 重命名（文档） ──

const renamingDocId = ref(null)
const renamingFolderId = ref(null)
const renameValue = ref('')
let renameInputEl = null

function startDocRename(docId) {
  const doc = documents.value.find(d => d.id === docId)
  if (!doc) return
  renamingDocId.value = docId; renamingFolderId.value = null
  renameValue.value = doc.user_title || doc.title
  nextTick(() => { renameInputEl?.focus(); renameInputEl?.select() })
}

async function commitDocRename(doc) {
  const newTitle = renameValue.value.trim()
  renamingDocId.value = null
  if (!newTitle || newTitle === (doc.user_title || doc.title)) return
  try {
    await fetch(`${API_BASE}/api/documents/${doc.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_title: newTitle }) })
    await docStore.fetchAll()
    await learningStore.record('document_renamed', { document_id: doc.id, context: { old_title: doc.title, new_title: newTitle } })
  } catch { /* ignore */ }
}

// ── 重命名（文件夹） ──

function startFolderRename(folderId) {
  const folder = folders.value.find(f => f.id === folderId)
  if (!folder) return
  renamingFolderId.value = folderId; renamingDocId.value = null
  renameValue.value = folder.name
  nextTick(() => { renameInputEl?.focus(); renameInputEl?.select() })
}

async function commitFolderRename(folder) {
  const newName = renameValue.value.trim()
  renamingFolderId.value = null
  if (!newName || newName === folder.name) return
  try {
    await fetch(`${API_BASE}/api/folders/${folder.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: newName }) })
    await docStore.fetchAll()
    await learningStore.record('folder_renamed', { context: { old_name: folder.name, new_name: newName } })
  } catch { /* ignore */ }
}

function cancelRename() { renamingDocId.value = null; renamingFolderId.value = null }

// ── 删除 ──

async function deleteDoc(docId) {
  const doc = documents.value.find(d => d.id === docId)
  const name = doc?.user_title || doc?.title || '此文档'
  if (!confirm(`确定删除「${name}」吗？此操作不可撤销。`)) return
  try {
    const res = await fetch(`${API_BASE}/api/documents/${docId}`, { method: 'DELETE' })
    if (res.ok) {
      if (docStore.state.selectedDocumentId === docId) contentStore.clear()
      await docStore.fetchAll()
      await learningStore.record('document_deleted', { document_id: docId })
    }
  } catch { /* ignore */ }
}

async function deleteFolder(folderId) {
  const folder = folders.value.find(f => f.id === folderId)
  if (!folder) return
  if (!confirm(`确定删除文件夹「${folder.name}」吗？文件夹内的文档将移出文件夹。`)) return
  try {
    const res = await fetch(`${API_BASE}/api/folders/${folderId}`, { method: 'DELETE' })
    if (res.ok) {
      await docStore.fetchAll()
      await learningStore.record('folder_deleted', { context: { name: folder.name } })
    }
  } catch { /* ignore */ }
}

// ── 移动 ──

async function moveToFolder({ documentId, folderId }) {
  await updateDocFolder(documentId, folderId)
}
</script>

<style scoped>
.document-tree { height: 100%; display: flex; flex-direction: column; }

.tree-header { padding: 14px 16px 10px; border-bottom: 1px solid var(--p-border); flex-shrink: 0; }
.tree-title { font-size: 13px; font-weight: 600; color: var(--p-text); letter-spacing: 0.02em; }
.tree-actions { margin-top: 10px; display: flex; gap: 6px; }

.btn-icon { font-size: 12px; padding: 5px 10px; border: 1px solid var(--p-border); border-radius: var(--r-sm); background: var(--p-surface); color: var(--p-text-secondary); cursor: pointer; font-weight: 500; line-height: 1.4; }
.btn-icon:hover { background: var(--p-surface-subtle); border-color: #cbd5e1; color: var(--p-text); }

.tree-empty { padding: 32px 16px; color: var(--p-text-muted); font-size: 13px; text-align: center; line-height: 1.6; }
.tree-body { flex: 1; overflow-y: auto; padding: 4px 0; }

/* ── 文件夹 ── */
.folder-section { margin-bottom: 2px; }
.folder-header { display: flex; align-items: center; gap: 6px; padding: 7px 14px; cursor: pointer; font-size: 13px; color: var(--p-text-secondary); user-select: none; border-radius: 0; transition: background 0.1s; }
.folder-header:hover { background: var(--p-surface-subtle); }
.folder-header.drag-over { background: var(--p-primary-light); outline: 2px dashed var(--p-primary); outline-offset: -2px; }
.folder-icon { font-size: 13px; flex-shrink: 0; }
.folder-name { flex: 1; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.folder-count { font-size: 11px; color: var(--p-text-muted); background: var(--p-surface-muted); padding: 0 6px; border-radius: 8px; min-width: 18px; text-align: center; line-height: 18px; }
.folder-arrow { font-size: 10px; color: var(--p-text-muted); transition: transform 0.15s; }
.folder-children { }

.root-section-label { font-size: 10px; font-weight: 600; color: var(--p-text-muted); text-transform: uppercase; letter-spacing: 0.04em; padding: 8px 16px 4px; }

/* ── 文档项 ── */
.tree-item { display: flex; align-items: center; gap: 6px; padding: 6px 16px 6px 24px; cursor: pointer; font-size: 13px; color: var(--p-text-secondary); transition: background 0.12s, color 0.12s; border-left: 3px solid transparent; margin: 1px 0; position: relative; }
.folder-children .tree-item { padding-left: 36px; }
.tree-item:hover { background: var(--p-surface-subtle); color: var(--p-text); }
.tree-item.selected { background: var(--p-primary-light); color: var(--p-primary); font-weight: 500; border-left-color: var(--p-primary); }
.tree-item.drag-over-top::before { content: ''; position: absolute; top: 0; left: 20px; right: 10px; height: 2px; background: var(--p-primary); border-radius: 1px; }
.tree-item.drag-over-bottom::after { content: ''; position: absolute; bottom: 0; left: 20px; right: 10px; height: 2px; background: var(--p-primary); border-radius: 1px; }

.drag-handle { font-size: 12px; color: var(--p-text-muted); cursor: grab; flex-shrink: 0; opacity: 0.4; letter-spacing: 2px; }
.tree-item:hover .drag-handle { opacity: 0.8; }
.item-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.rename-input { flex: 1; font-size: 13px; padding: 2px 6px; border: 1px solid var(--p-primary); border-radius: var(--r-sm); outline: none; color: var(--p-text); background: var(--p-surface); font-family: inherit; }
.folder-rename { font-weight: 500; }

.tree-body::-webkit-scrollbar { width: 4px; }
.tree-body::-webkit-scrollbar-thumb { background: transparent; border-radius: 2px; }
.tree-body:hover::-webkit-scrollbar-thumb { background: var(--p-border); }
</style>