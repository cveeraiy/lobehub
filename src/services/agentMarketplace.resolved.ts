import { shouldUseRest } from '@/services/_restFlag';

import { fetchOnboardingAgentTemplates as trpcFetch } from './agentMarketplace';
import { fetchOnboardingAgentTemplates as restFetch } from './agentMarketplace.rest';

export const fetchOnboardingAgentTemplates = shouldUseRest('market') ? restFetch : trpcFetch;
