import { shouldUseRest } from '@/services/_restFlag';

import {
  agentDocumentService as trpcService,
  mapAgentDocumentsToContext as trpcMapAgentDocumentsToContext,
  resolveAgentDocumentsContext as trpcResolveAgentDocumentsContext,
} from './agentDocument';
import {
  agentDocumentService as restService,
  mapAgentDocumentsToContext as restMapAgentDocumentsToContext,
  resolveAgentDocumentsContext as restResolveAgentDocumentsContext,
} from './agentDocument.rest';

export { agentDocumentSWRKeys } from '@/services/document/swrKeys';

const useRest = shouldUseRest('agentDocument');

export const agentDocumentService = useRest ? restService : trpcService;
export const mapAgentDocumentsToContext = useRest
  ? restMapAgentDocumentsToContext
  : trpcMapAgentDocumentsToContext;
export const resolveAgentDocumentsContext = useRest
  ? restResolveAgentDocumentsContext
  : trpcResolveAgentDocumentsContext;
