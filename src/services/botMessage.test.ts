import { beforeEach, describe, expect, it, vi } from 'vitest';

import { restClient } from '@/libs/rest';

import { botMessageService } from './botMessage';

vi.mock('@/libs/rest', () => ({
  restClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('BotMessageService', () => {
  it('calls query APIs with snake_case params', async () => {
    await botMessageService.call(
      'readMessages',
      { botId: 'bot-1', channelId: 'channel-1', limit: 20 },
      'query',
    );

    expect(restClient.get).toHaveBeenCalledWith('/bot-message/read-messages', {
      params: expect.objectContaining({
        bot_id: 'bot-1',
        channel_id: 'channel-1',
        limit: 20,
      }),
    });
  });

  it('calls mutation APIs with snake_case body', async () => {
    await botMessageService.call(
      'sendMessage',
      { botId: 'bot-1', channelId: 'channel-1', content: 'hello' },
      'mutate',
    );

    expect(restClient.post).toHaveBeenCalledWith('/bot-message/send-message', {
      body: expect.objectContaining({
        bot_id: 'bot-1',
        channel_id: 'channel-1',
        content: 'hello',
      }),
    });
  });
});
