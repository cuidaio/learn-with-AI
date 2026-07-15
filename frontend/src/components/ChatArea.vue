<template>
  <div class="chat-panel">
    <!-- Header -->
    <div class="chat-header">
      <h2 class="chat-title">
        <template v-if="selectedCount === 0">
          选择一个文档后开始提问
        </template>
        <template v-else-if="selectedCount === 1">
          已选：{{ selectedDocTitle }}
        </template>
        <template v-else>
          已选：{{ selectedDocTitle }} + {{ selectedCount - 1 }} 个其他文档
        </template>
      </h2>
    </div>

    <!-- Messages -->
    <div class="chat-messages" ref="messagesRef">
      <div v-if="messages.length === 0" class="chat-empty">
        选择一个或多个文档，输入问题开始学习
      </div>

      <div
        v-for="(msg, idx) in messages"
        :key="idx"
        class="message-row"
        :class="msg.role === 'user' ? 'row-user' : 'row-assistant'"
      >
        <div class="message-bubble" :class="msg.role">
          <div class="message-content" v-html="renderContent(msg)"></div>

          <!-- Sources (assistant only) -->
          <div v-if="msg.role === 'assistant' && msg.sources && msg.sources.length > 0" class="sources-section">
            <div class="sources-toggle" @click="toggleSources(idx)">
              {{ expandedSources[idx] ? '▼' : '▶' }} 📖 引用来源（{{ msg.sources.length }}）
            </div>
            <div v-if="expandedSources[idx]" class="sources-list">
              <div
                v-for="(source, si) in msg.sources"
                :key="si"
                class="source-item"
                :class="{ cited: source.cited_in_answer }"
              >
                <span class="source-num">{{ si + 1 }}</span>
                <div class="source-detail">
                  <div class="source-title" v-if="source.section_title">{{ source.section_title }}</div>
                  <div class="source-meta">
                    <span class="source-doc" v-if="source.document_title">{{ source.document_title }}</span>
                    <span class="source-score">相关度 {{ (source.relevance_score * 100).toFixed(0) }}%</span>
                    <span v-if="source.cited_in_answer" class="source-cited">已引用</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Thinking indicator -->
      <div v-if="isThinking" class="message-row row-assistant">
        <div class="message-bubble assistant thinking">
          <div class="thinking-dots">
            <span>正在思考</span>
            <span class="dot">.</span>
            <span class="dot">.</span>
            <span class="dot">.</span>
          </div>
        </div>
      </div>

      <!-- Error message -->
      <div v-if="errorMessage" class="message-row row-assistant">
        <div class="message-bubble assistant error">
          {{ errorMessage }}
        </div>
      </div>
    </div>

    <!-- Input -->
    <div class="chat-input-area">
      <div class="input-wrapper">
        <textarea
          v-model="inputText"
          :placeholder="selectedCount === 0 ? '请先选择文档' : '输入你关心的问题...'"
          :disabled="isThinking || selectedCount === 0"
          class="chat-input"
          rows="2"
          @keydown="onKeydown"
        ></textarea>
        <button
          class="btn btn-send"
          :disabled="isThinking || !inputText.trim() || selectedCount === 0"
          @click="onSend"
        >
          {{ isThinking ? '思考中...' : '发送' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick } from 'vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  isThinking: { type: Boolean, default: false },
  selectedCount: { type: Number, default: 0 },
  selectedDocTitle: { type: String, default: '' },
  errorMessage: { type: String, default: '' },
})

const emit = defineEmits(['send'])

const inputText = ref('')
const messagesRef = ref(null)
const expandedSources = reactive({})

function onSend() {
  const q = inputText.value.trim()
  if (!q || props.isThinking || props.selectedCount === 0) return
  inputText.value = ''
  emit('send', q)
  scrollToBottom()
}

function onKeydown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    onSend()
  }
}

function toggleSources(idx) {
  expandedSources[idx] = !expandedSources[idx]
}

function renderContent(msg) {
  let text = msg.content || ''
  // HTML-escape first (safe for v-html)
  text = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  if (msg.role === 'assistant') {
    // Highlight 【来源编号】 as styled tags
    text = text.replace(/【(\d+)】/g, '<span class="citation-tag">【$1】</span>')
  }
  return text
}

async function scrollToBottom() {
  await nextTick()
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}

// Expose for parent to call after new message
defineExpose({ scrollToBottom })
</script>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f9fafb;
}

.chat-header {
  padding: 20px 24px 12px;
  border-bottom: 1px solid #e5e7eb;
  background: #fff;
}

.chat-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: #374151;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.chat-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9ca3af;
  font-size: 15px;
}

.message-row {
  display: flex;
}
.row-user {
  justify-content: flex-end;
}
.row-assistant {
  justify-content: flex-start;
}

.message-bubble {
  max-width: 75%;
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.6;
  font-size: 14px;
  white-space: pre-wrap;
  word-wrap: break-word;
}
.message-bubble.user {
  background: #e5e7eb;
  color: #1f2937;
  border-bottom-right-radius: 4px;
}
.message-bubble.assistant {
  background: #fff;
  color: #1f2937;
  border: 1px solid #e5e7eb;
  border-bottom-left-radius: 4px;
}
.message-bubble.thinking {
  background: #f3f4f6;
  color: #6b7280;
}
.message-bubble.error {
  background: #fef2f2;
  color: #b91c1c;
  border-color: #fecaca;
}

.thinking-dots {
  display: flex;
  align-items: center;
  gap: 2px;
  font-size: 14px;
}
.dot {
  animation: blink 1.4s infinite;
  font-weight: bold;
  font-size: 18px;
}
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }
.dot:nth-child(4) { animation-delay: 0.6s; }

@keyframes blink {
  0%, 20% { opacity: 0; }
  50% { opacity: 1; }
  100% { opacity: 0; }
}

/* Sources */
.sources-section {
  margin-top: 12px;
  border-top: 1px solid #f0f0f0;
  padding-top: 8px;
}

.sources-toggle {
  font-size: 12px;
  color: #6b7280;
  cursor: pointer;
  user-select: none;
}
.sources-toggle:hover {
  color: #374151;
}

.sources-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.source-item {
  display: flex;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  background: #f9fafb;
  font-size: 12px;
}
.source-item.cited {
  background: #f0fdf4;
}

.source-num {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}
.source-item.cited .source-num {
  background: #22c55e;
  color: #fff;
}

.source-detail {
  flex: 1;
  min-width: 0;
}

.source-title {
  font-weight: 500;
  color: #374151;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 2px;
  color: #9ca3af;
  font-size: 11px;
}

.source-cited {
  color: #22c55e;
  font-weight: 500;
}

/* Input */
.chat-input-area {
  padding: 16px 24px;
  border-top: 1px solid #e5e7eb;
  background: #fff;
}

.input-wrapper {
  display: flex;
  gap: 10px;
  align-items: flex-end;
}

.chat-input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  resize: none;
  font-size: 14px;
  font-family: inherit;
  line-height: 1.5;
  outline: none;
  transition: border-color 0.15s;
}
.chat-input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}
.chat-input:disabled {
  background: #f3f4f6;
  cursor: not-allowed;
}

.btn-send {
  padding: 10px 24px;
  border: none;
  border-radius: 10px;
  background: #3b82f6;
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
  white-space: nowrap;
}
.btn-send:hover:not(:disabled) {
  background: #2563eb;
}
.btn-send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Citation tag styling */
:deep(.citation-tag) {
  display: inline-block;
  background: #dbeafe;
  color: #1d4ed8;
  padding: 0 6px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  cursor: default;
}
</style>
