import { AgentBuilderManifest } from '@lobechat/builtin-tool-agent-builder';
import { GroupAgentBuilderManifest } from '@lobechat/builtin-tool-group-agent-builder';
import { LocalSystemManifest } from '@lobechat/builtin-tool-local-system';
import { PageAgentManifest } from '@lobechat/builtin-tool-page-agent';
import { RemoteDeviceManifest } from '@lobechat/builtin-tool-remote-device';
import { UserInteractionManifest } from '@lobechat/builtin-tool-user-interaction';
import { WebBrowsingManifest } from '@lobechat/builtin-tool-web-browsing';
import { isDesktop, RECOMMENDED_SKILLS, RecommendedSkillType } from '@lobechat/const';
import { type LobeBuiltinTool } from '@lobechat/types';

import { LobeActivatorManifest } from './activator';
import { AgentDocumentsManifest } from './agentDocuments';
import { AgentManagementManifest } from './agentManagement';
import { AgentMarketplaceManifest } from './agentMarketplace';
import { BriefManifest } from './brief';
import { CalculatorManifest } from './calculator';
import { CloudSandboxManifest } from './cloudSandbox';
import { CredsManifest } from './creds';
import { CronManifest } from './cron';
import { GroupManagementManifest } from './groupManagement';
import { GTDManifest } from './gtd';
import { KnowledgeBaseManifest } from './knowledgeBase';
import { LobeAgentManifest } from './lobeAgent';
import { MemoryManifest } from './memory';
import { MessageManifest } from './message';
import { SkillsManifest } from './skills';
import { SkillStoreManifest } from './skillStore';
import { TaskManifest } from './task';
import { TopicReferenceManifest } from './topicReference';
import { WebOnboardingManifest } from './webOnboarding';

export {
  type ActivatedToolInfo,
  type ActivateToolsParams,
  type ActivateToolsState,
  type ActivateSkillParams as ActivatorActivateSkillParams,
  type ActivateSkillState as ActivatorActivateSkillState,
  ActivatorApiName,
  ActivatorExecutionRuntime,
  systemPrompt as activatorSystemPrompt,
  LobeActivatorIdentifier,
  LobeActivatorManifest,
  type ToolManifestInfo,
} from './activator';
export {
  type AgentDocumentLoadRule,
  type AgentDocumentReference,
  AgentDocumentsApiName,
  AgentDocumentsExecutionRuntime,
  AgentDocumentsIdentifier,
  AgentDocumentsManifest,
  systemPrompt as agentDocumentsSystemPrompt,
  type CopyDocumentArgs,
  type CopyDocumentState,
  type CreateDocumentArgs,
  type CreateDocumentState,
  type ListDocumentsArgs,
  type ListDocumentsState,
  type LoadRuleScope,
  type ModifyDocumentInsertOperation,
  type ModifyDocumentNodesArgs,
  type ModifyDocumentNodesState,
  type ModifyDocumentOperation,
  type ModifyDocumentRemoveOperation,
  type ModifyDocumentUpdateOperation,
  type ReadDocumentArgs,
  type ReadDocumentState,
  type RemoveDocumentArgs,
  type RemoveDocumentState,
  type RenameDocumentArgs,
  type RenameDocumentState,
  type ReplaceDocumentContentArgs,
  type ReplaceDocumentContentState,
  type UpdateLoadRuleArgs,
  type UpdateLoadRuleState,
} from './agentDocuments';
export {
  AgentManagementApiName,
  type AgentManagementApiNameType,
  AgentManagementIdentifier,
  AgentManagementManifest,
  type CallAgentParams,
  type CallAgentState,
  createCallAgentManifest,
} from './agentManagement';
export {
  AgentMarketplaceApiName,
  AgentMarketplaceExecutionRuntime,
  AgentMarketplaceIdentifier,
  AgentMarketplaceManifest,
  systemPrompt as agentMarketplaceSystemPrompt,
  type AgentTemplate,
  type AgentTemplateFetcher,
  buildAgentMarketplaceToolResult,
  fetchAgentTemplates,
  type FetchAgentTemplatesOptions,
  getTemplatesByCategories,
  type InstallMarketplaceAgentSummary,
  MARKETPLACE_CATEGORY_VALUES,
  MarketplaceCategory,
  normalizeAgentTemplate,
  type OnboardingFullResponse,
  type PickState,
  type RawAgentTemplate,
  setAgentTemplatesFetcher,
} from './agentMarketplace';
export { BriefApiName, BriefIdentifier, BriefManifest } from './brief';
export {
  type BaseParams,
  type BaseState,
  type CalculateParams,
  type CalculateState,
  CalculatorApiName,
  type CalculatorApiNameType,
  CalculatorIdentifier,
  CalculatorManifest,
  type DefintegrateParams,
  type DefintegrateState,
  type DifferentiateParams,
  type DifferentiateState,
  type EvaluateParams,
  type EvaluateState,
  type ExecuteParams,
  type ExecuteState,
  type IntegrateParams,
  type IntegrateState,
  type LimitParams,
  type LimitState,
  type SolveParams,
  type SolveState,
  type SortParams,
  type SortState,
} from './calculator';
export {
  CloudSandboxApiName,
  type CloudSandboxApiNameType,
  CloudSandboxExecutionRuntime,
  CloudSandboxIdentifier,
  CloudSandboxManifest,
  type ISandboxService,
  type SandboxCallToolResult,
  type SandboxExportFileResult,
} from './cloudSandbox';
export {
  checkCredsSatisfied,
  type CredRequirement,
  CredsApiName,
  type CredsApiNameType,
  CredsExecutionRuntime,
  CredsIdentifier,
  CredsManifest,
  systemPrompt as credsSystemPrompt,
  type CredSummary,
  type CredSummaryForContext,
  generateCredsList,
  generateKlavisServicesList,
  groupCredsByType,
  type ICredsService,
  injectCredsContext,
  type KlavisServiceSummary,
  type UserCredsContext,
} from './creds';
export {
  type CreateCronJobParams,
  type CreateCronJobState,
  CronApiName,
  type CronApiNameType,
  CronExecutionRuntime,
  CronIdentifier,
  type CronJobSummary,
  type CronJobSummaryForContext,
  CronManifest,
  type CronStats,
  systemPrompt as cronSystemPrompt,
  type DeleteCronJobParams,
  type DeleteCronJobState,
  generateCronJobsList,
  type GetCronJobParams,
  type GetCronJobState,
  type GetStatsParams,
  type GetStatsState,
  type ICronService,
  type ListCronJobsParams,
  type ListCronJobsState,
  type ResetExecutionsParams,
  type ResetExecutionsState,
  type ToggleCronJobParams,
  type ToggleCronJobState,
  type UpdateCronJobParams,
  type UpdateCronJobState,
} from './cron';
export {
  type BroadcastParams,
  type CreateWorkflowParams,
  type DelegateParams,
  type ExecuteTaskParams,
  type ExecuteTasksParams,
  GroupManagementApiName,
  type GroupManagementApiNameType,
  GroupManagementIdentifier,
  GroupManagementManifest,
  systemPrompt as groupManagementSystemPrompt,
  type InterruptParams,
  type SpeakParams,
  type SummarizeParams,
  type VoteParams,
} from './groupManagement';
export {
  GTDApiName,
  type GTDApiNameType,
  GTDExecutionRuntime,
  GTDIdentifier,
  GTDManifest,
  systemPrompt as gtdSystemPrompt,
} from './gtd';
export {
  type AddFilesArgs,
  type CreateKnowledgeBaseArgs,
  type CreateKnowledgeBaseState,
  type DeleteKnowledgeBaseArgs,
  type FileContentDetail,
  type FileDetail,
  type FileInfo,
  type GetFileDetailArgs,
  type GetFileDetailState,
  KnowledgeBaseApiName,
  type CreateDocumentArgs as KnowledgeBaseCreateDocumentArgs,
  type CreateDocumentState as KnowledgeBaseCreateDocumentState,
  type KnowledgeBaseFileInfo,
  KnowledgeBaseIdentifier,
  type KnowledgeBaseInfo,
  KnowledgeBaseManifest,
  systemPrompt as knowledgeBaseSystemPrompt,
  type ListFilesArgs,
  type ListFilesState,
  type ListKnowledgeBasesState,
  type ReadKnowledgeArgs,
  type ReadKnowledgeState,
  type RemoveFilesArgs,
  type SearchKnowledgeBaseArgs,
  type SearchKnowledgeBaseState,
  type ViewKnowledgeBaseArgs,
  type ViewKnowledgeBaseState,
} from './knowledgeBase';
export {
  type AnalyzeVisualMediaContentOptions,
  type AnalyzeVisualMediaNormalizedInput,
  type AnalyzeVisualMediaParams,
  buildAnalyzeVisualMediaContent,
  createUrlVisualFileItems,
  createVisualFileItems,
  filterAllowedVisualMediaUrls,
  formatVisualMediaUrlValidationError,
  getUnexpectedAnalyzeVisualMediaArgumentKeys,
  getVisualUrlName,
  hasUserVisualFiles,
  hasVisualFiles,
  inferVisualTypeFromUrl,
  isAllowedVisualMediaUrl,
  LobeAgentApiName,
  type LobeAgentApiNameType,
  LobeAgentIdentifier,
  LobeAgentManifest,
  systemPrompt as lobeAgentSystemPrompt,
  MAX_VISUAL_MEDIA_URL_LENGTH,
  MAX_VISUAL_MEDIA_URLS,
  normalizeAnalyzeVisualMediaInput,
  normalizeStringArray,
  selectVisualFileItems,
  validateVisualMediaUrls,
  type VisualFileItem,
  type VisualMediaUrlValidationResult,
  type VisualSourceMessage,
} from './lobeAgent';
export {
  MemoryApiName,
  type MemoryApiNameType,
  MemoryExecutionRuntime,
  MemoryIdentifier,
  MemoryManifest,
  systemPrompt as memorySystemPrompt,
} from './memory';
export {
  MessageApiName,
  type MessageApiNameType,
  MessageExecutionRuntime,
  MessageManifest,
  MessagePlatform,
  type MessagePlatformType,
  systemPrompt as messageSystemPrompt,
  MessageToolIdentifier,
} from './message';
export {
  type DocumentType,
  NotebookApiName,
  type CreateDocumentArgs as NotebookCreateDocumentArgs,
  type CreateDocumentState as NotebookCreateDocumentState,
  type DeleteDocumentArgs as NotebookDeleteDocumentArgs,
  type DeleteDocumentState as NotebookDeleteDocumentState,
  type NotebookDocument,
  type DocumentSourceType as NotebookDocumentSourceType,
  NotebookExecutionRuntime,
  type GetDocumentArgs as NotebookGetDocumentArgs,
  type GetDocumentState as NotebookGetDocumentState,
  NotebookIdentifier,
  NotebookManifest,
  systemPrompt as notebookSystemPrompt,
  type UpdateDocumentArgs as NotebookUpdateDocumentArgs,
  type UpdateDocumentState as NotebookUpdateDocumentState,
} from './notebook';
export {
  type ActivateSkillParams,
  type ActivateSkillState,
  type CommandResult,
  type ExecScriptActivatedSkill,
  type ExecScriptParams,
  type ExecScriptState,
  type ExportFileParams,
  type ExportFileState,
  type ReadReferenceParams,
  type ReadReferenceState,
  type RunCommandOptions,
  type RunCommandParams,
  SkillsApiName,
  SkillsIdentifier,
  SkillsManifest,
} from './skills';
export {
  type ImportFromMarketParams,
  type ImportFromMarketState,
  type ImportSkillParams,
  type ImportSkillState,
  type MarketSkillItem,
  type SearchSkillParams,
  type SearchSkillState,
  SkillStoreApiName,
  SkillStoreIdentifier,
  SkillStoreManifest,
} from './skillStore';
export {
  DEFAULT_LIST_TASK_LIMIT,
  type ListTasksParams,
  normalizeListTasksParams,
  normalizeOptionalFilterValues,
  TASK_STATUSES,
  TaskApiName,
  type TaskApiNameType,
  TaskIdentifier,
  type TaskListDisplayFilters,
  type TaskListQuery,
  TaskManifest,
  systemPrompt as taskSystemPrompt,
  UNFINISHED_TASK_STATUSES,
} from './task';
export {
  TopicReferenceApiName,
  type TopicReferenceApiNameType,
  TopicReferenceExecutor,
  TopicReferenceIdentifier,
  TopicReferenceManifest,
} from './topicReference';
export {
  type UpdateDocumentArgs,
  WebOnboardingApiName,
  type WebOnboardingDocumentType,
  WebOnboardingIdentifier,
  WebOnboardingManifest,
} from './webOnboarding';

/**
 * Default tool IDs that will always be added to the tools list.
 * Shared between frontend (createAgentToolsEngine) and server (createServerAgentToolsEngine).
 */
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

/**
 * Tool IDs that are always enabled regardless of user selection.
 * These are core system tools that the agent needs to function properly.
 */
export const alwaysOnToolIds = [
  LobeActivatorManifest.identifier,
  SkillsManifest.identifier,
  SkillStoreManifest.identifier,
];

/**
 * Tool IDs to exclude from defaults when in manual skill-activate mode.
 * These are the tool/skill discovery tools that should be disabled when user wants precise control.
 * Other default tools (sandbox, web browsing, etc.) remain available if enabled externally.
 */
export const manualModeExcludeToolIds = [
  LobeActivatorManifest.identifier,
  SkillStoreManifest.identifier,
];

/**
 * Tool IDs whose enabled state is decided by runtime / system conditions
 * (e.g. cloud runtime, agent has documents attached, knowledge base configured,
 * desktop gateway available), NOT by the user's plugin selection.
 *
 * The chat-input Tools popover deliberately hides these — even in manual
 * skill-activate mode — so users don't see a toggle that they can't actually
 * affect (the rules in `AgentToolsEngine.createEnableChecker` would force them
 * back on regardless of UI state).
 *
 * If you change this list, keep it in sync with the `rules` map in
 * `src/server/modules/Mecha/AgentToolsEngine/index.ts` and the matching frontend
 * `src/helpers/toolEngineering/index.ts`.
 */
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
  {
    identifier: CredsManifest.identifier,
    manifest: CredsManifest,
    type: 'builtin',
  },
  {
    identifier: CronManifest.identifier,
    manifest: CronManifest,
    type: 'builtin',
  },
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
  {
    identifier: GTDManifest.identifier,
    manifest: GTDManifest,
    type: 'builtin',
  },
  {
    identifier: CalculatorManifest.identifier,
    manifest: CalculatorManifest,
    type: 'builtin',
  },
  {
    identifier: MessageManifest.identifier,
    manifest: MessageManifest,
    type: 'builtin',
  },
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
];

const recommendedBuiltinIds = new Set(
  RECOMMENDED_SKILLS.filter((s) => s.type === RecommendedSkillType.Builtin).map((s) => s.id),
);

/**
 * Non-hidden builtin tools that are NOT in RECOMMENDED_SKILLS.
 * These tools default to uninstalled and must be explicitly installed by the user from the Skill Store.
 */
export const defaultUninstalledBuiltinTools = builtinTools
  .filter((t) => !t.hidden && !recommendedBuiltinIds.has(t.identifier))
  .map((t) => t.identifier);
