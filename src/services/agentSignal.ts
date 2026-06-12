import type {
  AgentSignalSourceEventInput,
  AgentSignalSourceType,
} from '@lobechat/agent-signal/source';

import { restClient } from '@/libs/rest';

type ClientGatewaySourceType = Extract<AgentSignalSourceType, `client.${string}`>;

type ClientGatewaySourceEventInput<TSourceType extends ClientGatewaySourceType> =
  AgentSignalSourceEventInput<TSourceType>;

class AgentSignalService {
  emitSourceEvent = async (payload: ClientGatewaySourceEventInput<ClientGatewaySourceType>) => {
    return restClient.post('/agent-signal/emit', { body: payload });
  };

  emitClientGatewaySourceEvent = async <TSourceType extends ClientGatewaySourceType>(
    payload: ClientGatewaySourceEventInput<TSourceType>,
  ) => {
    return this.emitSourceEvent({
      ...payload,
      timestamp: payload.timestamp ?? Date.now(),
    });
  };
}

export const agentSignalService = new AgentSignalService();
