import type { DocumentLoadFormat, DocumentLoadRule } from '@lobechat/agent-templates';
import {
  AGENT_DOCUMENT_INJECTION_POSITIONS,
  type AgentContextDocument,
} from '@lobechat/context-engine';

import { lambdaClient } from '@/libs/trpc/client';
import { invalidateDocumentMutation } from '@/services/document/invalidation';

export { agentDocumentSWRKeys } from '@/services/document/swrKeys';

const VALID_DOCUMENT_POSITIONS = new Set<AgentContextDocument['loadPosition']>(
  AGENT_DOCUMENT_INJECTION_POSITIONS,
);

export const normalizeAgentDocumentPosition = (
  position: string | null | undefined,
): AgentContextDocument['loadPosition'] | undefined => {
  if (!position) return undefined;

  return VALID_DOCUMENT_POSITIONS.has(position as AgentContextDocument['loadPosition'])
    ? (position as AgentContextDocument['loadPosition'])
    : undefined;
};

const revalidateAgentDocuments = async (agentId: string) => {
  await invalidateDocumentMutation({ agentId, cause: 'agent-document' });
};

const getStringField = (value: unknown, field: 'documentId' | 'id') => {
  if (!value || typeof value !== 'object' || !(field in value)) return undefined;

  const fieldValue = (value as Record<string, unknown>)[field];

  return typeof fieldValue === 'string' ? fieldValue : undefined;
};

const getAgentDocumentId = (value: unknown) => getStringField(value, 'id');

const getDocumentId = (value: unknown) => getStringField(value, 'documentId');

export interface AgentDocumentItem {
  content?: string;
  createdAt?: Date | string | null;
  description?: string;
  documentId: string;
  filename: string;
  id: string;
  loadRules?: AgentContextDocument['loadRules'];
  policy?: {
    context?: {
      policyLoadFormat?: AgentContextDocument['policyLoadFormat'];
      position?: string | null;
    };
  } | null;
  policyLoad?: AgentContextDocument['policyLoad'];
  policyLoadFormat?: AgentContextDocument['policyLoadFormat'];
  policyLoadPosition?: string | null;
  sourceType?: string | null;
  templateId?: string | null;
  title: string;
}

export interface AgentDocumentTemplateItem {
  description?: string;
  filenames: string[];
  id: string;
  name: string;
}

class AgentDocumentService {
  getTemplates = async (): Promise<AgentDocumentTemplateItem[]> => {
    return lambdaClient.agentDocument.getTemplates.query();
  };

  getDocuments = async (params: { agentId: string }): Promise<AgentDocumentItem[]> => {
    return lambdaClient.agentDocument.getDocuments.query(params) as Promise<AgentDocumentItem[]>;
  };

  initializeFromTemplate = async (params: { agentId: string; templateSet: string }) => {
    const result = await lambdaClient.agentDocument.initializeFromTemplate.mutate(params);
    await revalidateAgentDocuments(params.agentId);

    return result as unknown as AgentDocumentItem | undefined;
  };

  listDocuments = async (params: {
    agentId: string;
    target?: 'agent' | 'currentTopic';
    topicId?: string;
  }): Promise<AgentDocumentItem[]> => {
    return lambdaClient.agentDocument.listDocuments.query(params) as Promise<AgentDocumentItem[]>;
  };

  associateDocument = async (params: { agentId: string; documentId: string }) => {
    const result = await lambdaClient.agentDocument.associateDocument.mutate(params);
    await invalidateDocumentMutation({
      agentDocumentId: getAgentDocumentId(result),
      agentId: params.agentId,
      cause: 'agent-document',
      documentId: params.documentId,
    });

    return result as unknown as AgentDocumentItem | undefined;
  };

  createDocument = async (params: {
    agentId: string;
    content: string;
    title: string;
  }): Promise<AgentDocumentItem> => {
    const result = await lambdaClient.agentDocument.createDocument.mutate(params);
    await invalidateDocumentMutation({
      agentDocumentId: getAgentDocumentId(result),
      agentId: params.agentId,
      cause: 'agent-document',
      documentId: getDocumentId(result),
    });

    return result as unknown as AgentDocumentItem;
  };

  createForTopic = async (params: {
    agentId: string;
    content: string;
    title: string;
    topicId: string;
  }): Promise<AgentDocumentItem> => {
    const result = await lambdaClient.agentDocument.createForTopic.mutate(params);
    await invalidateDocumentMutation({
      agentDocumentId: getAgentDocumentId(result),
      agentId: params.agentId,
      cause: 'agent-document',
      documentId: getDocumentId(result),
      topicId: params.topicId,
    });

    return result as unknown as AgentDocumentItem;
  };

  readDocument = async (params: {
    agentId: string;
    format?: 'xml' | 'markdown' | 'both';
    id: string;
  }): Promise<AgentDocumentItem | undefined> => {
    return lambdaClient.agentDocument.readDocument.query(params) as Promise<
      AgentDocumentItem | undefined
    >;
  };

  replaceDocumentContent = async (params: {
    agentId: string;
    content: string;
    id: string;
  }): Promise<AgentDocumentItem | undefined> => {
    const result = await lambdaClient.agentDocument.replaceDocumentContent.mutate(params);
    await invalidateDocumentMutation({
      agentDocumentId: params.id,
      agentId: params.agentId,
      cause: 'agent-document',
      documentId: getDocumentId(result),
    });

    return result as unknown as AgentDocumentItem | undefined;
  };

  modifyNodes = async (params: {
    agentId: string;
    id: string;
    operations: Array<
      | {
          action: 'insert';
          afterId: string;
          litexml: string;
        }
      | {
          action: 'insert';
          beforeId: string;
          litexml: string;
        }
      | {
          action: 'modify';
          litexml: string | string[];
        }
      | {
          action: 'remove';
          id: string;
        }
    >;
  }): Promise<AgentDocumentItem | undefined> => {
    const result = await lambdaClient.agentDocument.modifyNodes.mutate(params);
    await invalidateDocumentMutation({
      agentDocumentId: params.id,
      agentId: params.agentId,
      cause: 'agent-document',
      documentId: getDocumentId(result),
    });

    return result as unknown as AgentDocumentItem | undefined;
  };

  removeDocument = async (params: {
    agentId: string;
    documentId?: string;
    id: string;
    topicId?: string;
  }): Promise<{ deleted: boolean; id: string }> => {
    const { agentId, documentId, id, topicId } = params;
    const result = await lambdaClient.agentDocument.removeDocument.mutate({ agentId, id });
    await invalidateDocumentMutation({
      agentDocumentId: id,
      agentId,
      cause: 'agent-document',
      documentId,
      topicId,
    });

    return result as unknown as { deleted: boolean; id: string };
  };

  copyDocument = async (params: {
    agentId: string;
    id: string;
    newTitle?: string;
  }): Promise<AgentDocumentItem | undefined> => {
    const result = await lambdaClient.agentDocument.copyDocument.mutate(params);
    await invalidateDocumentMutation({
      agentDocumentId: getAgentDocumentId(result),
      agentId: params.agentId,
      cause: 'agent-document',
      documentId: getDocumentId(result),
    });

    return result as unknown as AgentDocumentItem | undefined;
  };

  renameDocument = async (params: {
    agentId: string;
    id: string;
    newTitle: string;
  }): Promise<AgentDocumentItem | undefined> => {
    const result = await lambdaClient.agentDocument.renameDocument.mutate(params);
    await invalidateDocumentMutation({
      agentDocumentId: params.id,
      agentId: params.agentId,
      cause: 'agent-document',
      documentId: getDocumentId(result),
    });

    return result as unknown as AgentDocumentItem | undefined;
  };

  updateLoadRule = async (params: {
    agentId: string;
    id: string;
    rule: {
      keywordMatchMode?: 'all' | 'any';
      keywords?: string[];
      maxTokens?: number;
      policyLoadFormat?: DocumentLoadFormat;
      priority?: number;
      regexp?: string;
      rule?: DocumentLoadRule;
      timeRange?: {
        from?: string;
        to?: string;
      };
    };
  }): Promise<AgentDocumentItem | undefined> => {
    const result = await lambdaClient.agentDocument.updateLoadRule.mutate(params);
    await revalidateAgentDocuments(params.agentId);

    return result as unknown as AgentDocumentItem | undefined;
  };
}

export const mapAgentDocumentsToContext = (
  documents: Awaited<ReturnType<AgentDocumentService['getDocuments']>>,
): AgentContextDocument[] =>
  documents.map((doc) => ({
    content: doc.content ?? undefined,
    description: doc.description,
    filename: doc.filename,
    id: doc.id,
    loadPosition: normalizeAgentDocumentPosition(
      doc.policy?.context?.position || doc.policyLoadPosition,
    ),
    loadRules: doc.loadRules,
    policyId: doc.templateId,
    policyLoad: doc.policyLoad as 'always' | 'progressive',
    policyLoadFormat: doc.policy?.context?.policyLoadFormat || doc.policyLoadFormat || undefined,
    title: doc.title,
  }));

export const resolveAgentDocumentsContext = async (params: {
  agentId?: string;
  cachedDocuments?: AgentContextDocument[];
}) => {
  const { agentId, cachedDocuments } = params;

  if (cachedDocuments !== undefined) return cachedDocuments;
  if (!agentId) return undefined;

  const documents = await agentDocumentService.getDocuments({ agentId });

  return mapAgentDocumentsToContext(documents);
};

export const agentDocumentService = new AgentDocumentService();
