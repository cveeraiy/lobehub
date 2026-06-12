import { z } from 'zod';

import type { ChatSemanticSearchChunk } from './chunk';

export const SemanticSearchSchema = z.object({
  fileIds: z.array(z.string()).optional(),
  knowledgeIds: z.array(z.string()).optional(),
  query: z.string(),
  topK: z.number().optional(),
});

export type SemanticSearchSchemaType = z.infer<typeof SemanticSearchSchema>;

export type MessageSemanticSearchChunk = Pick<ChatSemanticSearchChunk, 'id' | 'similarity'>;

export interface FileSearchResult {
  fileId: string;
  fileName: string;
  relevanceScore: number;
  topChunks: Array<{
    id: string;
    similarity: number;
    text: string;
  }>;
}

export interface NewChunkItem {
  abstract?: string | null;
  clientId?: string | null;
  createdAt?: Date;
  fileId?: string;
  id?: string;
  index?: number | null;
  metadata?: unknown;
  text?: string | null;
  type?: string | null;
  updatedAt?: Date;
  userId?: string | null;
}

export interface NewUnstructuredChunkItem {
  clientId?: string | null;
  compositeId?: string | null;
  createdAt?: Date;
  fileId?: string | null;
  id?: string;
  index?: number | null;
  metadata?: unknown;
  parentId?: string | null;
  text?: string | null;
  type?: string | null;
  updatedAt?: Date;
  userId?: string | null;
}

export interface NewEmbeddingsItem {
  chunkId?: string | null;
  clientId?: string | null;
  embeddings?: number[] | null;
  fileId?: string;
  id?: string;
  model?: string | null;
  userId?: string | null;
}
