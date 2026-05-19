import { restClient } from '@/libs/rest';

export interface EnterpriseAiManagedSettings {
  model: boolean;
  provider: boolean;
  skills: boolean;
}

interface RestPolicyTarget {
  target_id: string;
  target_type: EnterpriseAiPolicyTarget['targetType'];
}

interface RestEnterpriseAiPolicy {
  created_at?: string;
  created_by?: string | null;
  description?: string | null;
  enabled: boolean;
  id: string;
  managed_settings: EnterpriseAiManagedSettings;
  model_config: Record<string, unknown>;
  name: string;
  organization_id?: string | null;
  priority: number;
  provider_config: Record<string, unknown>;
  restrictions: Record<string, unknown>;
  skill_config: Record<string, unknown>;
  targets: RestPolicyTarget[];
  updated_at?: string;
  updated_by?: string | null;
}

interface RestEffectiveEnterpriseAiPolicy {
  default_agent: Record<string, unknown>;
  managed_settings: EnterpriseAiManagedSettings;
  models: Record<string, unknown>;
  providers: Record<string, unknown>;
  restrictions: Record<string, unknown>;
  skills: Record<string, unknown>;
  source_policy_ids: string[];
}

export interface EnterpriseAiPolicyTarget {
  targetId: string;
  targetType: 'global' | 'organization' | 'group' | 'user';
}

export interface EnterpriseAiPolicy {
  createdAt?: string;
  createdBy?: string | null;
  description?: string | null;
  enabled: boolean;
  id: string;
  managedSettings: EnterpriseAiManagedSettings;
  modelConfig: Record<string, unknown>;
  name: string;
  organizationId?: string | null;
  priority: number;
  providerConfig: Record<string, unknown>;
  restrictions: Record<string, unknown>;
  skillConfig: Record<string, unknown>;
  targets: EnterpriseAiPolicyTarget[];
  updatedAt?: string;
  updatedBy?: string | null;
}

export type EnterpriseAiPolicyInput = Omit<
  EnterpriseAiPolicy,
  'createdAt' | 'createdBy' | 'id' | 'updatedAt' | 'updatedBy'
>;

export interface EffectiveEnterpriseAiPolicy {
  defaultAgent: Record<string, unknown>;
  managedSettings: EnterpriseAiManagedSettings;
  models: Record<string, unknown>;
  providers: Record<string, unknown>;
  restrictions: Record<string, unknown>;
  skills: Record<string, unknown>;
  sourcePolicyIds: string[];
}

const toPolicyTarget = (target: RestPolicyTarget): EnterpriseAiPolicyTarget => ({
  targetId: target.target_id,
  targetType: target.target_type,
});

const toRestPolicyTarget = (target: EnterpriseAiPolicyTarget): RestPolicyTarget => ({
  target_id: target.targetId,
  target_type: target.targetType,
});

const toPolicy = (policy: RestEnterpriseAiPolicy): EnterpriseAiPolicy => ({
  createdAt: policy.created_at,
  createdBy: policy.created_by,
  description: policy.description,
  enabled: policy.enabled,
  id: policy.id,
  managedSettings: policy.managed_settings,
  modelConfig: policy.model_config,
  name: policy.name,
  organizationId: policy.organization_id,
  priority: policy.priority,
  providerConfig: policy.provider_config,
  restrictions: policy.restrictions,
  skillConfig: policy.skill_config,
  targets: policy.targets.map(toPolicyTarget),
  updatedAt: policy.updated_at,
  updatedBy: policy.updated_by,
});

const toEffectivePolicy = (
  policy: RestEffectiveEnterpriseAiPolicy,
): EffectiveEnterpriseAiPolicy => ({
  defaultAgent: policy.default_agent,
  managedSettings: policy.managed_settings,
  models: policy.models,
  providers: policy.providers,
  restrictions: policy.restrictions,
  skills: policy.skills,
  sourcePolicyIds: policy.source_policy_ids,
});

const toRestPolicyInput = (policy: EnterpriseAiPolicyInput) => ({
  description: policy.description,
  enabled: policy.enabled,
  managed_settings: policy.managedSettings,
  model_config: policy.modelConfig,
  name: policy.name,
  organization_id: policy.organizationId,
  priority: policy.priority,
  provider_config: policy.providerConfig,
  restrictions: policy.restrictions,
  skill_config: policy.skillConfig,
  targets: policy.targets.map(toRestPolicyTarget),
});

class EnterpriseAiPolicyService {
  getEffectivePolicy = async (): Promise<EffectiveEnterpriseAiPolicy> => {
    const policy = await restClient.get<RestEffectiveEnterpriseAiPolicy>(
      '/enterprise-ai-policy/effective',
    );
    return toEffectivePolicy(policy);
  };

  listPolicies = async (): Promise<EnterpriseAiPolicy[]> => {
    const policies = await restClient.get<RestEnterpriseAiPolicy[]>(
      '/admin/enterprise-ai-policies',
    );
    return policies.map(toPolicy);
  };

  createPolicy = async (policy: EnterpriseAiPolicyInput): Promise<EnterpriseAiPolicy> => {
    const created = await restClient.post<RestEnterpriseAiPolicy>('/admin/enterprise-ai-policies', {
      body: toRestPolicyInput(policy),
    });
    return toPolicy(created);
  };

  updatePolicy = async (
    policyId: string,
    policy: EnterpriseAiPolicyInput,
  ): Promise<EnterpriseAiPolicy> => {
    const updated = await restClient.put<RestEnterpriseAiPolicy>(
      `/admin/enterprise-ai-policies/${policyId}`,
      { body: toRestPolicyInput(policy) },
    );
    return toPolicy(updated);
  };

  deletePolicy = async (policyId: string) => {
    return restClient.delete(`/admin/enterprise-ai-policies/${policyId}`);
  };

  assignTarget = async (
    policyId: string,
    target: EnterpriseAiPolicyTarget,
  ): Promise<EnterpriseAiPolicy> => {
    const updated = await restClient.post<RestEnterpriseAiPolicy>(
      `/admin/enterprise-ai-policies/${policyId}/targets`,
      { body: toRestPolicyTarget(target) },
    );
    return toPolicy(updated);
  };

  removeTarget = async (
    policyId: string,
    target: EnterpriseAiPolicyTarget,
  ): Promise<EnterpriseAiPolicy> => {
    const updated = await restClient.delete<RestEnterpriseAiPolicy>(
      `/admin/enterprise-ai-policies/${policyId}/targets/${target.targetType}/${target.targetId}`,
    );
    return toPolicy(updated);
  };
}

export const enterpriseAiPolicyService = new EnterpriseAiPolicyService();
