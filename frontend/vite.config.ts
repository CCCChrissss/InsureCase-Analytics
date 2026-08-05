import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  // API 維持同源 /api；Vite 僅在開發與臨時展示時代理到本機 FastAPI。
  const env = loadEnv(mode, process.cwd(), "");
  const apiProxyTarget = env.VITE_DEV_API_PROXY_TARGET ?? "http://127.0.0.1:8000";

  return {
    plugins: [react()],
    server: {
      port: 5173,
      host: "127.0.0.1",
      // Quick Tunnel 每次會產生不同子網域，因此只開放 Cloudflare 管理的網域尾碼。
      allowedHosts: [".trycloudflare.com"],
      proxy: {
        "/api": {
          target: apiProxyTarget,
          changeOrigin: true
        }
      }
    }
  };
});
