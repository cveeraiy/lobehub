import type { BuiltinAgentRuntimeContext, BuiltinAgentRuntimeDefinition } from '@/services/agent';
import { agentService } from '@/services/agent';

type RuntimeConfig = BuiltinAgentRuntimeDefinition['runtime'];

const cache = new Map<string, RuntimeConfig>();

const stableStringify = (value: unknown): string => {
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(',')}]`;
  if (!value || typeof value !== 'object') return JSON.stringify(value);

  return `{${Object.entries(value as Record<string, unknown>)
    .filter(([, item]) => item !== undefined)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, item]) => `${JSON.stringify(key)}:${stableStringify(item)}`)
    .join(',')}}`;
};

const keyOf = (slug: string, context: BuiltinAgentRuntimeContext = {}) =>
  `${slug}:${stableStringify(context)}`;

export const getCachedBuiltinAgentRuntimeConfig = (
  slug: string,
  context: BuiltinAgentRuntimeContext = {},
): RuntimeConfig | undefined => cache.get(keyOf(slug, context));

export const getAgentRuntimeConfig = getCachedBuiltinAgentRuntimeConfig;

export const preloadBuiltinAgentRuntimeConfig = async (
  slug: string,
  context: BuiltinAgentRuntimeContext = {},
): Promise<RuntimeConfig | undefined> => {
  const cacheKey = keyOf(slug, context);
  const cached = cache.get(cacheKey);
  if (cached) return cached;

  const definition = await agentService.resolveBuiltinAgentDefinition(slug, context);
  if (!definition) return;

  cache.set(cacheKey, definition.runtime);
  return definition.runtime;
};
