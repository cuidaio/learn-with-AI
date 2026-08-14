<template>
  <div class="config-tools">
    <span
      :class="['status-badge', backendConnected ? 'online' : 'offline']"
      :title="backendConnected ? '后端已连接' : '后端未连接'"
    >
      <span class="status-dot"></span>
      <span class="status-text">{{ backendConnected ? '已连接' : '未连接' }}</span>
    </span>
    <button class="config-btn" @click="$emit('toggle')" title="API 配置" aria-label="API 配置">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="3"/>
        <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
      </svg>
    </button>
  </div>
</template>

<script setup>
defineProps({
  backendConnected: { type: Boolean, default: false },
})
defineEmits(['toggle'])
</script>

<style scoped>
.config-tools {
  display: flex;
  align-items: center;
  gap: 4px;
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 2px 10px 2px 8px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
  line-height: 22px;
  transition: all 0.15s ease;
}

.status-badge.online {
  background: var(--p-success-light);
  color: #15803d;
}

.status-badge.offline {
  background: var(--p-error-light);
  color: #b91c1c;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.online .status-dot {
  background: #22c55e;
}

.offline .status-dot {
  background: #ef4444;
}

.status-text {
  font-size: 12px;
}

.config-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: none;
  border-radius: var(--r-sm);
  background: transparent;
  color: var(--p-text-muted);
  cursor: pointer;
  transition: all 0.15s ease;
}

.config-btn:hover {
  background: var(--p-surface-muted);
  color: var(--p-text-secondary);
}

.config-btn:active {
  transform: scale(0.94);
}
</style>
