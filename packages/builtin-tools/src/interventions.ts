import {
  AgentBuilderInterventions,
  AgentBuilderManifest,
} from '@lobechat/builtin-tool-agent-builder/client';
import {
  LocalSystemIdentifier,
  LocalSystemInterventions,
} from '@lobechat/builtin-tool-local-system/client';
import {
  UserInteractionIdentifier,
  UserInteractionInterventions,
} from '@lobechat/builtin-tool-user-interaction/client';
import { CloudSandboxManifest } from '@lobechat/builtin-tools';
import {
  AgentMarketplaceInterventions,
  AgentMarketplaceManifest,
} from '@lobechat/builtin-tools/agentMarketplaceClient';
import { CloudSandboxInterventions } from '@lobechat/builtin-tools/cloudSandboxClient';
import {
  GroupManagementInterventions,
  GroupManagementManifest,
} from '@lobechat/builtin-tools/groupManagementClient';
import { GTDInterventions, GTDManifest } from '@lobechat/builtin-tools/gtdClient';
import { MessageInterventions, MessageManifest } from '@lobechat/builtin-tools/messageClient';
import { type BuiltinIntervention } from '@lobechat/types';

import { MemoryInterventions, MemoryManifest } from './memory/client';
import { NotebookInterventions, NotebookManifest } from './notebook/client';
import { WebOnboardingInterventions, WebOnboardingManifest } from './webOnboarding/client';

/**
 * Builtin tools interventions registry
 * Organized by toolset (identifier) -> API name
 * Only register APIs that have custom intervention UI
 */
export const BuiltinToolInterventions: Record<string, Record<string, any>> = {
  [AgentBuilderManifest.identifier]: AgentBuilderInterventions,
  [AgentMarketplaceManifest.identifier]: AgentMarketplaceInterventions,
  [CloudSandboxManifest.identifier]: CloudSandboxInterventions,
  [GroupManagementManifest.identifier]: GroupManagementInterventions,
  [GTDManifest.identifier]: GTDInterventions,
  [LocalSystemIdentifier]: LocalSystemInterventions,
  [MemoryManifest.identifier]: MemoryInterventions,
  [MessageManifest.identifier]: MessageInterventions,
  [NotebookManifest.identifier]: NotebookInterventions,
  [UserInteractionIdentifier]: UserInteractionInterventions,
  [WebOnboardingManifest.identifier]: WebOnboardingInterventions,
};

export interface BuiltinInterventionRegistryEntry {
  apiName: string;
  identifier: string;
  intervention: BuiltinIntervention;
}

export const listBuiltinInterventionEntries = (): BuiltinInterventionRegistryEntry[] =>
  Object.entries(BuiltinToolInterventions).flatMap(([identifier, toolset]) =>
    Object.entries(toolset)
      .filter((entry): entry is [string, BuiltinIntervention] => !!entry[1])
      .map(([apiName, intervention]) => ({
        apiName,
        identifier,
        intervention,
      })),
  );

/**
 * Get builtin intervention component for a specific API
 * @param identifier - Tool identifier (e.g., 'lobe-local-system')
 * @param apiName - API name (e.g., 'runCommand')
 */
export const getBuiltinIntervention = (
  identifier?: string,
  apiName?: string,
): BuiltinIntervention | undefined => {
  if (!identifier || !apiName) return undefined;

  const toolset = BuiltinToolInterventions[identifier];
  if (!toolset) return undefined;

  return toolset[apiName];
};
