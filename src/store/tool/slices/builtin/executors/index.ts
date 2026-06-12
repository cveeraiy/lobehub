/**
 * Builtin Tool Executor Registry
 *
 * Central registry for all builtin tool executors.
 * Executors are registered as class instances by identifier.
 */
import { localSystemExecutor } from '@lobechat/builtin-tool-local-system/executor';
import { agentBuilderExecutor } from '@lobechat/builtin-tools/agentBuilderExecutor';
import { agentManagementExecutor } from '@lobechat/builtin-tools/agentManagementExecutor';
import { calculatorExecutor } from '@lobechat/builtin-tools/calculatorExecutor';
import { cloudSandboxExecutor } from '@lobechat/builtin-tools/cloudSandboxExecutor';
import { credsExecutor } from '@lobechat/builtin-tools/credsExecutor';
import { cronExecutor } from '@lobechat/builtin-tools/cronExecutor';
import { groupAgentBuilderExecutor } from '@lobechat/builtin-tools/groupAgentBuilderExecutor';
import { groupManagementExecutor } from '@lobechat/builtin-tools/groupManagementExecutor';
import { gtdExecutor } from '@lobechat/builtin-tools/gtdExecutor';
import { knowledgeBaseExecutor } from '@lobechat/builtin-tools/knowledgeBaseExecutor';
import { lobeAgentExecutor } from '@lobechat/builtin-tools/lobeAgentExecutor';
import { memoryExecutor } from '@lobechat/builtin-tools/memoryExecutor';
import { taskExecutor } from '@lobechat/builtin-tools/taskExecutor';

import type { BuiltinToolContext, BuiltinToolResult, IBuiltinToolExecutor } from '../types';
import { activatorExecutor } from './lobe-activator';
import { agentDocumentsExecutor } from './lobe-agent-documents';
import { agentMarketplaceExecutor } from './lobe-agent-marketplace';
import { messageExecutor } from './lobe-message';
import { notebookExecutor } from './lobe-notebook';
import { pageAgentExecutor } from './lobe-page-agent';
import { skillStoreExecutor } from './lobe-skill-store';
import { skillsExecutor } from './lobe-skills';
import { topicReferenceExecutor } from './lobe-topic-reference';
import { userInteractionExecutor } from './lobe-user-interaction';
import { webBrowsing } from './lobe-web-browsing';
import { webOnboardingExecutor } from './lobe-web-onboarding';

// ==================== Import and register all executors ====================

/**
 * Registry structure: Map<identifier, executor instance>
 */
const executorRegistry = new Map<string, IBuiltinToolExecutor>();

/**
 * Get a builtin tool executor by identifier
 *
 * @param identifier - The tool identifier
 * @returns The executor instance or undefined if not found
 */
export const getExecutor = (identifier: string): IBuiltinToolExecutor | undefined => {
  return executorRegistry.get(identifier);
};

/**
 * Check if an executor exists for the given identifier and apiName
 *
 * @param identifier - The tool identifier
 * @param apiName - The API name
 * @returns Whether the executor exists and supports the API
 */
export const hasExecutor = (identifier: string, apiName: string): boolean => {
  const executor = executorRegistry.get(identifier);
  return executor?.hasApi(apiName) ?? false;
};

/**
 * Get all registered identifiers
 *
 * @returns Array of registered identifiers
 */
export const getRegisteredIdentifiers = (): string[] => {
  return Array.from(executorRegistry.keys());
};

/**
 * Get all API names for a given identifier
 *
 * @param identifier - The tool identifier
 * @returns Array of API names or empty array if identifier not found
 */
export const getApiNamesForIdentifier = (identifier: string): string[] => {
  const executor = executorRegistry.get(identifier);
  return executor?.getApiNames() ?? [];
};

/**
 * Invoke a builtin tool executor
 *
 * @param identifier - The tool identifier
 * @param apiName - The API name
 * @param params - The parameters
 * @param ctx - The execution context
 * @returns The execution result
 */
export const invokeExecutor = async (
  identifier: string,
  apiName: string,
  params: any,
  ctx: BuiltinToolContext,
): Promise<BuiltinToolResult> => {
  const executor = executorRegistry.get(identifier);

  if (!executor) {
    return {
      error: {
        message: `Executor not found: ${identifier}`,
        type: 'ExecutorNotFound',
      },
      success: false,
    };
  }

  if (!executor.hasApi(apiName)) {
    return {
      error: {
        message: `API not found: ${identifier}/${apiName}`,
        type: 'ApiNotFound',
      },
      success: false,
    };
  }

  return executor.invoke(apiName, params, ctx);
};

/**
 * Register builtin tool executor instances
 *
 * @param executors - Array of executor instances to register
 */
const registerExecutors = (executors: IBuiltinToolExecutor[]): void => {
  for (const executor of executors) {
    executorRegistry.set(executor.identifier, executor);
  }
};

// Register all executor instances
registerExecutors([
  agentBuilderExecutor,
  agentDocumentsExecutor,
  agentManagementExecutor,
  agentMarketplaceExecutor,
  calculatorExecutor,
  cloudSandboxExecutor,
  credsExecutor,
  cronExecutor,
  groupAgentBuilderExecutor,
  groupManagementExecutor,
  gtdExecutor,
  knowledgeBaseExecutor,
  localSystemExecutor,
  memoryExecutor,
  messageExecutor,
  notebookExecutor,
  pageAgentExecutor,
  skillStoreExecutor,
  skillsExecutor,
  taskExecutor,
  activatorExecutor,
  topicReferenceExecutor,
  userInteractionExecutor,
  lobeAgentExecutor,
  webOnboardingExecutor,
  webBrowsing,
]);
