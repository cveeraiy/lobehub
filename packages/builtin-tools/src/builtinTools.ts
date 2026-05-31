import { LocalSystemManifest } from '@lobechat/builtin-tool-local-system';
import { PageAgentManifest } from '@lobechat/builtin-tool-page-agent';
import { isDesktop, RECOMMENDED_SKILLS, RecommendedSkillType } from '@lobechat/const';
import { type LobeBuiltinTool } from '@lobechat/types';

import { LobeActivatorManifest } from './activator';
import { AgentBuilderManifest } from './agentBuilder';
import { AgentDocumentsManifest } from './agentDocuments';
import { AgentManagementManifest } from './agentManagement';
import { AgentMarketplaceManifest } from './agentMarketplace';
import { BriefManifest } from './brief';
import { CalculatorManifest } from './calculator';
import { CloudSandboxManifest } from './cloudSandbox';
import { CredsManifest } from './creds';
import { CronManifest } from './cron';
import { GroupAgentBuilderManifest } from './groupAgentBuilder';
import { GroupManagementManifest } from './groupManagement';
import { GTDManifest } from './gtd';
import { KnowledgeBaseManifest } from './knowledgeBase';
import { LobeAgentManifest } from './lobeAgent';
import { MemoryManifest } from './memory';
import { MessageManifest } from './message';
import { NotebookManifest } from './notebook';
import { RemoteDeviceManifest } from './remoteDevice';
import { SkillsManifest } from './skills';
import { SkillStoreManifest } from './skillStore';
import { TaskManifest } from './task';
import { TopicReferenceManifest } from './topicReference';
import { UserInteractionManifest } from './userInteraction';
import { WebBrowsingManifest } from './webBrowsing';
import { WebOnboardingManifest } from './webOnboarding';

export const defaultToolIds = [
  LobeActivatorManifest.identifier,
  SkillsManifest.identifier,
  SkillStoreManifest.identifier,
  WebBrowsingManifest.identifier,
  KnowledgeBaseManifest.identifier,
  MemoryManifest.identifier,
  LocalSystemManifest.identifier,
  CloudSandboxManifest.identifier,
  TopicReferenceManifest.identifier,
  AgentDocumentsManifest.identifier,
  GTDManifest.identifier,
  TaskManifest.identifier,
  LobeAgentManifest.identifier,
];

export const alwaysOnToolIds = [
  LobeActivatorManifest.identifier,
  SkillsManifest.identifier,
  SkillStoreManifest.identifier,
];

export const manualModeExcludeToolIds = [
  LobeActivatorManifest.identifier,
  SkillStoreManifest.identifier,
];

export const runtimeManagedToolIds = [
  CloudSandboxManifest.identifier,
  KnowledgeBaseManifest.identifier,
  LocalSystemManifest.identifier,
  MemoryManifest.identifier,
  RemoteDeviceManifest.identifier,
  LobeAgentManifest.identifier,
  WebBrowsingManifest.identifier,
];

export const builtinTools: LobeBuiltinTool[] = [
  {
    discoverable: false,
    hidden: true,
    identifier: LobeActivatorManifest.identifier,
    manifest: LobeActivatorManifest,
    type: 'builtin',
  },
  {
    discoverable: false,
    hidden: true,
    identifier: SkillsManifest.identifier,
    manifest: SkillsManifest,
    type: 'builtin',
  },
  {
    hidden: true,
    identifier: SkillStoreManifest.identifier,
    manifest: SkillStoreManifest,
    type: 'builtin',
  },
  {
    discoverable: isDesktop,
    hidden: true,
    identifier: LocalSystemManifest.identifier,
    manifest: LocalSystemManifest,
    type: 'builtin',
  },
  {
    hidden: true,
    identifier: MemoryManifest.identifier,
    manifest: MemoryManifest,
    type: 'builtin',
  },
  {
    hidden: true,
    identifier: WebBrowsingManifest.identifier,
    manifest: WebBrowsingManifest,
    type: 'builtin',
  },
  {
    hidden: true,
    identifier: CloudSandboxManifest.identifier,
    manifest: CloudSandboxManifest,
    type: 'builtin',
  },
  {
    identifier: AgentDocumentsManifest.identifier,
    manifest: AgentDocumentsManifest,
    type: 'builtin',
  },
  { identifier: CredsManifest.identifier, manifest: CredsManifest, type: 'builtin' },
  { identifier: CronManifest.identifier, manifest: CronManifest, type: 'builtin' },
  {
    hidden: true,
    identifier: KnowledgeBaseManifest.identifier,
    manifest: KnowledgeBaseManifest,
    type: 'builtin',
  },
  {
    discoverable: false,
    hidden: true,
    identifier: PageAgentManifest.identifier,
    manifest: PageAgentManifest,
    type: 'builtin',
  },
  {
    discoverable: false,
    hidden: true,
    identifier: AgentBuilderManifest.identifier,
    manifest: AgentBuilderManifest,
    type: 'builtin',
  },
  {
    discoverable: false,
    hidden: true,
    identifier: GroupAgentBuilderManifest.identifier,
    manifest: GroupAgentBuilderManifest,
    type: 'builtin',
  },
  {
    discoverable: false,
    hidden: true,
    identifier: GroupManagementManifest.identifier,
    manifest: GroupManagementManifest,
    type: 'builtin',
  },
  {
    hidden: true,
    identifier: AgentManagementManifest.identifier,
    manifest: AgentManagementManifest,
    type: 'builtin',
  },
  { identifier: GTDManifest.identifier, manifest: GTDManifest, type: 'builtin' },
  { identifier: CalculatorManifest.identifier, manifest: CalculatorManifest, type: 'builtin' },
  { identifier: MessageManifest.identifier, manifest: MessageManifest, type: 'builtin' },
  {
    hidden: true,
    identifier: RemoteDeviceManifest.identifier,
    manifest: RemoteDeviceManifest,
    type: 'builtin',
  },
  {
    discoverable: false,
    hidden: true,
    identifier: TopicReferenceManifest.identifier,
    manifest: TopicReferenceManifest,
    type: 'builtin',
  },
  {
    discoverable: false,
    hidden: true,
    identifier: WebOnboardingManifest.identifier,
    manifest: WebOnboardingManifest,
    type: 'builtin',
  },
  {
    discoverable: false,
    hidden: true,
    identifier: UserInteractionManifest.identifier,
    manifest: UserInteractionManifest,
    type: 'builtin',
  },
  {
    discoverable: false,
    hidden: true,
    identifier: AgentMarketplaceManifest.identifier,
    manifest: AgentMarketplaceManifest,
    type: 'builtin',
  },
  {
    discoverable: false,
    hidden: true,
    identifier: TaskManifest.identifier,
    manifest: TaskManifest,
    type: 'builtin',
  },
  {
    discoverable: false,
    hidden: true,
    identifier: BriefManifest.identifier,
    manifest: BriefManifest,
    type: 'builtin',
  },
  {
    hidden: true,
    identifier: LobeAgentManifest.identifier,
    manifest: LobeAgentManifest,
    type: 'builtin',
  },
  { identifier: NotebookManifest.identifier, manifest: NotebookManifest, type: 'builtin' },
];

const recommendedBuiltinIds = new Set(
  RECOMMENDED_SKILLS.filter((s) => s.type === RecommendedSkillType.Builtin).map((s) => s.id),
);

export const defaultUninstalledBuiltinTools = builtinTools
  .filter((t) => !t.hidden && !recommendedBuiltinIds.has(t.identifier))
  .map((t) => t.identifier);
