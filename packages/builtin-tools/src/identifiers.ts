import { LocalSystemManifest } from '@lobechat/builtin-tool-local-system';
import { PageAgentManifest } from '@lobechat/builtin-tool-page-agent';

import { LobeActivatorManifest } from './activator';
import { AgentBuilderManifest } from './agentBuilder';
import { AgentDocumentsManifest } from './agentDocuments';
import { AgentManagementManifest } from './agentManagement';
import { AgentMarketplaceManifest } from './agentMarketplace';
import { CalculatorManifest } from './calculator';
import { CloudSandboxManifest } from './cloudSandbox';
import { CredsManifest } from './creds';
import { GroupAgentBuilderManifest } from './groupAgentBuilder';
import { GroupManagementManifest } from './groupManagement';
import { GTDManifest } from './gtd';
import { KnowledgeBaseManifest } from './knowledgeBase';
import { LobeAgentManifest } from './lobeAgent';
import { MemoryManifest } from './memory';
import { NotebookManifest } from './notebook';
import { SkillsManifest } from './skills';
import { SkillStoreManifest } from './skillStore';
import { TopicReferenceManifest } from './topicReference';
import { UserInteractionManifest } from './userInteraction';
import { WebBrowsingManifest } from './webBrowsing';
import { WebOnboardingManifest } from './webOnboarding';

export const builtinToolIdentifiers: string[] = [
  AgentBuilderManifest.identifier,
  AgentDocumentsManifest.identifier,
  AgentManagementManifest.identifier,
  AgentMarketplaceManifest.identifier,
  CalculatorManifest.identifier,
  CloudSandboxManifest.identifier,
  CredsManifest.identifier,
  GroupAgentBuilderManifest.identifier,
  GroupManagementManifest.identifier,
  GTDManifest.identifier,
  KnowledgeBaseManifest.identifier,
  LocalSystemManifest.identifier,
  MemoryManifest.identifier,
  NotebookManifest.identifier,
  PageAgentManifest.identifier,
  SkillsManifest.identifier,
  SkillStoreManifest.identifier,
  TopicReferenceManifest.identifier,
  LobeActivatorManifest.identifier,
  WebBrowsingManifest.identifier,
  UserInteractionManifest.identifier,
  LobeAgentManifest.identifier,
  WebOnboardingManifest.identifier,
];
