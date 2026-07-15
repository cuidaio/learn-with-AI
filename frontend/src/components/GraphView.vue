<template>
  <div class="graph-panel">
    <!-- Loading -->
    <div v-if="loading && !graphData" class="graph-empty">加载中...</div>

    <!-- Phase 1: entities still extracting -->
    <div v-else-if="entitiesBuilding" class="graph-empty graph-building">
      <div class="building-spinner"></div>
      <span>实体提取中，请稍候...</span>
    </div>

    <!-- Phase 2: entities done, relations still extracting -->
    <div v-else-if="relationsBuilding" class="graph-content">
      <div class="graph-toolbar">
        <span class="graph-title">知识图谱</span>
      </div>
      <div class="graph-columns">
        <div class="graph-col">
          <h3 class="col-title">实体 ({{ graphData.entities.length }})</h3>
          <div class="entity-list">
            <div v-for="entity in graphData.entities" :key="entity.id" class="entity-item">
              <span class="entity-name">{{ entity.name }}</span>
              <span class="entity-type" :class="'type-' + (entity.entity_type || 'concept')">
                {{ entity.entity_type || '概念' }}
              </span>
              <span v-if="entity.description" class="entity-desc">{{ entity.description }}</span>
            </div>
          </div>
        </div>
        <div class="graph-col graph-building">
          <div class="building-spinner"></div>
          <span>关系提取中...</span>
        </div>
      </div>
    </div>

    <!-- Empty (no graph data at all) -->
    <div v-else-if="!graphData" class="graph-empty">暂无知识图谱数据。上传文档后自动生成。</div>

    <!-- Content: entities + relations both ready -->
    <div v-else class="graph-content">
      <!-- Toolbar -->
      <div class="graph-toolbar">
        <span class="graph-title">知识图谱</span>
        <div class="graph-actions">
          <button class="btn btn-primary btn-sm" @click="$emit('generate', null)" :disabled="generating">
            {{ generating ? '生成中...' : '生成全部题目' }}
          </button>
        </div>
      </div>

      <!-- Two-column layout -->
      <div class="graph-columns">
        <!-- Entities -->
        <div class="graph-col">
          <h3 class="col-title">实体 ({{ graphData.entities.length }})</h3>
          <div class="entity-list">
            <div
              v-for="entity in graphData.entities"
              :key="entity.id"
              class="entity-item"
            >
              <span class="entity-name">{{ entity.name }}</span>
              <span class="entity-type" :class="'type-' + (entity.entity_type || 'concept')">
                {{ entity.entity_type || '概念' }}
              </span>
              <span v-if="entity.description" class="entity-desc">{{ entity.description }}</span>
            </div>
          </div>
        </div>

        <!-- Relations -->
        <div class="graph-col">
          <h3 class="col-title">关系 ({{ graphData.relations.length }})</h3>
          <div class="relation-list">
            <div
              v-for="rel in graphData.relations"
              :key="rel.id"
              class="relation-item"
            >
              <span class="rel-source">{{ rel.source_name || '?' }}</span>
              <span class="rel-arrow">──[{{ rel.relation_type }}]──></span>
              <span class="rel-target">{{ rel.target_name || '?' }}</span>
              <span v-if="rel.description" class="rel-desc">{{ rel.description }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  graphData: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  generating: { type: Boolean, default: false },
})

const emit = defineEmits(['generate', 'refresh'])

// Phase 1: no entities yet = LLM still extracting
const entitiesBuilding = computed(() => {
  return !props.graphData || (props.graphData.entities && props.graphData.entities.length === 0)
})

// Phase 2: entities exist but no relations yet
const relationsBuilding = computed(() => {
  return props.graphData
    && props.graphData.entities
    && props.graphData.entities.length > 0
    && (!props.graphData.relations || props.graphData.relations.length === 0)
})

// Auto-poll: refresh every 5s while any building phase
import { watch, onUnmounted } from 'vue'
let pollTimer = null

watch([entitiesBuilding, relationsBuilding], ([entBuilding, relBuilding]) => {
  if (entBuilding || relBuilding) {
    if (!pollTimer) {
      pollTimer = setInterval(() => emit('refresh'), 5000)
    }
  } else if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.graph-panel {
  height: 100%;
  overflow-y: auto;
  background: #f9fafb;
}

.graph-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #9ca3af;
  font-size: 15px;
}

.graph-building {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  min-height: 200px;
}

.building-spinner {
  width: 28px;
  height: 28px;
  border: 3px solid #e5e7eb;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.graph-content {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.graph-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
}

.graph-title {
  font-size: 1rem;
  font-weight: 600;
  color: #374151;
}

.graph-columns {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.graph-col {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.graph-col:first-child {
  border-right: 1px solid #e5e7eb;
}

.col-title {
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
}

/* Entities */
.entity-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.entity-item {
  padding: 8px 12px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.entity-name {
  font-weight: 600;
  color: #1f2937;
  font-size: 13px;
}

.entity-type {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  background: #f3f4f6;
  color: #6b7280;
}

.type-concept { background: #dbeafe; color: #1d4ed8; }
.type-theorist { background: #fce7f3; color: #be185d; }
.type-theory { background: #fef3c7; color: #b45309; }
.type-method { background: #d1fae5; color: #059669; }
.type-fact { background: #e0e7ff; color: #4338ca; }

.entity-desc {
  width: 100%;
  font-size: 12px;
  color: #9ca3af;
  margin-top: 2px;
}

/* Relations */
.relation-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.relation-item {
  padding: 8px 12px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  font-size: 13px;
}

.rel-source, .rel-target {
  font-weight: 600;
  color: #1f2937;
}

.rel-arrow {
  color: #9ca3af;
  font-size: 11px;
  white-space: nowrap;
}

.rel-desc {
  width: 100%;
  font-size: 12px;
  color: #9ca3af;
  margin-top: 2px;
}

/* Buttons */
.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn-primary {
  background: #3b82f6;
  color: #fff;
}
.btn-primary:hover:not(:disabled) {
  background: #2563eb;
}
.btn-sm {
  padding: 6px 12px;
  font-size: 12px;
}
</style>
