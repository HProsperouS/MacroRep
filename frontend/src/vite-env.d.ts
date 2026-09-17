/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL for the FastAPI backend. Empty = use the Vite dev proxy (/api). */
  readonly VITE_API_BASE_URL?: string
  /** "true" | "false". Defaults to true in dev: answer API calls with the in-memory mock. */
  readonly VITE_USE_MOCK_API?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
