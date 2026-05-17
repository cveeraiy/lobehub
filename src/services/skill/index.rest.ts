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

class AgentSkillService {
  // ===== Create =====

  async createSkill(params: CreateSkillInput): Promise<SkillItem | undefined> {
    return restClient.post('/skills', { body: params });
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
    return restClient.get(`/skills/${id}`);
  }

  async getZipUrl(id: string): Promise<{ name: string; url: string | null }> {
    return restClient.get(`/skills/${id}/zip-url`);
  }

  async getByIdentifier(identifier: string): Promise<SkillItem | undefined> {
    return restClient.get('/skills/by-identifier', { params: { identifier } });
  }

  async getByName(name: string): Promise<SkillItem | undefined> {
    return restClient.get('/skills/by-name', { params: { name } });
  }

  async list(source?: SkillSource): Promise<{ data: SkillListItem[]; total: number }> {
    return restClient.get('/skills', { params: source ? { source } : undefined });
  }

  async search(query: string): Promise<{ data: SkillListItem[]; total: number }> {
    return restClient.get('/skills/search', { params: { query } });
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
    return restClient.put<SkillItem>(`/skills/${params.id}`, {
      body: { content: params.content, manifest: params.manifest },
    });
  }

  // ===== Delete =====

  async deleteSkill(id: string): Promise<{ success: boolean }> {
    return restClient.delete(`/skills/${id}`);
  }
}

export const agentSkillService = new AgentSkillService();
