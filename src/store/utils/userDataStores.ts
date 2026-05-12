import { unstable_batchedUpdates } from 'react-dom';

import { useAgentStore } from '@/store/agent';
import { useAgentGroupStore } from '@/store/agentGroup';
import { useChatStore } from '@/store/chat';
import { useDocumentStore } from '@/store/document';
import { useFileStore } from '@/store/file';
import { useHomeStore } from '@/store/home';
import { useKnowledgeBaseStore } from '@/store/library';
import { useMentionStore } from '@/store/mention';
import { useNotebookStore } from '@/store/notebook';
import { usePageStore } from '@/store/page';
import { useSessionStore } from '@/store/session';
import { useTaskStore } from '@/store/task';
import { useToolStore } from '@/store/tool';
import { useUserStore } from '@/store/user';
import { useUserMemoryStore } from '@/store/userMemory';
import type { ResetableStore } from '@/store/utils/resetableStore';

interface ResetableStoreApi {
  getState: () => ResetableStore;
}

const resetableStores: ResetableStoreApi[] = [
  useAgentGroupStore,
  useAgentStore,
  useChatStore,
  useDocumentStore,
  useFileStore,
  useHomeStore,
  useKnowledgeBaseStore,
  useMentionStore,
  useNotebookStore,
  usePageStore,
  useSessionStore,
  useTaskStore,
  useToolStore,
  useUserMemoryStore,
  useUserStore,
];

export interface StoreActions extends ResetableStore {}

const createStoreActions = (stores: ResetableStoreApi[]): StoreActions => ({
  reset: () => {
    unstable_batchedUpdates(() => {
      for (const store of stores) {
        store.getState().reset();
      }
    });
  },
});

export const stores = createStoreActions(resetableStores);
