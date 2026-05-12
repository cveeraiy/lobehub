// Stub: Electron desktop features removed for enterprise web-only build
export interface PageReference {
  icon?: string;
  id: string;
  path: string;
  timestamp?: number;
  title?: string;
  type?: string;
}

export interface CachedPageData extends PageReference {
  pinned?: boolean;
}
