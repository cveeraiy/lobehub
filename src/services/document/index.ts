import { type DocumentItem } from '@lobechat/database/schemas';

import { restClient } from '@/libs/rest';
import type {
  CompareHistoryItemsInput,
  CompareHistoryItemsOutput,
  GetHistoryItemInput,
  GetHistoryItemOutput,
  ListHistoryInput,
  ListHistoryOutput,
  SaveDocumentHistoryInput,
  SaveDocumentHistoryOutput,
  UpdateDocumentInput,
  UpdateDocumentOutput,
} from '@/types/documentHistory';

import { abortableRequest } from '../utils/abortableRequest';

const serializeSavedAt = (savedAt: Date | string) =>
  savedAt instanceof Date ? savedAt.toISOString() : savedAt;

type SerializedSavedAt<T extends { savedAt: Date | string }> = Omit<T, 'savedAt'> & {
  savedAt: string;
};

const serializeHistoryTimestamp = <T extends { savedAt: Date | string }>(
  result: T,
): SerializedSavedAt<T> => ({
  ...result,
  savedAt: serializeSavedAt(result.savedAt),
});

const serializeHistoryList = <
  T extends {
    items: Array<{
      id: string;
      isCurrent: boolean;
      saveSource: ListHistoryOutput['items'][number]['saveSource'];
      savedAt: Date | string;
    }>;
    nextBeforeSavedAt?: Date | string;
  },
>(
  result: T,
): ListHistoryOutput => ({
  ...result,
  items: result.items.map((item) => ({
    ...item,
    savedAt: serializeSavedAt(item.savedAt),
  })),
  nextBeforeSavedAt: result.nextBeforeSavedAt
    ? serializeSavedAt(result.nextBeforeSavedAt)
    : undefined,
});

const serializeHistoryItem = <
  T extends {
    editorData: GetHistoryItemOutput['editorData'];
    id: string;
    isCurrent: boolean;
    saveSource: GetHistoryItemOutput['saveSource'];
    savedAt: Date | string;
  },
>(
  result: T,
): GetHistoryItemOutput => serializeHistoryTimestamp(result);

const serializeHistoryComparison = <
  T extends {
    from: {
      editorData: CompareHistoryItemsOutput['from']['editorData'];
      id: string;
      isCurrent: boolean;
      saveSource: CompareHistoryItemsOutput['from']['saveSource'];
      savedAt: Date | string;
    };
    to: {
      editorData: CompareHistoryItemsOutput['to']['editorData'];
      id: string;
      isCurrent: boolean;
      saveSource: CompareHistoryItemsOutput['to']['saveSource'];
      savedAt: Date | string;
    };
  },
>(
  result: T,
): CompareHistoryItemsOutput => ({
  from: serializeHistoryTimestamp(result.from),
  to: serializeHistoryTimestamp(result.to),
});

export interface CreateDocumentParams {
  content?: string;
  editorData: string;
  fileType?: string;
  knowledgeBaseId?: string;
  metadata?: Record<string, any>;
  parentId?: string;
  slug?: string;
  title: string;
}

export interface ListDocumentHistoryParams extends ListHistoryInput {}

export interface GetDocumentHistoryItemParams extends GetHistoryItemInput {}

export interface CompareDocumentHistoryItemsParams extends CompareHistoryItemsInput {}

export interface UpdateDocumentParams extends UpdateDocumentInput {}

export interface DocumentHistoryClientSurface {
  compareDocumentHistoryItems: (
    params: CompareDocumentHistoryItemsParams,
  ) => Promise<CompareHistoryItemsOutput>;
  getDocumentHistoryItem: (
    params: GetDocumentHistoryItemParams,
    uniqueKey?: string,
  ) => Promise<GetHistoryItemOutput>;
  listDocumentHistory: (params: ListDocumentHistoryParams) => Promise<ListHistoryOutput>;
  saveDocumentHistory: (params: SaveDocumentHistoryInput) => Promise<SaveDocumentHistoryOutput>;
  updateDocument: (params: UpdateDocumentParams) => Promise<UpdateDocumentOutput>;
}

export class DocumentService {
  async createDocument(params: CreateDocumentParams): Promise<DocumentItem> {
    return restClient.post<DocumentItem>('/documents', {
      body: {
        content: params.content,
        editor_data: params.editorData,
        file_type: params.fileType,
        knowledge_base_id: params.knowledgeBaseId,
        metadata: params.metadata,
        parent_id: params.parentId,
        slug: params.slug,
        title: params.title,
      },
    });
  }

  async createDocuments(documents: CreateDocumentParams[]): Promise<DocumentItem[]> {
    return restClient.post<DocumentItem[]>('/documents/batch', { body: { documents } });
  }

  async queryDocuments(params?: {
    current?: number;
    fileTypes?: string[];
    pageSize?: number;
    sourceTypes?: string[];
  }): Promise<{ items: DocumentItem[]; total: number }> {
    return restClient.get('/documents', { params: params as any });
  }

  async listDocumentHistory(params: ListDocumentHistoryParams): Promise<ListHistoryOutput> {
    const result = await restClient.get<any>('/documents/history', { params: params as any });
    return serializeHistoryList(result);
  }

  async getDocumentHistoryItem(
    params: GetDocumentHistoryItemParams,
    uniqueKey?: string,
  ): Promise<GetHistoryItemOutput> {
    if (uniqueKey) {
      return abortableRequest.execute(uniqueKey, async (signal) => {
        const result = await restClient.get<any>('/documents/history/item', {
          params: params as any,
          signal,
        });
        return serializeHistoryItem(result);
      });
    }

    const result = await restClient.get<any>('/documents/history/item', {
      params: params as any,
    });
    return serializeHistoryItem(result);
  }

  async compareDocumentHistoryItems(
    params: CompareDocumentHistoryItemsParams,
  ): Promise<CompareHistoryItemsOutput> {
    const result = await restClient.get<any>('/documents/history/compare', {
      params: params as any,
    });
    return serializeHistoryComparison(result);
  }

  async getPageDocuments(pageSize: number = 20): Promise<DocumentItem[]> {
    const result = await this.queryDocuments({
      current: 0,
      fileTypes: ['custom/document', 'application/pdf'],
      pageSize,
      sourceTypes: ['editor', 'file', 'api'],
    });

    return result.items
      .filter(
        (doc) =>
          ['editor', 'file', 'api'].includes(doc.sourceType) &&
          ['custom/document', 'application/pdf'].includes(doc.fileType),
      )
      .map((doc) => ({ ...doc, filename: doc.filename ?? doc.title ?? 'Untitled' }));
  }

  async getDocumentById(id: string, uniqueKey?: string): Promise<DocumentItem | undefined> {
    if (uniqueKey) {
      return abortableRequest.execute(uniqueKey, async (signal) =>
        restClient.get(`/documents/${id}`, { signal }),
      );
    }

    return restClient.get(`/documents/${id}`);
  }

  async parseDocument(id: string): Promise<DocumentItem> {
    const result = await restClient.post<any>(`/documents/${id}/parse`);
    return {
      content: result.content ?? '',
      createdAt: result.createdAt ? new Date(result.createdAt) : new Date(),
      editorData: result.editorData ?? null,
      fileType: result.fileType ?? 'custom/document',
      filename: result.filename,
      id: result.id,
      metadata: result.metadata ?? {},
      source: result.source ?? 'document',
      sourceType: result.sourceType ?? 'file',
      title: result.title ?? result.filename ?? 'Untitled',
      totalCharCount: result.totalCharCount ?? 0,
      totalLineCount: result.totalLineCount ?? 0,
      updatedAt: result.updatedAt ? new Date(result.updatedAt) : new Date(),
    } as DocumentItem;
  }

  async deleteDocument(id: string): Promise<void> {
    await restClient.delete(`/documents/${id}`);
  }

  async deleteDocuments(ids: string[]): Promise<void> {
    await restClient.post('/documents/batch-delete', { body: { ids } });
  }

  async updateDocument(params: UpdateDocumentParams): Promise<UpdateDocumentOutput> {
    const { id, ...body } = params as any;
    const result = await restClient.put<any>(`/documents/${id}`, { body });

    return {
      ...result,
      savedAt: result.savedAt
        ? result.savedAt instanceof Date
          ? result.savedAt.toISOString()
          : result.savedAt
        : undefined,
    };
  }

  async saveDocumentHistory(params: SaveDocumentHistoryInput): Promise<SaveDocumentHistoryOutput> {
    const result = await restClient.post<any>('/documents/history', { body: params });

    return {
      savedAt: result.savedAt instanceof Date ? result.savedAt.toISOString() : result.savedAt,
    };
  }
}

export const documentService = new DocumentService() as DocumentService &
  DocumentHistoryClientSurface;
