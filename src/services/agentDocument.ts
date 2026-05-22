import type { DocumentLoadFormat, DocumentLoadRule } from '@lobechat/agent-templates';
import {
  AGENT_DOCUMENT_INJECTION_POSITIONS,
  type AgentContextDocument,
} from '@lobechat/context-engine';

import { restClient } from '@/libs/rest';
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
    return restClient.get<AgentDocumentTemplateItem[]>('/agent-documents/templates');
  };

  getDocuments = async (params: { agentId: string }): Promise<AgentDocumentItem[]> => {
    return restClient.get<AgentDocumentItem[]>('/agent-documents', {
      params: { agent_id: params.agentId } as any,
    });
  };

  initializeFromTemplate = async (params: { agentId: string; templateSet: string }) => {
    const result = await restClient.post('/agent-documents/initialize-template', { body: params });
    await revalidateAgentDocuments(params.agentId);
    return result;
  };

  listDocuments = async (params: {
    agentId: string;
    target?: 'agent' | 'currentTopic';
    topicId?: string;
  }): Promise<AgentDocumentItem[]> => {
    return restClient.get<AgentDocumentItem[]>('/agent-documents/list', { params: params as any });
  };

  associateDocument = async (params: { agentId: string; documentId: string }) => {
    const result = await restClient.post<any>('/agent-documents/associate', { body: params });
    await invalidateDocumentMutation({
      agentDocumentId: getAgentDocumentId(result),
      agentId: params.agentId,
      cause: 'agent-document',
      documentId: params.documentId,
    });
    return result;
  };

  createDocument = async (params: {
    agentId: string;
    content: string;
    title: string;
  }): Promise<AgentDocumentItem> => {
    const result = await restClient.post<any>('/agent-documents', { body: params });
    await invalidateDocumentMutation({
      agentDocumentId: getAgentDocumentId(result),
      agentId: params.agentId,
      cause: 'agent-document',
      documentId: getDocumentId(result),
    });
    return result;
  };

  createForTopic = async (params: {
    agentId: string;
    content: string;
    title: string;
    topicId: string;
  }): Promise<AgentDocumentItem> => {
    const result = await restClient.post<any>('/agent-documents/for-topic', { body: params });
    await invalidateDocumentMutation({
      agentDocumentId: getAgentDocumentId(result),
      agentId: params.agentId,
      cause: 'agent-document',
      documentId: getDocumentId(result),
      topicId: params.topicId,
    });
    return result;
  };

  readDocument = async (params: {
    agentId: string;
    format?: 'xml' | 'markdown' | 'both';
    id: string;
  }): Promise<AgentDocumentItem | undefined> => {
    return restClient.get(`/agent-documents/${params.id}/read`, {
      params: { agent_id: params.agentId, format: params.format } as any,
    });
  };

  replaceDocumentContent = async (params: {
    agentId: string;
    content: string;
    id: string;
  }): Promise<AgentDocumentItem | undefined> => {
    const result = await restClient.put<any>(`/agent-documents/${params.id}/content`, {
      body: { agentId: params.agentId, content: params.content },
    });
    await invalidateDocumentMutation({
      agentDocumentId: params.id,
      agentId: params.agentId,
      cause: 'agent-document',
      documentId: getDocumentId(result),
    });
    return result;
  };

  modifyNodes = async (params: {
    agentId: string;
    id: string;
    operations: Array<
      | { action: 'insert'; afterId: string; litexml: string }
      | { action: 'insert'; beforeId: string; litexml: string }
      | { action: 'modify'; litexml: string | string[] }
      | { action: 'remove'; id: string }
    >;
  }): Promise<AgentDocumentItem | undefined> => {
    const result = await restClient.post<any>(`/agent-documents/${params.id}/modify-nodes`, {
      body: { agentId: params.agentId, operations: params.operations },
    });
    await invalidateDocumentMutation({
      agentDocumentId: params.id,
      agentId: params.agentId,
      cause: 'agent-document',
      documentId: getDocumentId(result),
    });
    return result;
  };

  removeDocument = async (params: {
    agentId: string;
    documentId?: string;
    id: string;
    topicId?: string;
  }): Promise<{ deleted: boolean; id: string }> => {
    const { agentId, documentId, id, topicId } = params;
    const result = await restClient.delete<{ deleted: boolean; id: string }>(
      `/agent-documents/${id}`,
      {
        params: { agent_id: agentId } as any,
      },
    );
    await invalidateDocumentMutation({
      agentDocumentId: id,
      agentId,
      cause: 'agent-document',
      documentId,
      topicId,
    });
    return result;
  };

  copyDocument = async (params: {
    agentId: string;
    id: string;
    newTitle?: string;
  }): Promise<AgentDocumentItem | undefined> => {
    const result = await restClient.post<any>(`/agent-documents/${params.id}/copy`, {
      body: { agentId: params.agentId, newTitle: params.newTitle },
    });
    await invalidateDocumentMutation({
      agentDocumentId: getAgentDocumentId(result),
      agentId: params.agentId,
      cause: 'agent-document',
      documentId: getDocumentId(result),
    });
    return result;
  };

  renameDocument = async (params: {
    agentId: string;
    id: string;
    newTitle: string;
  }): Promise<AgentDocumentItem | undefined> => {
    const result = await restClient.put<any>(`/agent-documents/${params.id}/rename`, {
      body: { agentId: params.agentId, newTitle: params.newTitle },
    });
    await invalidateDocumentMutation({
      agentDocumentId: params.id,
      agentId: params.agentId,
      cause: 'agent-document',
      documentId: getDocumentId(result),
    });
    return result;
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
      timeRange?: { from?: string; to?: string };
    };
  }): Promise<AgentDocumentItem | undefined> => {
    const result = await restClient.put<AgentDocumentItem | undefined>(
      `/agent-documents/${params.id}/load-rule`,
      {
        body: { agentId: params.agentId, rule: params.rule },
      },
    );
    await revalidateAgentDocuments(params.agentId);
    return result;
  };
}

export const mapAgentDocumentsToContext = (
  documents: Awaited<ReturnType<AgentDocumentService['getDocuments']>>,
): AgentContextDocument[] =>
  (documents as any[]).map((doc: any) => ({
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
