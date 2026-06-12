import { renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { EnabledProviderWithModels } from '@/types/aiProvider';

import { useBuildListItems } from './useBuildListItems';

const enabledList: EnabledProviderWithModels[] = [
  {
    children: [
      { abilities: {}, displayName: 'Claude Sonnet', id: 'claude-sonnet' },
      { abilities: {}, displayName: 'Claude Sonnet Duplicate', id: 'claude-sonnet' },
      { abilities: {}, displayName: 'Nova Pro', id: 'nova-pro' },
    ],
    id: 'bedrock',
    name: 'AWS Bedrock',
    source: 'builtin',
  },
];

describe('useBuildListItems', () => {
  it('deduplicates provider model children before building provider grouped items', () => {
    const { result } = renderHook(() => useBuildListItems(enabledList, 'byProvider'));

    const modelItems = result.current.filter((item) => item.type === 'provider-model-item');

    expect(modelItems).toHaveLength(2);
    expect(modelItems.map((item) => item.type === 'provider-model-item' && item.model.id)).toEqual([
      'claude-sonnet',
      'nova-pro',
    ]);
  });

  it('deduplicates provider model children before building model grouped items', () => {
    const { result } = renderHook(() => useBuildListItems(enabledList, 'byModel'));

    expect(result.current).toHaveLength(2);
    expect(result.current.map((item) => 'data' in item && item.data.model.id)).toEqual([
      'claude-sonnet',
      'nova-pro',
    ]);
  });
});
