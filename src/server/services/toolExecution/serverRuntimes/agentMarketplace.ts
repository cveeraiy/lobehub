import { AgentMarketplaceIdentifier } from '@lobechat/builtin-tools';
import { AgentMarketplaceExecutionRuntime } from '@lobechat/builtin-tools/agentMarketplaceExecutionRuntime';

import { type ServerRuntimeRegistration } from './types';

export const agentMarketplaceRuntime: ServerRuntimeRegistration = {
  factory: () => {
    return new AgentMarketplaceExecutionRuntime();
  },
  identifier: AgentMarketplaceIdentifier,
};
