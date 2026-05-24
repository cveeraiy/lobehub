import { type NewUserMemoryIdentity } from '@lobechat/types';

import { restClient } from '@/libs/rest';
import type { AddIdentityEntryResult } from '@/types/userMemory';

class MemoryCRUDService {
  // ============ Identity CRUD ============

  deleteAll = async () => {
    return restClient.delete('/user-memory');
  };

  createIdentity = async (data: NewUserMemoryIdentity): Promise<AddIdentityEntryResult> => {
    return restClient.post('/user-memory/identities', { body: data });
  };

  deleteIdentity = async (id: string) => {
    return restClient.delete(`/user-memory/identities/${id}`);
  };

  getIdentities = async () => {
    return restClient.get('/user-memory/identities');
  };

  updateIdentity = async (id: string, data: Partial<NewUserMemoryIdentity>): Promise<boolean> => {
    return restClient.put(`/user-memory/identities/${id}`, { body: data });
  };

  // ============ Context CRUD ============

  deleteContext = async (id: string) => {
    return restClient.delete(`/user-memory/contexts/${id}`);
  };

  getContexts = async () => {
    return restClient.get('/user-memory/contexts');
  };

  updateContext = async (
    id: string,
    data: { currentStatus?: string; description?: string; title?: string },
  ) => {
    return restClient.put(`/user-memory/contexts/${id}`, { body: data });
  };

  // ============ Activity CRUD ============

  deleteActivity = async (id: string) => {
    return restClient.delete(`/user-memory/activities/${id}`);
  };

  getActivities = async () => {
    return restClient.get('/user-memory/activities');
  };

  updateActivity = async (
    id: string,
    data: { narrative?: string; notes?: string; status?: string },
  ) => {
    return restClient.put(`/user-memory/activities/${id}`, { body: data });
  };

  // ============ Experience CRUD ============

  deleteExperience = async (id: string) => {
    return restClient.delete(`/user-memory/experiences/${id}`);
  };

  getExperiences = async () => {
    return restClient.get('/user-memory/experiences');
  };

  updateExperience = async (
    id: string,
    data: { action?: string; keyLearning?: string; situation?: string },
  ) => {
    return restClient.put(`/user-memory/experiences/${id}`, { body: data });
  };

  // ============ Preference CRUD ============

  deletePreference = async (id: string) => {
    return restClient.delete(`/user-memory/preferences/${id}`);
  };

  getPreferences = async () => {
    return restClient.get('/user-memory/preferences');
  };

  updatePreference = async (
    id: string,
    data: { conclusionDirectives?: string; suggestions?: string },
  ) => {
    return restClient.put(`/user-memory/preferences/${id}`, { body: data });
  };
}

export const memoryCRUDService = new MemoryCRUDService();
