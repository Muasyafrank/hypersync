import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Third-party code that changes far less often than app code. Splitting it
// out keeps the vendor chunks cached across deploys.
const VENDOR_CHUNKS = {
  react: ['react', 'react-dom', 'react-router-dom'],
  charts: ['recharts', 'd3-'],
  ui: ['react-bootstrap', 'lucide-react', '@restart'],
};

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  build: {
    rollupOptions: {
      output: {
        // Rolldown (Vite 8) requires the function form.
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          const match = Object.entries(VENDOR_CHUNKS).find(([, packages]) =>
            packages.some((name) => id.includes(`node_modules/${name}`)),
          );
          return match ? match[0] : 'vendor';
        },
      },
    },
  },
});
