import type { PartialDeep } from 'type-fest';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { UserSettings } from '@/types/user/settings';

import { userService } from './index.rest';

const mockRestPut = vi.hoisted(() => vi.fn());

vi.mock('@/libs/rest', () => ({
  restClient: {
    delete: vi.fn(),
    get: vi.fn(),
    patch: vi.fn(),
    post: vi.fn(),
    put: mockRestPut,
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('UserService REST', () => {
  describe('updateUserSettings', () => {
    it('maps frontend setting keys to the Python REST body shape', async () => {
      const signal = new AbortController().signal;
      mockRestPut.mockResolvedValueOnce({ ok: true });
      const settings = {
        defaultAgent: { config: { model: 'gpt-4o' } },
        general: { language: 'en-US' },
        hotkey: { search: 'mod+k' },
        image: { autoGenerate: true },
        keyVaults: { openai: { apiKey: 'secret' } },
        languageModel: { openai: { enabled: true } },
        market: { accessToken: 'market-token' },
        memory: { enabled: true },
        notification: { enabled: false },
        systemAgent: { translation: { model: 'gpt-4o-mini' } },
        tool: { uninstalledBuiltinTools: [] },
        tts: { sttAutoStop: true },
      } as unknown as PartialDeep<UserSettings>;

      await userService.updateUserSettings(settings, signal);

      expect(mockRestPut).toHaveBeenCalledWith('/user/settings', {
        body: {
          default_agent: { config: { model: 'gpt-4o' } },
          general: { language: 'en-US' },
          hotkey: { search: 'mod+k' },
          image: { autoGenerate: true },
          key_vaults: { openai: { apiKey: 'secret' } },
          language_model: { openai: { enabled: true } },
          market: { accessToken: 'market-token' },
          memory: { enabled: true },
          notification: { enabled: false },
          system_agent: { translation: { model: 'gpt-4o-mini' } },
          tool: { uninstalledBuiltinTools: [] },
          tts: { sttAutoStop: true },
        },
        signal,
      });
    });
  });
});
