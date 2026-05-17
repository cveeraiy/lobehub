import { shouldUseRest } from '@/services/_restFlag';

import { agentDocumentService as trpcService } from './agentDocument';
import { agentDocumentService as restService } from './agentDocument.rest';

export { agentDocumentSWRKeys } from '@/services/document/swrKeys';

export const agentDocumentService = shouldUseRest('agentDocument') ? restService : trpcService;
