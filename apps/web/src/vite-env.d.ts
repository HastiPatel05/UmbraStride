/// <reference types="vite/client" />

// Copyright (c) 2026 Tanmay Godse and Hasti Pareshbhai Patel. All Rights Reserved.

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  readonly VITE_DEFAULT_AOI?: string;
  readonly VITE_MAPBOX_ACCESS_TOKEN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
