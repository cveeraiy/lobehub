import { shouldUseRest } from '@/services/_restFlag';

import { mcpService as trpcService } from './mcp';
import { mcpService as restService } from './mcp.rest';

export const mcpService = shouldUseRest('mcp') ? restService : trpcService;
