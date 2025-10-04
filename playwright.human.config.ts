import type { PlaywrightTestConfig } from "@playwright/test";
import baseConfig from "./playwright.config";

const config: PlaywrightTestConfig = {
  ...baseConfig,
  use: {
    ...baseConfig.use,
    launchOptions: {
      ...(baseConfig.use?.launchOptions ?? {}),
      slowMo: 900,
    },
    colorScheme: "dark",
  },
};

export default config;
