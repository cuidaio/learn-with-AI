<template>
  <div class="document-reader" ref="scrollContainer">
    <div v-if="!data" class="reader-empty">无内容</div>
    <div v-else class="reader-content" @contextmenu.prevent="onContextMenu">
      <div class="reader-text" v-html="highlightedHtml" @mouseover="onHighlightMouseOver" @mouseout="onHighlightMouseOut"></div>
    </div>

    <!-- 底部占位（防止最后一行文本截断） -->
    <div class="reader-bottom-placeholder"></div>

    <!-- Context Menu -->
    <Teleport to="body">
      <div
        v-if="contextMenu.visible"
        class="ctx-menu"
        :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px' }"
        @click.stop
      >
        <div class="ctx-item" @click="openManualDialog">
          <span class="ctx-icon">📌</span>
          标记为知识点
        </div>
      </div>

      <!-- Manual Entity Dialog -->
      <div v-if="manualDialog.visible" class="ctx-overlay" @click.self="closeManualDialog">
        <div class="ctx-dialog">
          <div class="ctx-dialog-header">
            <h4>标记为知识点</h4>
            <button class="ctx-close" @click="closeManualDialog">✕</button>
          </div>
          <div class="ctx-dialog-body">
            <div class="ctx-field">
              <label class="ctx-label">选中的文本</label>
              <div class="ctx-selected-text">{{ manualDialog.selectedText }}</div>
            </div>
            <div class="ctx-field">
              <label class="ctx-label">实体名称</label>
              <input v-model="manualDialog.name" class="ctx-input" placeholder="输入知识点名称" />
            </div>
            <div class="ctx-field">
              <label class="ctx-label">实体类型</label>
              <select v-model="manualDialog.entityType" class="ctx-select">
                <option value="concept">概念</option>
                <option value="theorist">理论家</option>
                <option value="theory">理论</option>
                <option value="method">方法</option>
                <option value="fact">事实</option>
              </select>
            </div>
            <div class="ctx-field">
              <label class="ctx-label">描述</label>
              <textarea v-model="manualDialog.description" class="ctx-textarea" placeholder="简短描述该知识点" rows="2"></textarea>
            </div>
          </div>
          <div class="ctx-dialog-footer">
            <button class="ctx-btn ctx-btn-cancel" @click="closeManualDialog">取消</button>
            <button class="ctx-btn ctx-btn-confirm" :disabled="!manualDialog.name.trim()" @click="confirmManualAdd">确认添加</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Entity Highlight Tooltip -->
    <Teleport to="body">
      <div
        v-if="tooltip.visible"
        ref="tooltipRef"
        class="entity-tooltip"
        :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }"
        @mouseenter="tooltipHovered = true"
        @mouseleave="hideTooltip"
      >
        <div class="tooltip-header">
          <span class="tooltip-name">{{ tooltip.name }}</span>
          <span :class="['tooltip-type', 'tt-type-' + tooltip.entityType]">{{ tooltip.typeLabel }}</span>
        </div>
        <div v-if="tooltip.definition" class="tooltip-body">{{ tooltip.definition }}</div>
        <div v-if="tooltip.source" class="tooltip-footer">来源：{{ tooltip.source }}</div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch, onActivated, onDeactivated, onMounted, onUnmounted, nextTick } from 'vue'
import { useContentStore } from '../../stores/useContentStore'
import { useDocumentStore } from '../../stores/useDocumentStore'

const API_BASE = ''
const contentStore = useContentStore()
const docStore = useDocumentStore()

const data = computed(() => contentStore.state.contentData)
const activeTabId = computed(() => contentStore.state.activeTabId)

const scrollContainer = ref(null)

// ── 右键菜单 ──

const contextMenu = reactive({ visible: false, x: 0, y: 0, selectedText: '' })

function onContextMenu(e) {
  const selection = window.getSelection()
  const txt = (selection?.toString() || '').trim()
  if (!txt) {
    contextMenu.visible = false
    return
  }
  contextMenu.selectedText = txt
  contextMenu.x = e.clientX
  contextMenu.y = e.clientY
  contextMenu.visible = true
}

// ── 手动添加知识点对话框 ──

const manualDialog = reactive({
  visible: false,
  selectedText: '',
  name: '',
  entityType: 'concept',
  description: '',
})

function openManualDialog() {
  manualDialog.selectedText = contextMenu.selectedText
  manualDialog.name = contextMenu.selectedText.slice(0, 60)
  manualDialog.description = ''
  manualDialog.entityType = 'concept'
  manualDialog.visible = true
  contextMenu.visible = false
}

function closeManualDialog() {
  manualDialog.visible = false
}

async function confirmManualAdd() {
  const docId = docStore.state.selectedDocumentId
  if (!docId || !manualDialog.name.trim()) return

  try {
    const res = await fetch(`${API_BASE}/api/entities/manual`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        document_id: docId,
        name: manualDialog.name.trim(),
        entity_type: manualDialog.entityType,
        description: manualDialog.description.trim(),
        introduction_context: manualDialog.selectedText,
      }),
    })
    if (res.ok) {
      closeManualDialog()
      docStore.refreshHighlights()
    }
  } catch {
    // ignore
  }
}

// 点击其他地方关闭菜单
document.addEventListener('click', () => {
  contextMenu.visible = false
})

// ── 高亮渲染 ──

const highlightedHtml = computed(() => {
  if (!data.value) return ''
  const text = data.value.content || ''
  const highlights = data.value.highlights || []

  if (!highlights.length) {
    return wrapBlocks(convertBlocks(mdInline(text)))
  }

  const sorted = [...highlights].sort((a, b) => a.start - b.start)
  const fragments = []
  let cursor = 0

  for (const h of sorted) {
    if (h.start > cursor) {
      fragments.push(mdInline(text.slice(cursor, h.start)))
    }
    const name = esc(text.slice(h.start, h.end))
    const nameAttr = escAttr(text.slice(h.start, h.end))
    const type = escAttr(h.entity_type || 'concept')
    fragments.push(`<mark class="entity-highlight" data-name="${nameAttr}" data-type="${type}" data-start="${h.start}" data-end="${h.end}">${name}</mark>`)
    cursor = h.end
  }
  if (cursor < text.length) {
    fragments.push(mdInline(text.slice(cursor)))
  }

  let result = fragments.join('')
  result = convertBlocks(result)
  return wrapBlocks(result)
})

function wrapBlocks(html) {
  if (!html) return ''
  return '<p>' + html + '</p>'
    .replace(/<p><(h[234]|ul|ol|li|hr|blockquote|figure|mark)/g, '<$1')
    .replace(/(<\/(h[234]|ul|ol|li|hr|blockquote|figure)>)<\/p>/g, '</$1>')
}

function esc(s) {
  const d = document.createElement('div')
  d.textContent = s
  return d.innerHTML
}

function escAttr(s) {
  if (!s) return ''
  return s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function mdInline(text) {
  if (!text) return ''
  let h = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  h = h.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_m, alt, url) => {
    if (url.startsWith('images/') || url.startsWith('http')) {
      return `<figure class="md-img"><div class="md-img-placeholder">🖼 ${esc(alt || '图片')}</div><figcaption>${esc(alt || '')}</figcaption></figure>`
    }
    return ''
  })
  h = h.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
  h = h.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  h = h.replace(/__([^_]+)__/g, '<strong>$1</strong>')
  h = h.replace(/\*(?!\*)([^*]+?)(?<!\*)\*/g, '<em>$1</em>')
  h = h.replace(/_([^_]+)_/g, '<em>$1</em>')
  return h
}

function convertBlocks(html) {
  if (!html) return ''
  let h = html
  h = h.replace(/^### (.+)$/gm, '<h4>$1</h4>')
  h = h.replace(/^## (.+)$/gm, '<h3>$1</h3>')
  h = h.replace(/^# (.+)$/gm, '<h2>$1</h2>')
  h = h.replace(/^---+\s*$/gm, '<hr>')
  h = h.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
  h = h.replace(/^[-*] (.+)$/gm, '<li>$1</li>')
  h = h.replace(/((?:<li>[\s\S]*?<\/li>\n?)+)/g, '<ul>$1</ul>')
  h = h.replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
  h = h.replace(/((?:<li>[\s\S]*?<\/li>\n?)+?)(?=\n\n|$)/g, '<ol>$1</ol>')
  h = h.replace(/\n/g, '<br>')
  h = h.replace(/<(h[234]|ul|ol|li|hr|blockquote|figure)>\s*<br>/g, '<$1>')
  h = h.replace(/<br>\s*<\/(h[234]|ul|ol|li|hr|blockquote|figure)>/g, '</$1>')
  h = h.replace(/(<\/(h[234]|ul|ol|li|hr|blockquote|figure)>)\s*<br>/g, '$1')
  return h
}

// ── 高亮悬浮 Tooltip（分级解释） ──

const tooltip = reactive({
  visible: false,
  x: 0,
  y: 0,
  name: '',
  entityType: '',
  typeLabel: '',
  definition: '',
  source: '',
})
const tooltipHovered = ref(false)
const tooltipRef = ref(null)
let tooltipTimer = null

const typeLabels = { concept: '概念', theorist: '理论家', theory: '理论', method: '方法', fact: '事实' }

/** 定义信号词，本地上下文中出现这些词说明实体已被定义 */
const DEF_SIGNALS = /是|指|即|称为|定义为|意思是|也就是|表示|是指|就是指/

function onHighlightMouseOver(e) {
  const mark = e.target.closest('.entity-highlight')
  if (!mark) {
    if (tooltipTimer) clearTimeout(tooltipTimer)
    hideTooltip()
    return
  }

  const name = mark.dataset.name
  const start = parseInt(mark.dataset.start, 10)
  const end = parseInt(mark.dataset.end, 10)
  const type = mark.dataset.type || 'concept'

  if (tooltipTimer) clearTimeout(tooltipTimer)
  tooltipTimer = setTimeout(() => {
    showEntityTooltip(name, type, start, end, e)
  }, 200)
}

function onHighlightMouseOut(e) {
  const mark = e.target.closest('.entity-highlight')
  if (mark) return // still inside a mark
  if (tooltipTimer) clearTimeout(tooltipTimer)
  setTimeout(() => {
    if (!tooltipHovered.value) hideTooltip()
  }, 150)
}

function hideTooltip() {
  tooltipHovered.value = false
  tooltip.visible = false
  tooltipRef.value = null
}

function getHighlightContext(name, start, end) {
  const text = data.value?.content || ''
  const ctxStart = Math.max(0, start - 200)
  const ctxEnd = Math.min(text.length, end + 200)
  return text.slice(ctxStart, ctxEnd)
}

function hasLocalDefinition(name, context) {
  // 查找名称在上下文中的位置
  const nameIdx = context.lastIndexOf(name)
  if (nameIdx === -1) return false
  // 检查名称后面是否有定义信号
  const afterName = context.slice(nameIdx + name.length, nameIdx + name.length + 60)
  return DEF_SIGNALS.test(afterName)
}

async function showEntityTooltip(name, type, start, end, e) {
  // 1. 检查当前上下文是否已定义
  const text = data.value?.content || ''
  const context = getHighlightContext(name, start, end)
  if (hasLocalDefinition(name, context)) {
    hideTooltip()
    return
  }

  // 2. 查找跨文档定义
  const docId = docStore.state.selectedDocumentId
  if (!docId) {
    hideTooltip()
    return
  }

  try {
    const url = `${API_BASE}/api/entities/lookup?name=${encodeURIComponent(name)}&document_id=${docId}`
    const res = await fetch(url)
    if (!res.ok) {
      hideTooltip()
      return
    }
    const entity = await res.json()

    // 3. 仅 intro_context 不为空才显示
    if (!entity.introduction_context) {
      hideTooltip()
      return
    }

    // 4. 显示 tooltip
    const rect = e.target.getBoundingClientRect()
    tooltip.name = entity.name
    tooltip.entityType = entity.entity_type || 'concept'
    tooltip.typeLabel = typeLabels[entity.entity_type] || entity.entity_type || '概念'
    tooltip.definition = entity.introduction_context
    tooltip.source = entity.source_document_title || ''
    tooltip.x = rect.left
    tooltip.y = rect.bottom + 6
    tooltip.visible = true

    // 确保 tooltip 不超出屏幕
    await nextTick()
    if (tooltipRef.value) {
      const tr = tooltipRef.value.getBoundingClientRect()
      if (tr.right > window.innerWidth) {
        tooltip.x = window.innerWidth - tr.width - 12
      }
      if (tr.bottom > window.innerHeight) {
        tooltip.y = rect.top - tr.height - 6
      }
    }
  } catch {
    hideTooltip()
  }
}

// ── 滚动位置保存/恢复（按 tabId 独立记录） ──

let scrollSaveTimer = null
function onScroll() {
  if (!scrollContainer.value) return
  if (scrollSaveTimer) clearTimeout(scrollSaveTimer)
  scrollSaveTimer = setTimeout(() => {
    saveCurrentScroll()
  }, 300)
}

function saveCurrentScroll() {
  const tabId = activeTabId.value
  if (tabId && scrollContainer.value) {
    contentStore.saveScrollPosition(tabId, scrollContainer.value.scrollTop)
  }
}

function restoreScroll() {
  const tabId = activeTabId.value
  if (tabId && scrollContainer.value) {
    const saved = contentStore.getScrollPosition(tabId)
    if (saved !== null) {
      scrollContainer.value.scrollTop = saved
    }
  }
}

// ── 高亮刷新监听 ──

watch(() => docStore.state.highlightRefreshTrigger, () => {
  contentStore.refreshCurrentDocument()
})

// ── 生命周期 ──

onMounted(() => {
  // 首次添加滚动监听（keep-alive 下只执行一次）
  if (scrollContainer.value) {
    scrollContainer.value.addEventListener('scroll', onScroll, { passive: true })
  }
})

onUnmounted(() => {
  if (scrollContainer.value) {
    scrollContainer.value.removeEventListener('scroll', onScroll)
  }
  if (tooltipTimer) clearTimeout(tooltipTimer)
  if (scrollSaveTimer) clearTimeout(scrollSaveTimer)
})

// keep-alive 激活：从其他 tab 切回时恢复
onActivated(() => {
  nextTick(() => restoreScroll())
})

// keep-alive 停用：离开此 tab 时保存
onDeactivated(() => {
  saveCurrentScroll()
})

// tabId 不变但 contentData 变化（同类型 tab 间切换，如 doc A ↔ doc B）
watch(() => contentStore.state.contentData, () => {
  nextTick(() => restoreScroll())
})
</script>

<style scoped>
.document-reader {
  height: 100%;
  padding: 28px 32px 0;
  overflow-y: auto;
}

.reader-empty {
  color: var(--p-text-muted);
  text-align: center;
  padding: 60px 40px;
}

.reader-content {
  font-size: 15px;
  line-height: 1.9;
  color: var(--p-text);
  max-width: 75ch;
}

.reader-bottom-placeholder {
  height: 60px;
  flex-shrink: 0;
}

.reader-text :deep(h2),
.reader-text :deep(h3),
.reader-text :deep(h4) {
  margin-top: 1.5em;
  margin-bottom: 0.5em;
  font-weight: 600;
  line-height: 1.3;
  color: var(--p-text);
}

.reader-text :deep(h2) { font-size: 1.25em; border-bottom: 1px solid var(--p-border); padding-bottom: 0.3em; }
.reader-text :deep(h3) { font-size: 1.1em; }
.reader-text :deep(h4) { font-size: 1em; }

.reader-text :deep(p) { margin-bottom: 0.8em; }

.reader-text :deep(strong) { font-weight: 600; }
.reader-text :deep(em) { font-style: italic; }

.reader-text :deep(ul), .reader-text :deep(ol) {
  margin: 0.5em 0;
  padding-left: 1.5em;
}

.reader-text :deep(li) {
  margin-bottom: 0.3em;
}

.reader-text :deep(blockquote) {
  margin: 0.8em 0;
  padding: 8px 16px;
  background: var(--p-surface-subtle);
  border-radius: var(--r-sm);
  color: var(--p-text-secondary);
}

.reader-text :deep(hr) {
  margin: 1.2em 0;
  border: none;
  border-top: 1px solid var(--p-border);
}

.reader-text :deep(a) {
  color: var(--p-primary);
  text-decoration: none;
}

.reader-text :deep(a:hover) {
  text-decoration: underline;
}

.reader-text :deep(.entity-highlight) {
  background: var(--p-accent-light);
  padding: 1px 4px;
  border-radius: 3px;
  cursor: help;
  border-bottom: 1px dashed var(--p-accent);
  transition: background 0.12s ease;
}

.reader-text :deep(.entity-highlight:hover) {
  background: #fde68a;
}

.reader-text :deep(.md-img) {
  margin: 1em 0;
  text-align: center;
}

.reader-text :deep(.md-img-placeholder) {
  display: inline-block;
  padding: 24px 40px;
  background: var(--p-surface-muted);
  border: 1px dashed var(--p-border);
  border-radius: var(--r-md);
  color: var(--p-text-muted);
  font-size: 14px;
}

.reader-text :deep(figcaption) {
  font-size: 12px;
  color: var(--p-text-muted);
  margin-top: 4px;
}

.document-reader::-webkit-scrollbar {
  width: 4px;
}
.document-reader::-webkit-scrollbar-thumb {
  background: transparent;
  border-radius: 2px;
}
.document-reader:hover::-webkit-scrollbar-thumb {
  background: var(--p-border);
}

/* ── 右键菜单 ── */
.ctx-menu {
  position: fixed;
  z-index: 9999;
  min-width: 160px;
  background: var(--p-surface);
  border: 1px solid var(--p-border);
  border-radius: var(--r-md);
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
  overflow: hidden;
}

.ctx-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  font-size: 13px;
  color: var(--p-text);
  cursor: pointer;
  transition: background 0.08s;
}

.ctx-item:hover {
  background: var(--p-surface-muted);
}

.ctx-icon {
  font-size: 14px;
}

/* ── 对话框遮罩 ── */
.ctx-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9998;
}

.ctx-dialog {
  background: var(--p-surface);
  border-radius: var(--r-xl);
  width: 440px;
  max-width: 90vw;
  box-shadow: 0 8px 32px rgba(0,0,0,0.18);
  animation: ctxIn 0.15s ease-out;
}

@keyframes ctxIn {
  from { opacity: 0; transform: translateY(6px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.ctx-dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--p-border);
}

.ctx-dialog-header h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--p-text);
}

.ctx-close {
  background: none;
  border: none;
  font-size: 15px;
  color: var(--p-text-muted);
  cursor: pointer;
  width: 26px;
  height: 26px;
  border-radius: var(--r-sm);
  display: flex;
  align-items: center;
  justify-content: center;
}

.ctx-close:hover {
  background: var(--p-surface-muted);
}

.ctx-dialog-body {
  padding: 16px 20px;
}

.ctx-field {
  margin-bottom: 12px;
}

.ctx-field:last-child {
  margin-bottom: 0;
}

.ctx-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--p-text);
  margin-bottom: 5px;
}

.ctx-selected-text {
  font-size: 13px;
  color: var(--p-text-secondary);
  background: var(--p-surface-subtle);
  padding: 8px 10px;
  border-radius: var(--r-sm);
  line-height: 1.5;
  max-height: 60px;
  overflow-y: auto;
}

.ctx-input,
.ctx-select,
.ctx-textarea {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--p-border);
  border-radius: var(--r-sm);
  font-size: 13px;
  color: var(--p-text);
  background: var(--p-surface);
  outline: none;
  box-sizing: border-box;
  font-family: inherit;
}

.ctx-input:focus,
.ctx-select:focus,
.ctx-textarea:focus {
  border-color: var(--p-primary);
  box-shadow: 0 0 0 3px rgba(79, 106, 240, 0.12);
}

.ctx-textarea {
  resize: vertical;
  min-height: 50px;
}

.ctx-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid var(--p-border);
}

.ctx-btn {
  padding: 7px 18px;
  border-radius: var(--r-md);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid transparent;
}

.ctx-btn-cancel {
  background: var(--p-surface);
  border-color: var(--p-border);
  color: var(--p-text-secondary);
}

.ctx-btn-cancel:hover {
  background: var(--p-surface-muted);
}

.ctx-btn-confirm {
  background: var(--p-primary);
  color: #fff;
}

.ctx-btn-confirm:hover {
  background: var(--p-primary-hover);
}

.ctx-btn-confirm:disabled {
  background: #A5B4FC;
  cursor: not-allowed;
}

/* ── Entity Tooltip ── */
.entity-tooltip {
  position: fixed;
  z-index: 10001;
  background: #1e293b;
  color: #f1f5f9;
  border-radius: 8px;
  padding: 10px 14px;
  max-width: 360px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.3);
  font-size: 13px;
  line-height: 1.5;
  pointer-events: auto;
}

.tooltip-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.tooltip-name {
  font-weight: 600;
  font-size: 14px;
  color: #fff;
}

.tooltip-type {
  font-size: 11px;
  font-weight: 500;
  padding: 1px 7px;
  border-radius: 10px;
}

.tt-type-concept { background: #3730a3; color: #c7d2fe; }
.tt-type-theorist { background: #92400e; color: #fde68a; }
.tt-type-theory { background: #166534; color: #bbf7d0; }
.tt-type-method { background: #9d174d; color: #fbcfe8; }
.tt-type-fact { background: #5b21b6; color: #ddd6fe; }

.tooltip-body {
  font-size: 13px;
  color: #e2e8f0;
  margin-bottom: 4px;
  line-height: 1.6;
}

.tooltip-footer {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 4px;
  padding-top: 4px;
  border-top: 1px solid rgba(255,255,255,0.1);
}
</style>
