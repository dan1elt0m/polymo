import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";

const rootDir = path.resolve(__dirname, "builder-ui");
const staticDir = path.resolve(__dirname, "src/polymo/builder/static");

export default defineConfig({
  root: rootDir,
  plugins: [react()],
  publicDir: path.resolve(rootDir, "public"),
  build: {
    outDir: staticDir,
    emptyOutDir: false,
    rollupOptions: {
      input: path.resolve(rootDir, "index.html"),
      output: {
        entryFileNames: "main.js",
        chunkFileNames: "assets/[name].js",
        assetFileNames: ({ name }) => {
          if (name && name.endsWith(".css")) {
            return "main.css";
          }
          return "assets/[name][extname]";
        },
      },
    },
  },
  server: {
    port: 5173,
    open: false,
  },
  resolve: {
    alias: {
      "@": path.resolve(rootDir, "src"),
    },
  },
});
