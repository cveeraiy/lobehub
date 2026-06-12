import { z } from 'zod';

export type SearchMode = 'off' | 'auto' | 'on';

export type SearchResultType =
  | 'agent'
  | 'chatGroup'
  | 'communityAgent'
  | 'file'
  | 'folder'
  | 'knowledgeBase'
  | 'mcp'
  | 'memory'
  | 'message'
  | 'page'
  | 'pageContent'
  | 'plugin'
  | 'topic';

export enum ModelSearchImplement {
  /**
   * Model has built-in search functionality
   * Similar to search modes of models like Jina, PPLX, transparent to the caller
   */
  Internal = 'internal',
  /**
   * Uses parameter toggle approach, e.g. Qwen, Google, OpenRouter, search results in
   */
  Params = 'params',
  /**
   * Uses tool calling approach
   */
  Tool = 'tool',
}

export interface CitationItem {
  favicon?: string;
  id?: string;
  title?: string;
  url: string;
}

export interface ImageCitationItem {
  domain?: string;
  imageUri?: string;
  sourceUri?: string;
  title?: string;
}

export interface GroundingSearch {
  citations?: CitationItem[];
  imageResults?: ImageCitationItem[];
  imageSearchQueries?: string[];
  searchQueries?: string[];
}

export interface BaseSearchResult {
  createdAt: Date;
  description?: string | null;
  id: string;
  relevance: number;
  title: string;
  type: SearchResultType;
  updatedAt: Date;
}

export interface AgentSearchResult extends BaseSearchResult {
  avatar: string | null;
  backgroundColor: string | null;
  slug: string | null;
  tags: string[];
  type: 'agent';
}

export interface AssistantSearchResult extends BaseSearchResult {
  author: string;
  avatar?: string | null;
  homepage?: string | null;
  identifier: string;
  tags?: string[] | null;
  type: 'communityAgent';
}

export interface ChatGroupSearchResult extends BaseSearchResult {
  avatar: string | null;
  backgroundColor: string | null;
  type: 'chatGroup';
}

export interface SearchFileResult extends BaseSearchResult {
  fileType: string;
  knowledgeBaseId: string | null;
  name: string;
  size: number;
  type: 'file';
  url: string | null;
}

export interface FolderSearchResult extends BaseSearchResult {
  knowledgeBaseId: string | null;
  slug: string | null;
  type: 'folder';
}

export interface KnowledgeBaseSearchResult extends BaseSearchResult {
  avatar: string | null;
  type: 'knowledgeBase';
}

export interface MCPSearchResult extends BaseSearchResult {
  author: string;
  avatar?: string | null;
  category?: string | null;
  connectionType?: 'http' | 'stdio' | null;
  identifier: string;
  installCount?: number | null;
  isFeatured?: boolean | null;
  isValidated?: boolean | null;
  tags?: string[] | null;
  type: 'mcp';
}

export interface MemorySearchResult extends BaseSearchResult {
  memoryLayer: string | null;
  type: 'memory';
}

export interface MessageSearchResult extends BaseSearchResult {
  agentId: string | null;
  content: string;
  model: string | null;
  role: string;
  topicId: string | null;
  type: 'message';
}

export interface PageContentSearchResult extends BaseSearchResult {
  type: 'pageContent';
}

export interface PageSearchResult extends BaseSearchResult {
  type: 'page';
}

export interface PluginSearchResult extends BaseSearchResult {
  author: string;
  avatar?: string | null;
  category?: string | null;
  identifier: string;
  tags?: string[] | null;
  type: 'plugin';
}

export interface TopicSearchResult extends BaseSearchResult {
  agent: {
    avatar: string | null;
    backgroundColor: string | null;
    title: string | null;
  } | null;
  agentId: string | null;
  favorite: boolean | null;
  sessionId: string | null;
  type: 'topic';
}

export type SearchResult =
  | AgentSearchResult
  | AssistantSearchResult
  | ChatGroupSearchResult
  | SearchFileResult
  | FolderSearchResult
  | KnowledgeBaseSearchResult
  | MCPSearchResult
  | MemorySearchResult
  | MessageSearchResult
  | PageContentSearchResult
  | PageSearchResult
  | PluginSearchResult
  | TopicSearchResult;

export const ImageCitationItemSchema = z.object({
  domain: z.string().optional(),
  imageUri: z.string().optional(),
  sourceUri: z.string().optional(),
  title: z.string().optional(),
});

export const GroundingSearchSchema = z.object({
  citations: z
    .array(
      z.object({
        favicon: z.string().optional(),
        id: z.string().optional(),
        title: z.string().optional(),
        url: z.string(),
      }),
    )
    .optional(),
  imageResults: z.array(ImageCitationItemSchema).optional(),
  imageSearchQueries: z.array(z.string()).optional(),
  searchQueries: z.array(z.string()).optional(),
});
