import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react({
      babel: {
        plugins: [['babel-plugin-react-compiler']],
      },
    }),
  ],
  server: {
    port: 5173,
    strictPort: true,
    // 不需要 proxy，因为是通过后端的 8000 端口统一访问
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
  }
})
