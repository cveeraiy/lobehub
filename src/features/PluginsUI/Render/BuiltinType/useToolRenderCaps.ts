import type { ToolRenderCapabilities } from '@lobechat/shared-tool-ui';
import { useMemo } from 'react';

import { useChatStore } from '@/store/chat';
import { chatToolSelectors } from '@/store/chat/slices/builtinTool/selectors';

/**
 * Provides capabilities for tool render components.
 * Web-only: provides loading state (no local file operations).
 */
export const useToolRenderCaps = (): ToolRenderCapabilities => {
  return useMemo<ToolRenderCapabilities>(
    () => ({
      isLoading: (messageId: string) => {
        return chatToolSelectors.isSearchingLocalFiles(messageId)(useChatStore.getState());
      },
    }),
    [],
  );
};
