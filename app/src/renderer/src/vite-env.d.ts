/// <reference types="vite/client" />

import type { AicBridge } from "../../preload/preload";

declare global {
  interface Window {
    aic?: AicBridge;
  }
}

export {};
