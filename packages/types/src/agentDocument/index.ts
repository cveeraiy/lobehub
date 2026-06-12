import type {
  AgentDocumentPolicy,
  DocumentLoadFormat,
  DocumentLoadRules,
  PolicyLoad,
} from '@lobechat/agent-templates';

export type { AgentDocumentPolicy, DocumentLoadRules } from '@lobechat/agent-templates';
export {
  AgentAccess,
  AutoLoadAccess,
  DocumentLoadFormat,
  DocumentLoadPosition,
  DocumentLoadRule,
  PolicyLoad,
} from '@lobechat/agent-templates';

export type AgentDocumentSourceType = 'api' | 'file' | 'topic' | 'web';

export interface AgentDocument {
  accessPublic: number;
  accessSelf: number;
  accessShared: number;
  agentId: string;
  content: string;
  createdAt: Date;
  deletedAt: Date | null;
  deletedByAgentId: string | null;
  deletedByUserId: string | null;
  deleteReason: string | null;
  description: string | null;
  documentId: string;
  editorData: Record<string, unknown> | null;
  filename: string;
  fileType: string;
  id: string;
  metadata: Record<string, unknown> | null;
  parentId: string | null;
  policy: AgentDocumentPolicy | null;
  policyLoad: PolicyLoad;
  policyLoadFormat: DocumentLoadFormat;
  policyLoadPosition: string;
  policyLoadRule: string;
  source: string | null;
  sourceType: AgentDocumentSourceType;
  templateId: string | null;
  title: string;
  updatedAt: Date;
  userId: string;
}

export interface AgentDocumentWithRules extends AgentDocument {
  loadRules: DocumentLoadRules;
}

export interface ToolUpdateLoadRule {
  keywordMatchMode?: 'all' | 'any';
  keywords?: string[];
  maxDocuments?: number;
  maxTokens?: number;
  mode?: 'always' | 'manual' | 'on-demand' | 'progressive';
  pinnedDocumentIds?: string[];
  policyLoadFormat?: 'file' | 'raw';
  priority?: number;
  regexp?: string;
  rule?: 'always' | 'by-keywords' | 'by-regexp' | 'by-time-range';
  timeRange?: {
    from?: string;
    to?: string;
  };
}
