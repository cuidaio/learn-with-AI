<template>
  <div class="chat-view">
    <div class="chat-messages" ref="msgRef">
      <div v-if="!messages.length" class="chat-empty">
        {{ selectedDocId ? '输入问题开始对话' : '请先在左侧选中文档' }}
      </div>
      <div
        v-for="(msg, i) in messages"
        :key="i"
        :class="['msg', msg.role === 'user' ? 'msg-user' : 'msg-ai']"
      >
        <div class="msg-label">{{ msg.role === 'user' ? '你' : 'AI' }}</div>
        <div class="msg-content">{{ msg.content }}</div>
        <div v-if="msg.sources && msg.sources.length" class="msg-sources">
          <span v-for="(s, si) in msg.sources" :key="si" class="source-tag">{{ s.document_title || s.section_title || '来源' }}</span>
        </div>
      </div>
      <div v-if="isThinking" class="msg-thinking">思考中...</div>
    </div>
    <div class="chat-input-row">
      <input
        v-model="inputText"
        class="chat-input"
        placeholder="输入问题..."
        @keyup.enter="send"
        :disabled="isThinking"
      />
      <button class="chat-send-btn" @click="send" :disabled="isThinking || !inputText.trim()">发送</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useDocumentStore } from '../../stores/useDocumentStore'
import { useContentStore } from '../../stores/useContentStore'

const API_BASE = ''

const docStore = useDocumentStore()
const contentStore = useContentStore()

const messages = ref([])
const inputText = ref('')
const isThinking = ref(false)
const msgRef = ref(null)

const selectedDocId = computed(() => docStore.state.selectedDocumentId)

async function send() {
  const q = inputText.value.trim()
  if (!q || !selectedDocId.value) return
  inputText.value = ''
  messages.value.push({ role: 'user', content: q })
  isThinking.value = true

  try {
    const res = await fetch(`${API_BASE}/api/ask/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        document_ids: [selectedDocId.value],
        question: q,
        top_k: 5,
      }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      messages.value.push({ role: 'assistant', content: '错误：' + (err.detail || '请求失败') })
      return
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let aiMsg = null

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const data = JSON.parse(line.slice(6))
          if (data.type === 'start') {
            aiMsg = { role: 'assistant', content: '', sources: [] }
            messages.value.push(aiMsg)
          } else if (data.type === 'token' && aiMsg) {
            aiMsg.content += data.content
            messages.value = [...messages.value]
          } else if (data.type === 'done' && aiMsg) {
            aiMsg.sources = data.sources || []
            messages.value = [...messages.value]
          } else if (data.type === 'error') {
            messages.value.push({ role: 'assistant', content: '错误：' + (data.message || '生成失败') })
          }
        } catch {
          // skip
        }
      }
    }
  } catch {
    messages.value.push({ role: 'assistant', content: '网络连接失败' })
  } finally {
    isThinking.value = false
    setTimeout(() => {
      if (msgRef.value) msgRef.value.scrollTop = msgRef.value.scrollHeight
    }, 50)
  }
}
</script>

<style scoped>
.chat-view {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

.chat-empty {
  text-align: center;
  color: var(--p-text-muted);
  font-size: 13px;
  padding: 48px 24px;
  line-height: 1.6;
}

.msg {
  margin-bottom: 16px;
  max-width: 85%;
}

.msg-user {
  margin-left: auto;
}

.msg-ai {
  margin-right: auto;
}

.msg-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--p-text-muted);
  margin-bottom: 4px;
  padding: 0 4px;
}

.msg-content {
  font-size: 13px;
  line-height: 1.6;
  padding: 10px 14px;
  border-radius: var(--r-lg);
  white-space: pre-wrap;
}

.msg-user .msg-content {
  background: var(--p-primary);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.msg-ai .msg-content {
  background: var(--p-surface-subtle);
  color: var(--p-text);
  border-bottom-left-radius: 4px;
}

.msg-thinking {
  color: var(--p-text-muted);
  font-size: 12px;
  padding: 8px 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.msg-thinking::after {
  content: '';
  width: 12px;
  height: 12px;
  border: 2px solid var(--p-border);
  border-top-color: var(--p-primary);
  border-radius: 50%;
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.3; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1); }
}

.msg-sources {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.source-tag {
  font-size: 10px;
  padding: 2px 8px;
  background: var(--p-primary-light);
  color: var(--p-primary);
  border-radius: 10px;
  font-weight: 500;
}

.chat-input-row {
  display: flex;
  gap: 8px;
  padding: 12px 16px 14px;
  border-top: 1px solid var(--p-border);
  background: var(--p-surface);
}

.chat-input {
  flex: 1;
  padding: 9px 14px;
  border: 1px solid var(--p-border);
  border-radius: var(--r-md);
  font-size: 13px;
  color: var(--p-text);
  background: var(--p-surface-subtle);
  outline: none;
}

.chat-input:focus {
  border-color: var(--p-primary);
  box-shadow: 0 0 0 3px rgba(79, 106, 240, 0.12);
  background: var(--p-surface);
}

.chat-input::placeholder {
  color: var(--p-text-muted);
}

.chat-send-btn {
  padding: 8px 18px;
  background: var(--p-primary);
  color: #fff;
  border: none;
  border-radius: var(--r-md);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
}

.chat-send-btn:hover {
  background: var(--p-primary-hover);
}

.chat-send-btn:disabled {
  background: #A5B4FC;
  cursor: not-allowed;
}

.chat-messages::-webkit-scrollbar {
  width: 4px;
}
.chat-messages::-webkit-scrollbar-thumb {
  background: transparent;
  border-radius: 2px;
}
.chat-messages:hover::-webkit-scrollbar-thumb {
  background: var(--p-border);
}
</style>
