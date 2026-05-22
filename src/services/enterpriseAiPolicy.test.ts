import { beforeEach, describe, expect, it, vi } from 'vitest';

import { enterpriseAiPolicyService } from './enterpriseAiPolicy';

const mockRestDelete = vi.hoisted(() => vi.fn());
const mockRestGet = vi.hoisted(() => vi.fn());
const mockRestPost = vi.hoisted(() => vi.fn());
const mockRestPut = vi.hoisted(() => vi.fn());

vi.mock('@/libs/rest', () => ({
  restClient: {
    delete: mockRestDelete,
    get: mockRestGet,
    post: mockRestPost,
    put: mockRestPut,
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('EnterpriseAiPolicyService REST', () => {
  it('loads and normalizes the effective policy', async () => {
    mockRestGet.mockResolvedValueOnce({
      default_agent: { model: 'gpt-4o', provider: 'openai' },
      managed_settings: { model: true, provider: true, skills: false },
      models: { allow: ['gpt-4o'] },
      providers: { openai: { enabled: true } },
      restrictions: {},
      skills: {},
      source_policy_ids: ['policy-1'],
    });

    const result = await enterpriseAiPolicyService.getEffectivePolicy();

    expect(mockRestGet).toHaveBeenCalledWith('/enterprise-ai-policy/effective');
    expect(result).toEqual({
      defaultAgent: { model: 'gpt-4o', provider: 'openai' },
      managedSettings: { model: true, provider: true, skills: false },
      models: { allow: ['gpt-4o'] },
      providers: { openai: { enabled: true } },
      restrictions: {},
      skills: {},
      sourcePolicyIds: ['policy-1'],
    });
  });

  it('creates policies with snake_case REST fields', async () => {
    mockRestPost.mockResolvedValueOnce({
      enabled: true,
      id: 'policy-1',
      managed_settings: { model: true, provider: true, skills: true },
      model_config: {},
      name: 'Default',
      priority: 10,
      provider_config: {},
      restrictions: {},
      skill_config: {},
      targets: [{ target_id: 'org-1', target_type: 'organization' }],
    });

    const result = await enterpriseAiPolicyService.createPolicy({
      enabled: true,
      managedSettings: { model: true, provider: true, skills: true },
      modelConfig: {},
      name: 'Default',
      priority: 10,
      providerConfig: {},
      restrictions: {},
      skillConfig: {},
      targets: [{ targetId: 'org-1', targetType: 'organization' }],
    });

    expect(mockRestPost).toHaveBeenCalledWith('/admin/enterprise-ai-policies', {
      body: {
        description: undefined,
        enabled: true,
        managed_settings: { model: true, provider: true, skills: true },
        model_config: {},
        name: 'Default',
        organization_id: undefined,
        priority: 10,
        provider_config: {},
        restrictions: {},
        skill_config: {},
        targets: [{ target_id: 'org-1', target_type: 'organization' }],
      },
    });
    expect(result.targets).toEqual([{ targetId: 'org-1', targetType: 'organization' }]);
  });

  it('loads configured group targets', async () => {
    mockRestGet.mockResolvedValueOnce([{ id: 'engineering' }, { id: 'finance' }]);

    const result = await enterpriseAiPolicyService.listGroupTargets();

    expect(mockRestGet).toHaveBeenCalledWith('/admin/enterprise-ai-policies/group-targets');
    expect(result).toEqual(['engineering', 'finance']);
  });
});
