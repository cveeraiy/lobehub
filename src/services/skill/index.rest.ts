import type {
  CreateSkillInput,
  ImportGitHubInput,
  ImportUrlInput,
  ImportZipInput,
  SkillImportResult,
  SkillItem,
  SkillListItem,
  SkillResourceContent,
  SkillResourceTreeNode,
  SkillSource,
  UpdateSkillInput,
} from '@lobechat/types';

import { restClient } from '@/libs/rest';

type RawSkillItem = Partial<
  SkillItem & {
    created_at: Date | string;
    updated_at: Date | string;
    zip_file_hash: string | null;
  }
>;

type RawSkillListResponse =
  | SkillListItem[]
  | {
      data?: RawSkillItem[];
      items?: RawSkillItem[];
      total?: number;
      total_count?: number;
      totalCount?: number;
    };

const toDate = (value: unknown) => {
  if (value instanceof Date) return value;
  if (typeof value === 'string' || typeof value === 'number') return new Date(value);
  return new Date(0);
};

const normalizeSkillItem = (item: RawSkillItem): SkillItem => ({
  content: item.content ?? null,
  createdAt: toDate(item.createdAt ?? item.created_at),
  description: item.description ?? null,
  editorData: item.editorData ?? null,
  id: item.id ?? '',
  identifier: item.identifier ?? '',
  manifest: item.manifest ?? { description: item.description ?? '', name: item.name ?? '' },
  name: item.name ?? item.manifest?.name ?? '',
  resources: item.resources ?? null,
  source: item.source ?? 'user',
  updatedAt: toDate(item.updatedAt ?? item.updated_at),
  zipFileHash: item.zipFileHash ?? item.zip_file_hash ?? null,
});

const normalizeSkillListResponse = (
  response: RawSkillListResponse,
): { data: SkillListItem[]; total: number } => {
  const items = Array.isArray(response) ? response : (response.data ?? response.items ?? []);

  return {
    data: items.map(normalizeSkillItem),
    total: Array.isArray(response)
      ? response.length
      : (response.total ?? response.totalCount ?? response.total_count ?? items.length),
  };
};

class AgentSkillService {
  // ===== Create =====

  async createSkill(params: CreateSkillInput): Promise<SkillItem | undefined> {
    const skill = await restClient.post<RawSkillItem>('/skills', { body: params });
    return skill ? normalizeSkillItem(skill) : undefined;
  }

  // ===== Import =====

  async importFromGitHub(params: ImportGitHubInput): Promise<SkillImportResult | undefined> {
    return restClient.post('/skills/import/github', { body: params });
  }

  async importFromUrl(params: ImportUrlInput): Promise<SkillImportResult | undefined> {
    return restClient.post('/skills/import/url', { body: params });
  }

  async importFromZip(params: ImportZipInput): Promise<SkillImportResult | undefined> {
    return restClient.post('/skills/import/zip', { body: params });
  }

  async importFromMarket(identifier: string): Promise<SkillImportResult | undefined> {
    return restClient.post('/skills/import/market', { body: { identifier } });
  }

  // ===== Query =====

  async getById(id: string): Promise<SkillItem | undefined> {
    const skill = await restClient.get<RawSkillItem>(`/skills/${id}`);
    return skill ? normalizeSkillItem(skill) : undefined;
  }

  async getZipUrl(id: string): Promise<{ name: string; url: string | null }> {
    return restClient.get(`/skills/${id}/zip-url`);
  }

  async getByIdentifier(identifier: string): Promise<SkillItem | undefined> {
    const skill = await restClient.get<RawSkillItem>('/skills/by-identifier', {
      params: { identifier },
    });
    return skill ? normalizeSkillItem(skill) : undefined;
  }

  async getByName(name: string): Promise<SkillItem | undefined> {
    const skill = await restClient.get<RawSkillItem>('/skills/by-name', { params: { name } });
    return skill ? normalizeSkillItem(skill) : undefined;
  }

  async list(source?: SkillSource): Promise<{ data: SkillListItem[]; total: number }> {
    const response = await restClient.get<RawSkillListResponse>('/skills', {
      params: source ? { source } : undefined,
    });
    return normalizeSkillListResponse(response);
  }

  async search(query: string): Promise<{ data: SkillListItem[]; total: number }> {
    const response = await restClient.get<RawSkillListResponse>('/skills/search', {
      params: { query },
    });
    return normalizeSkillListResponse(response);
  }

  // ===== Resources =====

  async listResources(id: string, includeContent?: boolean): Promise<SkillResourceTreeNode[]> {
    return restClient.get(`/skills/${id}/resources`, {
      params: includeContent !== undefined ? { includeContent } : undefined,
    });
  }

  async readResource(id: string, path: string): Promise<SkillResourceContent> {
    return restClient.get(`/skills/${id}/resources/content`, { params: { path } });
  }

  // ===== Update =====

  async updateSkill(params: UpdateSkillInput): Promise<SkillItem> {
    const skill = await restClient.put<RawSkillItem>(`/skills/${params.id}`, {
      body: { content: params.content, manifest: params.manifest },
    });
    return normalizeSkillItem(skill);
  }

  // ===== Delete =====

  async deleteSkill(id: string): Promise<{ success: boolean }> {
    return restClient.delete(`/skills/${id}`);
  }
}

export const agentSkillService = new AgentSkillService();
