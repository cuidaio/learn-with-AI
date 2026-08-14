<template>
  <div class="question-viewer">
    <div v-if="!questions.length" class="qv-empty">暂无题目</div>
    <div v-else class="qv-list">
      <div v-for="(q, i) in questions" :key="q.id || i" class="qv-card">
        <!-- 元信息 -->
        <div class="qv-meta">
          <span class="qv-type" :class="'type-' + q.question_type">{{ typeLabel(q.question_type) }}</span>
          <span v-if="q.bloom_level" class="qv-bloom">{{ bloomLabel(q.bloom_level) }}</span>
        </div>

        <!-- 题干 -->
        <div class="qv-stem">{{ q.stem }}</div>

        <!-- ── 单选题 ── -->
        <div v-if="q.question_type === 'choice'" class="qv-options">
          <div
            v-for="(optText, optKey) in q.options"
            :key="optKey"
            :class="['qv-option', optClass(q, optKey)]"
            @click="selectChoice(q, optKey)"
          >
            <span :class="['qv-radio', { checked: answers[q.id] === optKey }]">
              <span v-if="answers[q.id] === optKey" class="qv-dot"></span>
            </span>
            <span class="qv-opt-key">{{ optKey }}.</span>
            <span class="qv-opt-text">{{ optText }}</span>
          </div>
        </div>

        <!-- ── 多选题 ── -->
        <div v-if="q.question_type === 'multi_choice'" class="qv-options">
          <div
            v-for="(optText, optKey) in q.options"
            :key="optKey"
            :class="['qv-option', optClass(q, optKey)]"
            @click="toggleMultiChoice(q, optKey)"
          >
            <span :class="['qv-checkbox', { checked: isMultiSelected(q, optKey) }]">
              <span v-if="isMultiSelected(q, optKey)" class="qv-check"></span>
            </span>
            <span class="qv-opt-key">{{ optKey }}.</span>
            <span class="qv-opt-text">{{ optText }}</span>
          </div>
        </div>

        <!-- ── 填空题 ── -->
        <div v-if="q.question_type === 'fill'" class="qv-fill">
          <input
            v-model="fillAnswers[q.id]"
            type="text"
            class="qv-input"
            placeholder="请输入答案"
            :disabled="submitted[q.id]"
          />
        </div>

        <!-- ── 简答/论述题 ── -->
        <div v-if="q.question_type === 'short_answer' || q.question_type === 'essay'" class="qv-textarea-wrap">
          <textarea
            v-model="textAnswers[q.id]"
            class="qv-textarea"
            :placeholder="q.question_type === 'essay' ? '请输入论述内容...' : '请输入答案...'"
            :rows="q.question_type === 'essay' ? 5 : 3"
            :disabled="submitted[q.id]"
          ></textarea>
        </div>

        <!-- ── 提交按钮（单选题选择即提交，不显示按钮） ── -->
        <div v-if="!submitted[q.id] && q.question_type !== 'choice'" class="qv-actions">
          <button class="qv-submit" @click="submitAnswer(q)">提交答案</button>
        </div>

        <!-- ── 反馈 ── -->
        <div v-if="submitted[q.id]" class="qv-feedback" :class="feedbackCorrect[q.id] ? 'fb-correct' : 'fb-wrong'">
          <div class="fb-header">
            <span class="fb-icon">{{ feedbackCorrect[q.id] ? '✅' : '❌' }}</span>
            <span class="fb-text">{{ feedbackCorrect[q.id] ? '正确！' : '错误' }}</span>
          </div>
          <div v-if="!feedbackCorrect[q.id]" class="fb-correct-answer">
            正确答案：<strong>{{ correctAnswerLabel(q) }}</strong>
          </div>
          <div v-if="q.explanation" class="fb-explanation">{{ q.explanation }}</div>
          <div v-if="!feedbackCorrect[q.id]" class="fb-retry">
            <button class="qv-retry" @click="resetQuestion(q)">再做一次</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useContentStore } from '../../stores/useContentStore'
import { useLearningStore } from '../../stores/useLearningStore'

const contentStore = useContentStore()
const learningStore = useLearningStore()

const questions = computed(() => {
  const data = contentStore.state.contentData
  if (!data) return []
  if (Array.isArray(data)) return data
  if (data.questions) return data.questions
  if (data.data && data.data.questions) return data.data.questions
  return []
})

const activeTabId = computed(() => contentStore.state.activeTabId)

// ── 作答状态（持久化到 tabMeta） ──
const answers = ref({})           // { qid: 'A' } for choice
const multiAnswers = ref({})      // { qid: ['A','B'] } for multi_choice
const fillAnswers = ref({})       // { qid: 'input' }
const textAnswers = ref({})       // { qid: 'long text' }
const submitted = ref({})         // { qid: true }
const feedbackCorrect = ref({})   // { qid: true/false }
const startTimes = ref({})        // { qid: timestamp }

const QS_KEY = 'questionState'

function saveState() {
  if (!activeTabId.value) return
  contentStore.setTabMeta(activeTabId.value, QS_KEY, {
    answers: answers.value,
    multiAnswers: multiAnswers.value,
    fillAnswers: fillAnswers.value,
    textAnswers: textAnswers.value,
    submitted: submitted.value,
    feedbackCorrect: feedbackCorrect.value,
    startTimes: startTimes.value,
  })
}

function restoreState() {
  if (!activeTabId.value) return
  const saved = contentStore.getTabMeta(activeTabId.value, QS_KEY)
  if (saved) {
    answers.value = saved.answers || {}
    multiAnswers.value = saved.multiAnswers || {}
    fillAnswers.value = saved.fillAnswers || {}
    textAnswers.value = saved.textAnswers || {}
    submitted.value = saved.submitted || {}
    feedbackCorrect.value = saved.feedbackCorrect || {}
    startTimes.value = saved.startTimes || {}
  }
}

// 深度 watch 自动持久化
watch([answers, multiAnswers, fillAnswers, textAnswers, submitted, feedbackCorrect], saveState, { deep: true })

onMounted(() => {
  restoreState()
  // 为新题目设置开始时间
  for (const q of questions.value) {
    if (q.id && !startTimes.value[q.id]) {
      startTimes.value[q.id] = Date.now()
    }
  }
})

function selectChoice(q, key) {
  if (submitted.value[q.id]) return
  // 点击已选项不做操作（单选不取消）
  if (answers.value[q.id] === key) return
  answers.value[q.id] = key
  // 单选题选择即提交
  submitAnswer(q)
}

function toggleMultiChoice(q, key) {
  if (submitted.value[q.id]) return
  if (!multiAnswers.value[q.id]) multiAnswers.value[q.id] = []
  const arr = multiAnswers.value[q.id]
  const idx = arr.indexOf(key)
  if (idx === -1) arr.push(key)
  else arr.splice(idx, 1)
}

function isMultiSelected(q, key) {
  return multiAnswers.value[q.id]?.includes(key)
}

/** 解析 answer 字段：多选用 JSON.parse，其他直接返回字符串 */
function parseAnswerKeys(answer) {
  if (!answer) return []
  // 尝试 JSON.parse（多选 answer 是 JSON 数组字符串）
  try {
    const parsed = JSON.parse(answer)
    if (Array.isArray(parsed)) return parsed.map(s => String(s).trim()).filter(Boolean)
  } catch { /* 不是 JSON，走下面 */ }
  return [answer]
}

function optClass(q, key) {
  if (!submitted.value[q.id]) return ''
  const correct = isCorrectAnswer(q, key)
  const selected = q.question_type === 'choice'
    ? answers.value[q.id] === key
    : multiAnswers.value[q.id]?.includes(key)
  if (correct && selected) return 'opt-correct'
  if (correct) return 'opt-correct'
  if (selected) return 'opt-wrong'
  return 'opt-dimmed'
}

function isCorrectAnswer(q, key) {
  if (q.question_type === 'choice') return q.answer === key
  if (q.question_type === 'multi_choice') {
    return parseAnswerKeys(q.answer).includes(key)
  }
  return false
}

function submitAnswer(q) {
  const qid = q.id
  let correct = false

  if (q.question_type === 'choice') {
    correct = answers.value[qid] === q.answer
  } else if (q.question_type === 'multi_choice') {
    const userSet = new Set(multiAnswers.value[qid] || [])
    const correctSet = new Set(parseAnswerKeys(q.answer))
    correct = userSet.size === correctSet.size && [...userSet].every(k => correctSet.has(k))
  } else if (q.question_type === 'fill') {
    const userAns = (fillAnswers.value[qid] || '').trim().replace(/\s+/g, '')
    const correctAns = (q.answer || '').trim().replace(/\s+/g, '')
    correct = userAns === correctAns
  } else {
    // 简答/论述：关键词匹配（M3.1 文本匹配，M4 LLM）
    const userAns = (textAnswers.value[qid] || '').trim()
    const correctAns = (q.answer || '').trim()
    if (!userAns) { correct = false }
    else if (correctAns.length > 20) {
      // 长答案：检查关键词覆盖
      const keywords = correctAns.split(/[,，、\s]+/).filter(k => k.length >= 2)
      const matched = keywords.filter(k => userAns.includes(k))
      correct = keywords.length > 0 ? matched.length / keywords.length >= 0.5 : false
    } else {
      correct = userAns.includes(correctAns) || correctAns.includes(userAns)
    }
  }

  submitted.value[qid] = true
  feedbackCorrect.value[qid] = correct

  const timeSpent = startTimes.value[qid] ? Date.now() - startTimes.value[qid] : 0

  // 记录学习事件
  let userAnswer = ''
  if (q.question_type === 'choice') userAnswer = answers.value[qid] || ''
  else if (q.question_type === 'multi_choice') userAnswer = (multiAnswers.value[qid] || []).join(',')
  else if (q.question_type === 'fill') userAnswer = fillAnswers.value[qid] || ''
  else userAnswer = (textAnswers.value[qid] || '').slice(0, 100)

  learningStore.record('question_answered', {
    question_id: qid,
    context: {
      question_type: q.question_type,
      user_answer: userAnswer,
      is_correct: correct,
      time_spent_ms: timeSpent,
    },
  })
}

function resetQuestion(q) {
  const qid = q.id
  submitted.value[qid] = false
  feedbackCorrect.value[qid] = undefined
  if (q.question_type === 'choice') answers.value[qid] = null
  else if (q.question_type === 'multi_choice') multiAnswers.value[qid] = []
  else if (q.question_type === 'fill') fillAnswers.value[qid] = ''
  else textAnswers.value[qid] = ''
  startTimes.value[qid] = Date.now()
}

function correctAnswerLabel(q) {
  if (q.question_type === 'choice') {
    const k = q.answer || ''
    return `${k}. ${q.options?.[k] || ''}`
  }
  if (q.question_type === 'multi_choice') {
    const keys = parseAnswerKeys(q.answer)
    return keys.map(k => `${k}. ${q.options?.[k] || ''}`).join('；')
  }
  return q.answer || ''
}

// ── 标签 ──

function typeLabel(type) {
  const map = { choice: '单选', multi_choice: '多选', fill: '填空', short_answer: '简答', essay: '论述' }
  return map[type] || type
}

function bloomLabel(level) {
  const map = { remember: '识记', understand: '理解', apply: '应用', analyze: '分析', evaluate: '评价' }
  return map[level] || level
}
</script>

<style scoped>
.question-viewer {
  padding: 20px 24px;
}

.qv-empty {
  text-align: center;
  color: var(--p-text-muted);
  padding: 60px 24px;
  font-size: 13px;
}

.qv-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.qv-card {
  background: var(--p-surface);
  border: 1px solid var(--p-border);
  border-radius: var(--r-lg);
  padding: 16px 20px;
  transition: border-color 0.12s ease, box-shadow 0.12s ease;
}

.qv-card:hover {
  border-color: #cbd5e1;
  box-shadow: var(--shadow-sm);
}

.qv-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.qv-type {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: 20px;
  letter-spacing: 0.02em;
}

.type-choice { background: #EEF0FF; color: var(--p-primary); }
.type-multi_choice { background: #ede9fe; color: #7c3aed; }
.type-fill { background: #dbeafe; color: #1d4ed8; }
.type-short_answer { background: #fef3c7; color: #b45309; }
.type-essay { background: #fce7f3; color: #be185d; }

.qv-bloom {
  font-size: 11px;
  color: var(--p-text-muted);
  font-weight: 500;
}

.qv-stem {
  font-size: 14px;
  line-height: 1.7;
  color: var(--p-text);
  margin-bottom: 12px;
}

/* ── 选项区 ── */

.qv-options {
  margin: 4px 0 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.qv-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: var(--r-sm);
  cursor: pointer;
  font-size: 13px;
  color: var(--p-text-secondary);
  transition: background 0.1s;
  border: 1px solid transparent;
}

.qv-option:hover {
  background: var(--p-surface-subtle);
}

.qv-option.opt-correct {
  background: #f0fdf4;
  border-color: #bbf7d0;
  color: #166534;
}

.qv-option.opt-wrong {
  background: #fef2f2;
  border-color: #fecaca;
  color: #991b1b;
}

.qv-option.opt-dimmed {
  opacity: 0.5;
}

.qv-radio, .qv-checkbox {
  flex-shrink: 0;
  width: 16px;
  height: 16px;
  border: 1.5px solid var(--p-text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  box-sizing: border-box;
}

.qv-radio { border-radius: 50%; }
.qv-checkbox { border-radius: 3px; }

.qv-radio.checked { border-color: var(--p-primary); }
.qv-checkbox.checked { border-color: var(--p-primary); background: var(--p-primary); }

.qv-dot {
  width: 8px;
  height: 8px;
  background: var(--p-primary);
  border-radius: 50%;
}

.qv-check {
  color: #fff;
  font-size: 11px;
  line-height: 1;
  font-weight: 700;
}

.opt-correct .qv-radio { border-color: #16a34a; }
.opt-correct .qv-radio .qv-dot { background: #16a34a; }
.opt-correct .qv-checkbox { border-color: #16a34a; background: #16a34a; }
.opt-correct .qv-checkbox .qv-check { color: #fff; }

.opt-wrong .qv-radio { border-color: #dc2626; }
.opt-wrong .qv-radio .qv-dot { background: #dc2626; }
.opt-wrong .qv-checkbox { border-color: #dc2626; background: #dc2626; }
.opt-wrong .qv-checkbox .qv-check { color: #fff; }

.qv-opt-key {
  font-weight: 600;
  color: var(--p-text-muted);
  min-width: 18px;
}

.qv-opt-text {
  flex: 1;
}

/* ── 填空输入 ── */

.qv-fill {
  margin: 8px 0;
}

.qv-input {
  width: 100%;
  max-width: 320px;
  padding: 8px 12px;
  border: 1px solid var(--p-border);
  border-radius: var(--r-md);
  font-size: 14px;
  color: var(--p-text);
  background: var(--p-surface);
  outline: none;
}

.qv-input:focus {
  border-color: var(--p-primary);
  box-shadow: 0 0 0 3px rgba(79, 106, 240, 0.12);
}

.qv-input:disabled {
  background: var(--p-surface-muted);
  opacity: 0.7;
}

/* ── 简答/论述 ── */

.qv-textarea-wrap {
  margin: 8px 0;
}

.qv-textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--p-border);
  border-radius: var(--r-md);
  font-size: 13px;
  color: var(--p-text);
  background: var(--p-surface);
  resize: vertical;
  font-family: inherit;
  line-height: 1.6;
  outline: none;
}

.qv-textarea:focus {
  border-color: var(--p-primary);
  box-shadow: 0 0 0 3px rgba(79, 106, 240, 0.12);
}

.qv-textarea:disabled {
  background: var(--p-surface-muted);
  opacity: 0.7;
}

/* ── 操作按钮 ── */

.qv-actions {
  margin-top: 10px;
}

.qv-submit {
  font-size: 13px;
  font-weight: 500;
  padding: 7px 20px;
  background: var(--p-primary);
  color: #fff;
  border: none;
  border-radius: var(--r-md);
  cursor: pointer;
  transition: background 0.12s;
}

.qv-submit:hover {
  background: var(--p-primary-hover);
}

.qv-retry {
  font-size: 12px;
  font-weight: 500;
  padding: 6px 16px;
  background: var(--p-surface);
  border: 1px solid var(--p-border);
  border-radius: var(--r-md);
  color: var(--p-text-secondary);
  cursor: pointer;
  transition: all 0.1s;
}

.qv-retry:hover {
  border-color: var(--p-primary);
  color: var(--p-primary);
}

/* ── 反馈区 ── */

.qv-feedback {
  margin-top: 12px;
  padding: 12px 16px;
  border-radius: var(--r-md);
  border: 1px solid;
}

.fb-correct {
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.fb-wrong {
  background: #fef2f2;
  border-color: #fecaca;
}

.fb-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 6px;
}

.fb-correct .fb-text { color: #166534; }
.fb-wrong .fb-text { color: #991b1b; }

.fb-correct-answer {
  font-size: 13px;
  color: var(--p-text-secondary);
  margin-bottom: 6px;
  line-height: 1.5;
}

.fb-explanation {
  font-size: 13px;
  color: var(--p-text-secondary);
  line-height: 1.6;
  white-space: pre-wrap;
}

.fb-retry {
  margin-top: 8px;
}
</style>