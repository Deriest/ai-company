/**
 * Centralized update source configuration.
 * Re-exports pure helpers; main process may override base URL from store/env.
 */
export {
  type UpdateChannel,
  type UpdateConfig,
  DEFAULT_UPDATE_BASE_URL,
  PUBLIC_UPDATE_BASE_URL,
  resolveUpdateBaseUrl,
  manifestUrl,
  defaultUpdateConfig,
} from "../shared/updateLogic";
