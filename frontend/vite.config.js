import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// L'API est appelee en chemin relatif (/api/...) : en production le reverse-proxy
// nginx route /api/ vers le backend, en dev le proxy vite ci-dessous fait le meme
// travail. Plus d'URL absolue en dur, donc plus de dependance a une origine
// particuliere (le menu region/departement restait vide hors 127.0.0.1:5173).
const API_TARGET = process.env.VITE_API_PROXY || 'http://127.0.0.1:50000'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: API_TARGET,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
})