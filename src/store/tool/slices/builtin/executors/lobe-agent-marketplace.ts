import { AgentMarketplaceExecutionRuntime } from '@lobechat/builtin-tools/agentMarketplaceExecutionRuntime';
import { AgentMarketplaceExecutor } from '@lobechat/builtin-tools/agentMarketplaceExecutor';

import {
  trackOnboardingMarketplacePicked,
  trackOnboardingMarketplaceShown,
} from '@/services/onboardingMetrics';

const runtime = new AgentMarketplaceExecutionRuntime({
  onPicked: (payload) => {
    trackOnboardingMarketplacePicked(payload);
  },
  onShown: (payload) => {
    trackOnboardingMarketplaceShown(payload);
  },
});

export const agentMarketplaceExecutor = new AgentMarketplaceExecutor(runtime);
