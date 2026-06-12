import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { useUserStore } from '@/store/user';

import { useUserAvatar } from './useUserAvatar';

describe('useUserAvatar', () => {
  it('should return default avatar when user has no avatar', () => {
    act(() => {
      useUserStore.setState({ user: { avatar: undefined } as any });
    });

    const { result } = renderHook(() => useUserAvatar());

    expect(result.current).toBe('😀');
  });

  it('should return user avatar when available', () => {
    const mockAvatar = 'https://example.com/avatar.png';

    act(() => {
      useUserStore.setState({ user: { avatar: mockAvatar } as any });
    });

    const { result } = renderHook(() => useUserAvatar());

    expect(result.current).toBe(mockAvatar);
  });
});
