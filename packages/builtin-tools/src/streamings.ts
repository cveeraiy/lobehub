import {
  AgentBuilderManifest,
  AgentBuilderStreamings,
} from '@lobechat/builtin-tool-agent-builder/client';
import {
  ClaudeCodeIdentifier,
  ClaudeCodeStreamings,
} from '@lobechat/builtin-tool-claude-code/client';
import {
  GroupAgentBuilderManifest,
  GroupAgentBuilderStreamings,
} from '@lobechat/builtin-tool-group-agent-builder/client';
import {
  LocalSystemManifest,
  LocalSystemStreamings,
} from '@lobechat/builtin-tool-local-system/client';
import {
  AgentManagementManifest,
  AgentManagementStreamings,
} from '@lobechat/builtin-tools/agentManagementClient';
import {
  CloudSandboxManifest,
  CloudSandboxStreamings,
} from '@lobechat/builtin-tools/cloudSandboxClient';
import {
  GroupManagementManifest,
  GroupManagementStreamings,
} from '@lobechat/builtin-tools/groupManagementClient';
import { GTDManifest, GTDStreamings } from '@lobechat/builtin-tools/gtdClient';
import { MessageManifest, MessageStreamings } from '@lobechat/builtin-tools/messageClient';
import { type BuiltinStreaming } from '@lobechat/types';

import { AgentDocumentsManifest, AgentDocumentsStreamings } from './agentDocuments/client';
import { MemoryManifest, MemoryStreamings } from './memory/client';
import { NotebookManifest, NotebookStreamings } from './notebook/client';

/**
 * Builtin tools streaming renderer registry
 * Organized by toolset (identifier) -> API name
 *
 * Streaming components are used to render tool calls while they are
 * still executing, allowing real-time feedback to users.
 * The component should fetch streaming content from store internally.
 */
const BuiltinToolStreamings: Record<string, Record<string, BuiltinStreaming>> = {
  [AgentBuilderManifest.identifier]: AgentBuilderStreamings as Record<string, BuiltinStreaming>,
  [AgentDocumentsManifest.identifier]: AgentDocumentsStreamings as Record<string, BuiltinStreaming>,
  [AgentManagementManifest.identifier]: AgentManagementStreamings as Record<
    string,
    BuiltinStreaming
  >,
  [ClaudeCodeIdentifier]: ClaudeCodeStreamings as Record<string, BuiltinStreaming>,
  [CloudSandboxManifest.identifier]: CloudSandboxStreamings as Record<string, BuiltinStreaming>,
  [GroupAgentBuilderManifest.identifier]: GroupAgentBuilderStreamings as Record<
    string,
    BuiltinStreaming
  >,
  [GroupManagementManifest.identifier]: GroupManagementStreamings as Record<
    string,
    BuiltinStreaming
  >,
  [GTDManifest.identifier]: GTDStreamings as Record<string, BuiltinStreaming>,
  [LocalSystemManifest.identifier]: LocalSystemStreamings as Record<string, BuiltinStreaming>,
  [MemoryManifest.identifier]: MemoryStreamings as Record<string, BuiltinStreaming>,
  [MessageManifest.identifier]: MessageStreamings as Record<string, BuiltinStreaming>,
  [NotebookManifest.identifier]: NotebookStreamings as Record<string, BuiltinStreaming>,
};

export interface BuiltinStreamingRegistryEntry {
  apiName: string;
  identifier: string;
  streaming: BuiltinStreaming;
}

export const listBuiltinStreamingEntries = (): BuiltinStreamingRegistryEntry[] =>
  Object.entries(BuiltinToolStreamings).flatMap(([identifier, toolset]) =>
    Object.entries(toolset)
      .filter((entry): entry is [string, BuiltinStreaming] => !!entry[1])
      .map(([apiName, streaming]) => ({
        apiName,
        identifier,
        streaming,
      })),
  );

/**
 * Get builtin streaming component for a specific API
 * @param identifier - Tool identifier (e.g., 'lobe-code-interpreter')
 * @param apiName - API name (e.g., 'executeCode')
 */
export const getBuiltinStreaming = (
  identifier?: string,
  apiName?: string,
): BuiltinStreaming | undefined => {
  if (!identifier || !apiName) return undefined;

  const toolset = BuiltinToolStreamings[identifier];
  if (!toolset) return undefined;

  return toolset[apiName];
};
