import { restClient } from '@/libs/rest';
import {
  type CheckFileHashResult,
  type FileItem,
  type FileListItem,
  type KnowledgeItemStatus,
  type QueryFileListParams,
  type UploadFileParams,
} from '@/types/files';

interface CreateFileParams extends Omit<UploadFileParams, 'url'> {
  knowledgeBaseId?: string;
  parentId?: string;
  url: string;
}

export class FileService {
  createFile = async (
    params: UploadFileParams & { parentId?: string },
    knowledgeBaseId?: string,
  ): Promise<{ id: string; url: string }> => {
    return restClient.post<{ id: string; url: string }>('/files', {
      body: { ...params, knowledgeBaseId } as CreateFileParams,
    });
  };

  getFile = async (id: string): Promise<FileItem> => {
    const item = await restClient.get<any>(`/files/${id}`);

    if (!item) {
      throw new Error('file not found');
    }

    return {
      createdAt: item.createdAt,
      id: item.id,
      name: item.name,
      size: item.size,
      source: item.source,
      type: item.fileType,
      updatedAt: item.updatedAt,
      url: item.url,
    };
  };

  removeFile = async (id: string): Promise<void> => {
    await restClient.delete(`/files/${id}`);
  };

  removeFiles = async (ids: string[]): Promise<void> => {
    await restClient.post('/files/batch-delete', { body: { ids } });
  };

  removeAllFiles = async () => {
    await restClient.delete('/files');
  };

  getKnowledgeItems = async (params: QueryFileListParams) => {
    return restClient.get('/files/knowledge-items', { params: params as any });
  };

  getKnowledgeItemStatusesByIds = async (ids: string[]): Promise<KnowledgeItemStatus[]> => {
    return restClient.post<KnowledgeItemStatus[]>('/files/knowledge-item-statuses', {
      body: { ids },
    });
  };

  resolveKnowledgeItemIds = async (params: QueryFileListParams) => {
    return restClient.get('/files/knowledge-item-ids', { params: params as any });
  };

  deleteKnowledgeItemsByQuery = async (params: QueryFileListParams) => {
    return restClient.post('/files/knowledge-items/delete', { body: params });
  };

  getKnowledgeItem = async (id: string): Promise<FileListItem | null> => {
    if (id.startsWith('docs_')) {
      const doc = await restClient.get<any>(`/documents/${id}`);
      if (!doc) return null;

      return {
        chunkCount: null,
        chunkingError: null,
        chunkingStatus: null,
        content: doc.content,
        createdAt: doc.createdAt ? new Date(doc.createdAt) : new Date(),
        editorData: doc.editorData,
        embeddingError: null,
        embeddingStatus: null,
        fileType: doc.fileType || 'custom/document',
        finishEmbedding: false,
        id: doc.id,
        metadata: doc.metadata,
        name: doc.title || doc.filename || 'Untitled',
        parentId: doc.parentId,
        size: doc.totalCharCount || 0,
        slug: doc.slug,
        sourceType: 'document',
        updatedAt: doc.updatedAt ? new Date(doc.updatedAt) : new Date(),
        url: doc.source || '',
      } as FileListItem;
    } else {
      return restClient.get(`/files/${id}/item`);
    }
  };

  getFolderBreadcrumb = async (slug: string) => {
    return restClient.get(`/documents/breadcrumb/${slug}`);
  };

  checkFileHash = async (hash: string): Promise<CheckFileHashResult> => {
    return restClient.post<CheckFileHashResult>('/files/check-hash', { body: { hash } });
  };

  removeFileAsyncTask = async (id: string, type: 'embedding' | 'chunk') => {
    return restClient.delete(`/files/${id}/async-task`, { params: { type } });
  };

  updateFile = async (
    id: string,
    data: {
      metadata?: Record<string, any>;
      name?: string;
      parentId?: string | null;
    },
  ) => {
    return restClient.put(`/files/${id}`, { body: data });
  };

  getRecentFiles = async (limit?: number) => {
    return restClient.get('/files/recent', { params: limit ? { limit } : undefined });
  };

  getRecentPages = async (limit?: number) => {
    return restClient.get('/files/recent-pages', { params: limit ? { limit } : undefined });
  };
}

export const fileService = new FileService();
