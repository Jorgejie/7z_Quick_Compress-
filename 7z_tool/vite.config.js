import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    outDir: 'html_dist',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/check_7z': 'http://127.0.0.1:8765',
      '/stat': 'http://127.0.0.1:8765',
      '/compress': 'http://127.0.0.1:8765',
      '/extract': 'http://127.0.0.1:8765',
      '/upload': 'http://127.0.0.1:8765',
      '/pick_files': 'http://127.0.0.1:8765',
      '/pick_folder': 'http://127.0.0.1:8765',
      '/open_finder': 'http://127.0.0.1:8765',
      '/get_config': 'http://127.0.0.1:8765',
      '/save_config': 'http://127.0.0.1:8765',
    },
  },
});
