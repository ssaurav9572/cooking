import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "in.cookai.app",
  appName: "CookAI",
  webDir: "../frontend",
  server: { androidScheme: "https" },
};

export default config;
