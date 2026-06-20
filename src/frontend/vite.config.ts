import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: 5173,
    watch: {
      // Bật polling khi chạy trong Docker để hot-reload nhận diện
      // thay đổi file qua bind-mount. Local dev giữ inotify (nhanh hơn).
      usePolling: process.env.VITE_USE_POLLING === 'true',
    },
  },
})
