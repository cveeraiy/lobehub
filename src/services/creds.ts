import type { UserCredSummary } from '@lobechat/types';

import { restClient } from '@/libs/rest';

interface CredMutationParams {
  description?: string;
  fileHashId?: string;
  fileName?: string;
  key?: string;
  name?: string;
  oauthConnectionId?: number;
  type?: string;
  values?: Record<string, string>;
}

interface InjectCredParams {
  keys: string[];
  sandbox?: boolean;
  topicId?: string;
  userId?: string;
}

interface InjectForSkillParams {
  sandbox?: boolean;
  skillIdentifier: string;
}

const toSnakeBody = (params: CredMutationParams) => ({
  description: params.description,
  file_hash_id: params.fileHashId,
  file_name: params.fileName,
  key: params.key,
  name: params.name,
  oauth_connection_id: params.oauthConnectionId,
  type: params.type,
  values: params.values,
});

class CredsService {
  createFile = async (params: CredMutationParams) => {
    return restClient.post('/market/creds/file', { body: toSnakeBody(params) });
  };

  createKV = async (params: CredMutationParams) => {
    return restClient.post('/market/creds/kv', { body: toSnakeBody(params) });
  };

  createOAuth = async (params: CredMutationParams) => {
    return restClient.post('/market/creds/oauth', { body: toSnakeBody(params) });
  };

  delete = async (id: number): Promise<void> => {
    await restClient.delete(`/market/creds/${id}`);
  };

  deleteByKey = async (key: string): Promise<void> => {
    await restClient.delete(`/market/creds/by-key/${encodeURIComponent(key)}`);
  };

  get = async (id: number, params?: { decrypt?: boolean }) => {
    return restClient.get(`/market/creds/${id}`, { params });
  };

  getByKey = async (key: string, params?: { decrypt?: boolean }) => {
    return restClient.get(`/market/creds/by-key/${encodeURIComponent(key)}`, { params });
  };

  getSkillCredStatus = async (skillIdentifier: string) => {
    return restClient.get('/market/creds/skill-status', { params: { keys: skillIdentifier } });
  };

  inject = async (params: InjectCredParams) => {
    return restClient.post('/market/creds/inject', { body: params });
  };

  injectForSkill = async (params: InjectForSkillParams) => {
    return restClient.post('/market/creds/inject-for-skill', { body: params });
  };

  list = async (): Promise<{ data: UserCredSummary[] }> => {
    return restClient.get('/market/creds/list');
  };

  listOAuthConnections = async () => {
    return restClient.get<{ connections: unknown[] }>('/market/creds/oauth-connections');
  };

  update = async (id: number, params: CredMutationParams) => {
    return restClient.put(`/market/creds/${id}`, { body: toSnakeBody(params) });
  };

  uploadFile = async (params: { file: string; fileName: string; fileType?: string }) => {
    return restClient.post<{ fileHashId: string; fileName: string }>('/market/creds/upload', {
      body: {
        file: params.file,
        file_name: params.fileName,
        file_type: params.fileType,
      },
    });
  };
}

export const credsService = new CredsService();
