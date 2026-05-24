import {
  type AgentTemplate,
  type AgentTemplateFetcher,
  normalizeAgentTemplate,
  type RawAgentTemplate,
} from '@lobechat/builtin-tools';

import { restClient } from '@/libs/rest';

export const fetchOnboardingAgentTemplates: AgentTemplateFetcher = async () => {
  const data = await restClient.get<Record<string, RawAgentTemplate[]>>(
    '/market/agent/onboarding-full',
  );
  if (!data || typeof data !== 'object') return [];

  const templates: AgentTemplate[] = [];
  for (const [category, items] of Object.entries(data)) {
    if (!Array.isArray(items)) continue;
    for (const item of items as RawAgentTemplate[]) {
      const normalized = normalizeAgentTemplate(item, category);
      if (normalized) templates.push(normalized);
    }
  }
  return templates;
};
