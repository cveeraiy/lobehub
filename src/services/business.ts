import { restClient } from '@/libs/rest';

interface SelfHostedSubscription {
  plan: string;
  status: string;
  subscription: unknown;
  usageBasedBilling: boolean;
}

interface SelfHostedTopUp {
  balance: number;
  currency: string;
  enabled: boolean;
  mode: string;
}

interface SelfHostedSpend {
  currency: string;
  estimatedCost: number;
  inputTokens: number;
  messageCount: number;
  outputTokens: number;
  totalTokens: number;
}

class BusinessService {
  getSpend = async () => {
    return restClient.get<SelfHostedSpend>('/spend');
  };

  getSubscription = async () => {
    return restClient.get<SelfHostedSubscription>('/subscription');
  };

  getTopUp = async () => {
    return restClient.get<SelfHostedTopUp>('/top-up');
  };
}

export const businessService = new BusinessService();
