import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useSocialConnect } from './useSocialConnect';

const getStatusMock = vi.hoisted(() => vi.fn());
const getAuthorizeUrlMock = vi.hoisted(() => vi.fn());
const revokeMock = vi.hoisted(() => vi.fn());
const scanClaimableResourcesMock = vi.hoisted(() => vi.fn());

vi.mock('@/services/marketAuth', () => ({
  marketAuthService: {
    scanClaimableResources: scanClaimableResourcesMock,
  },
}));

vi.mock('@/services/marketConnect', () => ({
  marketConnectService: {
    getAuthorizeUrl: getAuthorizeUrlMock,
    getStatus: getStatusMock,
    revoke: revokeMock,
  },
}));

describe('useSocialConnect', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    scanClaimableResourcesMock.mockResolvedValue({ plugins: [], skills: [] });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('should keep polling after callback notification until the profile becomes available', async () => {
    const onConnectSuccess = vi.fn();

    getStatusMock.mockResolvedValueOnce({ connected: false }).mockResolvedValueOnce({
      connected: true,
      connection: { providerUsername: 'octocat' },
    });

    const { result } = renderHook(() =>
      useSocialConnect({
        onConnectSuccess,
        provider: 'github',
      }),
    );

    await act(async () => {
      const event = new MessageEvent('message', {
        data: {
          provider: 'github',
          type: 'SOCIAL_PROFILE_AUTH_CALLBACK',
        },
      });

      Object.defineProperty(event, 'origin', {
        configurable: true,
        value: window.location.origin,
      });

      window.dispatchEvent(event);
      await Promise.resolve();
    });

    expect(getStatusMock).toHaveBeenCalledTimes(1);
    expect(result.current.isConnecting).toBe(true);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
      await Promise.resolve();
    });

    expect(onConnectSuccess).toHaveBeenCalledWith({
      id: 'github',
      provider: 'github',
      username: 'octocat',
    });
    expect(getStatusMock).toHaveBeenCalledTimes(2);
    expect(scanClaimableResourcesMock).toHaveBeenCalledTimes(1);
    expect(result.current.isConnected).toBe(true);
    expect(result.current.isConnecting).toBe(false);
  });

  it('should stop waiting and expose the callback error without polling', async () => {
    const { result } = renderHook(() =>
      useSocialConnect({
        provider: 'github',
      }),
    );

    await act(async () => {
      const event = new MessageEvent('message', {
        data: {
          error: 'Access denied',
          provider: 'github',
          type: 'SOCIAL_PROFILE_AUTH_ERROR',
        },
      });

      Object.defineProperty(event, 'origin', {
        configurable: true,
        value: window.location.origin,
      });

      window.dispatchEvent(event);
      await Promise.resolve();
    });

    expect(result.current.error).toBe('Access denied');
    expect(getStatusMock).not.toHaveBeenCalled();
  });
});
