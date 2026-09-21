import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: './',
  resolve: {
    alias: {
      '@': new URL('./src', import.meta.url).pathname,
    },
    conditions: ['import', 'module', 'browser', 'default'],
  },
  build: {
    outDir: '../../docs',
    emptyOutDir: false,
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        assetFileNames: 'assets/v2-[name]-[hash][extname]',
        chunkFileNames: 'assets/v2-[name]-[hash].js',
        entryFileNames: 'assets/v2-[name]-[hash].js',
        manualChunks: {
          echarts: ['echarts', 'echarts-for-react'],
          react: ['react', 'react-dom', 'react-router-dom'],
        },
      },
    },
  },
})
