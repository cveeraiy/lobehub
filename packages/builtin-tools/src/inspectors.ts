import {
  ClaudeCodeIdentifier,
  ClaudeCodeInspectors,
} from '@lobechat/builtin-tool-claude-code/client';
import {
  LocalSystemInspectors,
  LocalSystemManifest,
} from '@lobechat/builtin-tool-local-system/client';
import { PageAgentInspectors, PageAgentManifest } from '@lobechat/builtin-tool-page-agent/client';
import { createRunCommandInspector } from '@lobechat/shared-tool-ui/inspectors';
import { type BuiltinInspector } from '@lobechat/types';

import { LobeActivatorInspectors, LobeActivatorManifest } from './activator/client';
import { AgentBuilderInspectors, AgentBuilderManifest } from './agentBuilder/client';
import { AgentManagementInspectors, AgentManagementManifest } from './agentManagement/client';
import { CloudSandboxIdentifier, CloudSandboxInspectors } from './cloudSandbox/client';
import { CodexInspectors } from './codex';
import { GroupAgentBuilderInspectors, GroupAgentBuilderManifest } from './groupAgentBuilder/client';
import { GroupManagementInspectors, GroupManagementManifest } from './groupManagement/client';
import { GTDInspectors, GTDManifest } from './gtd/client';
import { KnowledgeBaseInspectors, KnowledgeBaseManifest } from './knowledgeBase/client';
import { MemoryInspectors, MemoryManifest } from './memory/client';
import { MessageInspectors, MessageManifest } from './message/client';
import { NotebookInspectors, NotebookManifest } from './notebook/client';
import { SkillsInspectors, SkillsManifest } from './skills/client';
import { SkillStoreInspectors, SkillStoreManifest } from './skillStore/client';
import { WebBrowsingInspectors, WebBrowsingManifest } from './webBrowsing/client';

/**
 * Builtin tools inspector registry
 * Organized by toolset (identifier) -> API name
 *
 * Inspector components are used to customize the title/header area
 * of tool calls in the conversation UI.
 */
const BuiltinToolInspectors: Record<string, Record<string, BuiltinInspector>> = {
  [AgentBuilderManifest.identifier]: AgentBuilderInspectors as Record<string, BuiltinInspector>,
  [AgentManagementManifest.identifier]: AgentManagementInspectors as Record<
    string,
    BuiltinInspector
  >,
  [ClaudeCodeIdentifier]: ClaudeCodeInspectors as Record<string, BuiltinInspector>,
  [CloudSandboxIdentifier]: CloudSandboxInspectors as Record<string, BuiltinInspector>,
  [GroupAgentBuilderManifest.identifier]: GroupAgentBuilderInspectors as Record<
    string,
    BuiltinInspector
  >,
  [GroupManagementManifest.identifier]: GroupManagementInspectors as Record<
    string,
    BuiltinInspector
  >,
  [GTDManifest.identifier]: GTDInspectors as Record<string, BuiltinInspector>,
  [KnowledgeBaseManifest.identifier]: KnowledgeBaseInspectors as Record<string, BuiltinInspector>,
  [LocalSystemManifest.identifier]: LocalSystemInspectors as Record<string, BuiltinInspector>,
  [MemoryManifest.identifier]: MemoryInspectors as Record<string, BuiltinInspector>,
  [MessageManifest.identifier]: MessageInspectors as Record<string, BuiltinInspector>,
  [NotebookManifest.identifier]: NotebookInspectors as Record<string, BuiltinInspector>,
  [PageAgentManifest.identifier]: PageAgentInspectors as Record<string, BuiltinInspector>,
  [LobeActivatorManifest.identifier]: LobeActivatorInspectors as Record<string, BuiltinInspector>,
  // @deprecated backward compat: old messages stored 'lobe-tools' as identifier
  ['lobe-tools']: LobeActivatorInspectors as Record<string, BuiltinInspector>,
  [SkillStoreManifest.identifier]: SkillStoreInspectors as Record<string, BuiltinInspector>,
  [SkillsManifest.identifier]: SkillsInspectors as Record<string, BuiltinInspector>,
  [WebBrowsingManifest.identifier]: WebBrowsingInspectors as Record<string, BuiltinInspector>,
  codex: {
    ...CodexInspectors,
    command_execution: createRunCommandInspector('Run') as BuiltinInspector,
  },
};

export interface BuiltinInspectorRegistryEntry {
  apiName: string;
  identifier: string;
  inspector: BuiltinInspector;
}

export const listBuiltinInspectorEntries = (): BuiltinInspectorRegistryEntry[] =>
  Object.entries(BuiltinToolInspectors).flatMap(([identifier, toolset]) =>
    Object.entries(toolset)
      .filter((entry): entry is [string, BuiltinInspector] => !!entry[1])
      .map(([apiName, inspector]) => ({
        apiName,
        identifier,
        inspector,
      })),
  );

/**
 * Get builtin inspector component for a specific API
 * @param identifier - Tool identifier (e.g., 'lobe-code-interpreter')
 * @param apiName - API name (e.g., 'executeCode')
 */
export const getBuiltinInspector = (
  identifier?: string,
  apiName?: string,
): BuiltinInspector | undefined => {
  if (!identifier || !apiName) return undefined;

  const toolset = BuiltinToolInspectors[identifier];
  if (!toolset) return undefined;

  return toolset[apiName];
};
