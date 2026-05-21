/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  readonly VITE_DEFAULT_AOI?: string;
  readonly VITE_SHADEMAP_API_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
