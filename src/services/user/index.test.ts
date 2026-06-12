import type { PartialDeep } from 'type-fest';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { UserSettings } from '@/types/user/settings';

import { userService } from './index';

const mockRestPut = vi.hoisted(() => vi.fn());
const mockRestGet = vi.hoisted(() => vi.fn());
const mockRestPost = vi.hoisted(() => vi.fn());
const mockRestDelete = vi.hoisted(() => vi.fn());

vi.mock('@/libs/rest', () => ({
  restClient: {
    delete: mockRestDelete,
    get: mockRestGet,
    patch: vi.fn(),
    post: mockRestPost,
    put: mockRestPut,
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('UserService REST', () => {
  it('loads user state from the REST endpoint', async () => {
    const state = { isOnboard: true, preference: {}, settings: {}, userId: 'user-1' };
    mockRestGet.mockResolvedValueOnce(state);

    await expect(userService.getUserState()).resolves.toBe(state);

    expect(mockRestGet).toHaveBeenCalledWith('/user/state');
  });

  it('updates avatar with the REST body shape', async () => {
    mockRestPut.mockResolvedValueOnce({ ok: true });

    await userService.updateAvatar('https://example.com/avatar.png');

    expect(mockRestPut).toHaveBeenCalledWith('/user/avatar', {
      body: { avatar: 'https://example.com/avatar.png' },
    });
  });

  it('marks the user onboarded through REST', async () => {
    mockRestPost.mockResolvedValueOnce({ ok: true });

    await userService.makeUserOnboarded();

    expect(mockRestPost).toHaveBeenCalledWith('/user/onboarded');
  });

  it('resets settings through REST', async () => {
    mockRestDelete.mockResolvedValueOnce({ ok: true });

    await userService.resetUserSettings();

    expect(mockRestDelete).toHaveBeenCalledWith('/user/settings');
  });

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
