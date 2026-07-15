<template>
  <div class="question-panel">
    <div v-if="loading" class="question-empty">加载中...</div>

    <div v-else-if="questions.length === 0" class="question-empty">
      暂未生成题目。在上方面板选择知识点和题型后生成。
    </div>

    <div v-else class="question-list">
      <div class="question-header">
        <span class="question-count">题目 ({{ questions.length }})</span>
      </div>

      <div
        v-for="(q, idx) in questions"
        :key="q.id"
        class="question-card"
      >
        <!-- Meta row -->
        <div class="q-meta">
          <span class="q-type" :class="'type-' + q.question_type">
            {{ typeLabel(q.question_type) }}
          </span>
          <span v-if="q.bloom_level" class="q-bloom">{{ bloomLabel(q.bloom_level) }}</span>
          <span v-if="q.difficulty_estimate" class="q-difficulty">
            难度 {{ (q.difficulty_estimate * 100).toFixed(0) }}
          </span>
        </div>

        <!-- Stem -->
        <div class="q-stem">{{ q.stem }}</div>

        <!-- Options (choice / multi_choice) -->
        <div v-if="q.options" class="q-options">
          <div
            v-for="(optText, optKey) in q.options"
            :key="optKey"
            :class="['q-option', { 'q-option-correct': expandedIds.value.has(q.id) && isCorrectOption(q, optKey) }]"
          >
            <span class="q-opt-marker">
              <template v-if="q.question_type === 'multi_choice'">☐</template>
              <template v-else>○</template>
            </span>
            <span class="q-opt-key">{{ optKey }}.</span>
            <span class="q-opt-text">{{ optText }}</span>
            <span v-if="expandedIds.value.has(q.id) && isCorrectOption(q, optKey)" class="q-opt-correct">✓</span>
          </div>
        </div>

        <!-- Answer (collapsible) -->
        <div class="q-answer-section">
          <button class="q-toggle" @click="toggleAnswer(q.id)">
            {{ expandedIds.value.has(q.id) ? '隐藏答案' : '显示答案' }}
          </button>
          <div v-if="expandedIds.value.has(q.id)" class="q-answer">
            {{ q.answer }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { shallowRef } from 'vue'

const props = defineProps({
  questions: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
})

const expandedIds = shallowRef(new Set())

function toggleAnswer(id) {
  const next = new Set(expandedIds.value)
  if (next.has(id)) {
    next.delete(id)
  } else {
    next.add(id)
  }
  expandedIds.value = next
}

function isCorrectOption(q, key) {
  if (q.question_type === 'multi_choice') {
    try {
      const correct = JSON.parse(q.answer)
      return Array.isArray(correct) && correct.includes(key)
    } catch {
      return false
    }
  }
  return q.answer === key
}

function typeLabel(type) {
  const map = {
    choice: '单选',
    multi_choice: '多选',
    fill: '填空',
    short_answer: '简答',
    essay: '论述',
  }
  return map[type] || type
}

function bloomLabel(level) {
  const map = {
    remember: '识记',
    understand: '理解',
    apply: '应用',
    analyze: '分析',
    evaluate: '评价',
  }
  return map[level] || level
}
</script>

<style scoped>
.question-panel {
  height: 100%;
  overflow-y: auto;
  background: #f9fafb;
  flex: 1;
}

.question-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #9ca3af;
  font-size: 15px;
  padding: 24px;
}

.question-header {
  padding: 16px 24px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
}

.question-count {
  font-size: 1rem;
  font-weight: 600;
  color: #374151;
}

.question-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.question-card {
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  padding: 16px 24px;
}

.q-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.q-type {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
}

.type-choice { background: #e0e7ff; color: #4338ca; }
.type-multi_choice { background: #ede9fe; color: #7c3aed; }
.type-fill { background: #dbeafe; color: #1d4ed8; }
.type-short_answer { background: #fef3c7; color: #b45309; }
.type-essay { background: #fce7f3; color: #be185d; }

.q-bloom {
  font-size: 11px;
  color: #6b7280;
  background: #f3f4f6;
  padding: 2px 6px;
  border-radius: 4px;
}

.q-difficulty {
  font-size: 11px;
  color: #6b7280;
}

.q-stem {
  font-size: 14px;
  line-height: 1.6;
  color: #1f2937;
  margin-bottom: 8px;
}

.q-options {
  margin: 8px 0;
}

.q-option {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
  font-size: 13px;
  color: #374151;
}

.q-option-correct {
  background: #f0fdf4;
  border-radius: 4px;
  padding: 4px 6px;
}

.q-opt-marker {
  font-size: 12px;
  color: #9ca3af;
  width: 14px;
  text-align: center;
}

.q-opt-key {
  font-weight: 600;
  color: #6b7280;
  min-width: 16px;
}

.q-opt-correct {
  color: #16a34a;
  font-weight: bold;
  margin-left: auto;
}

.q-answer-section {
  margin-top: 4px;
}

.q-toggle {
  font-size: 12px;
  color: #3b82f6;
  cursor: pointer;
  background: none;
  border: none;
  padding: 0;
}
.q-toggle:hover {
  color: #2563eb;
}

.q-answer {
  margin-top: 8px;
  padding: 10px 12px;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.5;
  color: #166534;
  white-space: pre-wrap;
}
</style>
