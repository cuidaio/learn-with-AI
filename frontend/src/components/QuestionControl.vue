<template>
  <div class="question-control">
    <div class="qc-title">
      <span>生成题目</span>
    </div>

    <!-- Scenario -->
    <div class="qc-section">
      <div class="qc-label">学习场景</div>
      <div class="scenario-group">
        <button
          v-for="s in scenarios"
          :key="s.key"
          :class="['scenario-btn', { active: selectedScenario === s.key }]"
          @click="selectedScenario = s.key"
        >{{ s.label }}</button>
      </div>
    </div>

    <!-- Entity selection -->
    <div class="qc-section">
      <div class="qc-label">选题范围</div>
      <label class="qc-radio">
        <input
          type="radio"
          value="all"
          v-model="entityMode"
          :disabled="entities.length === 0"
        />
        全部知识点（当前 {{ entities.length }} 个实体）
      </label>
      <label class="qc-radio">
        <input type="radio" value="select" v-model="entityMode" />
        选择知识点
      </label>
      <div v-if="entityMode === 'select'" class="qc-entity-list">
        <label v-for="e in entities" :key="e.id" class="qc-checkbox">
          <input type="checkbox" :value="e.id" v-model="selectedEntityIds" />
          {{ e.name }}
          <span v-if="e.entity_type" class="qc-entity-type">{{ e.entity_type }}</span>
        </label>
      </div>
    </div>

    <!-- Type selection -->
    <div class="qc-section">
      <div class="qc-label">题型（可多选）</div>
      <div class="qc-type-group">
        <label v-for="t in typeOptions" :key="t.key" class="qc-checkbox qc-type-checkbox">
          <input type="checkbox" :value="t.key" v-model="selectedTypes" />
          {{ t.label }}
        </label>
      </div>
    </div>

    <!-- Generate button -->
    <div class="qc-actions">
      <span class="qc-count">预计生成 {{ estimatedCount }} 题</span>
      <button
        class="qc-generate-btn"
        :disabled="!canGenerate || generating"
        @click="handleGenerate"
      >
        {{ generating ? '生成中...' : '生成题目' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  entities: { type: Array, default: () => [] },
  generating: { type: Boolean, default: false },
})

const emit = defineEmits(['generate'])

const scenarios = [
  { key: 'section_review', label: '章节自测' },
  { key: 'weakness', label: '薄弱专项' },
  { key: 'comprehensive', label: '综合模拟' },
]

const typeOptions = [
  { key: 'choice', label: '单选' },
  { key: 'multi_choice', label: '多选' },
  { key: 'fill', label: '填空' },
  { key: 'short_answer', label: '简答' },
  { key: 'essay', label: '论述' },
]

const selectedScenario = ref('section_review')
const entityMode = ref('all')
const selectedEntityIds = ref([])
const selectedTypes = ref(['choice', 'multi_choice', 'fill', 'short_answer', 'essay'])

const estimatedCount = computed(() => {
  const count = entityMode.value === 'all'
    ? props.entities.length
    : Math.max(1, selectedEntityIds.value.length)
  return Math.max(6, Math.min(50, count * 3))
})

const canGenerate = computed(() => {
  if (props.entities.length === 0) return false
  if (entityMode.value === 'select' && selectedEntityIds.value.length === 0) return false
  return selectedTypes.value.length > 0
})

function handleGenerate() {
  const ids = entityMode.value === 'all'
    ? props.entities.map(e => e.id)
    : selectedEntityIds.value

  emit('generate', {
    entityIds: ids,
    types: selectedTypes.value,
    totalCount: estimatedCount.value,
    scenario: selectedScenario.value,
  })
}
</script>

<style scoped>
.question-control {
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  padding: 16px 24px;
}

.qc-title {
  font-size: 1rem;
  font-weight: 600;
  color: #374151;
  margin-bottom: 12px;
}

.qc-section {
  margin-bottom: 12px;
}

.qc-label {
  font-size: 12px;
  font-weight: 500;
  color: #6b7280;
  margin-bottom: 6px;
}

.scenario-group {
  display: flex;
  gap: 6px;
}

.scenario-btn {
  padding: 4px 12px;
  font-size: 12px;
  border: 1px solid #d1d5db;
  border-radius: 14px;
  background: #fff;
  color: #374151;
  cursor: pointer;
}
.scenario-btn.active {
  background: #3b82f6;
  color: #fff;
  border-color: #3b82f6;
}

.qc-radio, .qc-checkbox {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #374151;
  cursor: pointer;
  margin: 2px 0;
}

.qc-entity-list {
  margin-left: 20px;
  max-height: 140px;
  overflow-y: auto;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 4px 8px;
}

.qc-entity-type {
  font-size: 10px;
  color: #9ca3af;
  margin-left: 2px;
}

.qc-type-group {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.qc-type-checkbox {
  font-size: 13px;
}

.qc-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
}

.qc-count {
  font-size: 12px;
  color: #6b7280;
}

.qc-generate-btn {
  padding: 6px 20px;
  font-size: 13px;
  font-weight: 500;
  border: none;
  border-radius: 6px;
  background: #3b82f6;
  color: #fff;
  cursor: pointer;
}
.qc-generate-btn:disabled {
  background: #9ca3af;
  cursor: not-allowed;
}
.qc-generate-btn:hover:not(:disabled) {
  background: #2563eb;
}
</style>
