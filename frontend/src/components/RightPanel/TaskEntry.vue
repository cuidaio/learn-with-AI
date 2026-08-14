<template>
  <div class="task-entry">
    <button class="create-btn" @click="showModal = true">＋ 创建任务</button>
  </div>
  <CreateTaskModal v-if="showModal" @close="showModal = false" />
</template>

<script setup>
import { ref } from 'vue'
import CreateTaskModal from './CreateTaskModal.vue'

const showModal = ref(false)
</script>

<style scoped>
.task-entry {
  padding: 14px 16px 8px;
  flex-shrink: 0;
}

.create-btn {
  width: 100%;
  padding: 10px 0;
  background: var(--p-primary);
  color: #fff;
  border: none;
  border-radius: var(--r-md);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.12s ease, box-shadow 0.12s ease;
  box-shadow: var(--shadow-xs);
}

.create-btn:hover {
  background: var(--p-primary-hover);
  box-shadow: var(--shadow-sm);
}

.create-btn:active {
  transform: scale(0.98);
}
</style>
