import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  root: path.resolve(__dirname, "src/renderer"),
  base: "./",
  resolve: {
    alias: { "@": path.resolve(__dirname, "src/renderer/src") },
  },
  server: {
    host: "127.0.0.1",
    port: 5174,
    strictPort: true,
  },
  build: {
    outDir: path.resolve(__dirname, "dist"),
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom"],
        },
      },
    },
  },
});
