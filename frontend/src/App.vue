<template>
  <div id="app-root">
    <!-- Header -->
    <header class="app-header">
      <h1 class="app-title">learn-with-AI</h1>
      <div class="header-right">
        <ApiConfigButton :backendConnected="connected" @toggle="configStore.togglePanel()" />
      </div>
    </header>

    <!-- 三栏工作台 -->
    <MainLayout />

    <!-- API 配置面板 -->
    <ApiConfigPanel :visible="configStore.state.isPanelOpen" @close="configStore.closePanel()" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import MainLayout from './layouts/MainLayout.vue'
import ApiConfigButton from './components/ApiConfigButton.vue'
import ApiConfigPanel from './components/ApiConfigPanel.vue'
import { useConfigStore } from './stores/useConfigStore'

const connected = ref(false)
const configStore = useConfigStore()

onMounted(async () => {
  try {
    const res = await fetch('/api/health')
    const data = await res.json()
    connected.value = data.status === 'healthy'
  } catch {
    connected.value = false
  }
})
</script>

<style>
/* ========== Design Tokens ========== */
:root {
  --p-primary: #4F6AF0;
  --p-primary-hover: #3D56D9;
  --p-primary-light: #EEF0FF;
  --p-accent: #f59e0b;
  --p-accent-light: #fef3c7;
  --p-surface: #ffffff;
  --p-surface-subtle: #f8fafc;
  --p-surface-muted: #f1f5f9;
  --p-border: #e2e8f0;
  --p-border-light: #f1f5f9;
  --p-text: #0f172a;
  --p-text-secondary: #475569;
  --p-text-muted: #94a3b8;
  --p-success: #22c55e;
  --p-success-light: #f0fdf4;
  --p-error: #ef4444;
  --p-error-light: #fef2f2;
  --p-warning: #f59e0b;
  --p-warning-light: #fffbeb;
  --shadow-xs: 0 1px 2px rgba(15, 23, 42, 0.04);
  --shadow-sm: 0 1px 3px rgba(15, 23, 42, 0.06), 0 1px 2px rgba(15, 23, 42, 0.04);
  --shadow-md: 0 4px 12px rgba(15, 23, 42, 0.08);
  --shadow-lg: 0 8px 30px rgba(15, 23, 42, 0.12);
  --r-xs: 4px;
  --r-sm: 6px;
  --r-md: 8px;
  --r-lg: 12px;
  --r-xl: 14px;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Inter', system-ui, sans-serif;
  background: var(--p-surface-muted);
  color: var(--p-text);
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  height: 100vh;
  overflow: hidden;
}

#app {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

#app-root {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
  height: 48px;
  background: var(--p-surface);
  border-bottom: 1px solid var(--p-border);
  flex-shrink: 0;
  z-index: 10;
  box-shadow: var(--shadow-xs);
}

.app-title {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--p-text);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* ========== Global transitions ========== */
button, input, select, textarea {
  transition: all 0.15s ease;
}
</style>
