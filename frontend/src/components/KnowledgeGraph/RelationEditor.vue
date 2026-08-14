<template>
  <div class="re-backdrop" @click.self="onCancel">
    <div class="relation-editor">
      <div class="re-header">{{ panelTitle }}</div>
      <div class="re-body">
        <div class="re-entities">
          <span class="re-entity-name">{{ sourceName }}</span>
          <span class="re-arrow">→</span>
          <span class="re-entity-name">{{ targetName }}</span>
        </div>
        <div class="re-field">
          <label class="re-label" for="re-type">关系类型</label>
          <div class="re-select-wrap">
            <select id="re-type" v-model="localRelationType" class="re-select">
              <option v-for="t in RELATION_TYPES" :key="t.value" :value="t.value">{{ t.label }}</option>
            </select>
            <span class="re-select-arrow">▼</span>
          </div>
        </div>
        <div class="re-field">
          <label class="re-label" for="re-desc">描述</label>
          <input id="re-desc" v-model="localDescription" class="re-input" placeholder="可选的关系描述..." maxlength="200" />
        </div>
      </div>
      <div class="re-footer">
        <button class="re-btn re-btn-delete" :disabled="!hasExistingRelation" @click="onDelete">删除</button>
        <div class="re-footer-right">
          <button class="re-btn re-btn-cancel" @click="onCancel">取消</button>
          <button class="re-btn re-btn-save" @click="onSave">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'

const RELATION_TYPES = [
  { value: 'related_to', label: '相关 (related_to)' },
  { value: 'contains', label: '包含 (contains)' },
  { value: 'part_of', label: '组成部分 (part_of)' },
  { value: 'causes', label: '导致 (causes)' },
  { value: 'influences', label: '影响 (influences)' },
  { value: 'is_a', label: '属于 (is_a)' },
  { value: 'used_for', label: '用于 (used_for)' },
  { value: 'applies_to', label: '适用于 (applies_to)' },
  { value: 'example_of', label: '示例 (example_of)' },
  { value: 'opposite_of', label: '相反 (opposite_of)' },
  { value: 'precedes', label: '先于 (precedes)' },
  { value: 'follows', label: '后于 (follows)' },
  { value: 'supports', label: '支持 (supports)' },
  { value: 'contrasts', label: '对比 (contrasts)' },
  { value: 'contradicts', label: '矛盾 (contradicts)' },
  { value: 'defines', label: '定义 (defines)' },
  { value: 'derived_from', label: '源于 (derived_from)' },
  { value: 'develops', label: '发展 (develops)' },
]

const props = defineProps({
  sourceName: { type: String, default: '' },
  targetName: { type: String, default: '' },
  relationType: { type: String, default: '' },
  description: { type: String, default: '' },
  hasExistingRelation: { type: Boolean, default: false },
  mode: { type: String, default: 'node' },
})

const emit = defineEmits(['save', 'delete', 'cancel'])

const localRelationType = ref(props.relationType || 'related_to')
const localDescription = ref(props.description || '')

watch(() => props.relationType, (v) => { localRelationType.value = v || 'related_to' })
watch(() => props.description, (v) => { localDescription.value = v || '' })

const panelTitle = computed(() => props.mode === 'edge' ? '编辑连线' : '编辑关系')

function onSave() {
  emit('save', { relationType: localRelationType.value, description: localDescription.value })
}
function onDelete() { emit('delete') }
function onCancel() { emit('cancel') }
</script>

<style scoped>
.re-backdrop {
  position: fixed;
  inset: 0;
  z-index: 99;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(15,23,42,0.15);
  animation: re-fadein 0.15s ease-out;
}
@keyframes re-fadein { from { opacity: 0 } to { opacity: 1 } }

.relation-editor {
  width: 280px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  box-shadow: 0 8px 30px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.06);
  font-size: 13px;
  color: #1e293b;
  animation: re-enter 0.15s ease-out;
}
@keyframes re-enter { from { opacity: 0; transform: scale(0.95) translateY(-4px); } to { opacity: 1; transform: scale(1); } }

.re-header { padding: 10px 14px; font-weight: 600; font-size: 13px; border-bottom: 1px solid #f1f5f9; color: #0f172a; }
.re-body { padding: 10px 14px; display: flex; flex-direction: column; gap: 10px; }
.re-entities { display: flex; align-items: center; gap: 6px; padding: 6px 10px; background: #f8fafc; border-radius: 6px; font-size: 12px; }
.re-entity-name { font-weight: 500; color: #1e293b; max-width: 100px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.re-arrow { color: #94a3b8; flex-shrink: 0; font-size: 14px; }
.re-field { display: flex; flex-direction: column; gap: 4px; }
.re-label { font-size: 11px; font-weight: 500; color: #64748b; }
.re-select-wrap { position: relative; }
.re-select { width: 100%; padding: 6px 28px 6px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 12px; color: #1e293b; background: #fff; appearance: none; cursor: pointer; outline: none; }
.re-select:focus { border-color: #4F6AF0; box-shadow: 0 0 0 2px rgba(79,106,240,0.12); }
.re-select-arrow { position: absolute; right: 10px; top: 50%; transform: translateY(-50%); font-size: 8px; color: #94a3b8; pointer-events: none; }
.re-input { width: 100%; padding: 6px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 12px; color: #1e293b; outline: none; box-sizing: border-box; }
.re-input:focus { border-color: #4F6AF0; box-shadow: 0 0 0 2px rgba(79,106,240,0.12); }
.re-input::placeholder { color: #94a3b8; }
.re-footer { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-top: 1px solid #f1f5f9; }
.re-footer-right { display: flex; gap: 6px; }
.re-btn { padding: 5px 12px; border-radius: 6px; font-size: 12px; font-weight: 500; cursor: pointer; border: 1px solid transparent; transition: background 0.15s, border-color 0.15s; }
.re-btn:disabled { opacity: 0.35; cursor: not-allowed; }
.re-btn-delete { color: #ef4444; background: transparent; border-color: #fecaca; }
.re-btn-delete:not(:disabled):hover { background: #fef2f2; border-color: #fca5a5; }
.re-btn-cancel { color: #64748b; background: transparent; border-color: #e2e8f0; }
.re-btn-cancel:hover { background: #f8fafc; border-color: #cbd5e1; }
.re-btn-save { color: #fff; background: #4F6AF0; border-color: #4F6AF0; }
.re-btn-save:hover { background: #3b57d9; }
</style>
