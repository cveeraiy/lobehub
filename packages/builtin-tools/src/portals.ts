import { type BuiltinPortal } from '@lobechat/types';

import { WebBrowsingManifest, WebBrowsingPortal } from './webBrowsing/client';

export const BuiltinToolsPortals: Record<string, BuiltinPortal> = {
  [WebBrowsingManifest.identifier]: WebBrowsingPortal as BuiltinPortal,
};
