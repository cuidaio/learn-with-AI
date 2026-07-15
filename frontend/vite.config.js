import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api/ask/stream': {
        target: 'http://backend:7480',
        changeOrigin: true,
      },
      '/api/ask': {
        target: 'http://backend:7480',
        changeOrigin: true,
      },
      '/api/documents': {
        target: 'http://backend:7480',
        changeOrigin: true,
      },
      '/api/health': {
        target: 'http://backend:7480',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
