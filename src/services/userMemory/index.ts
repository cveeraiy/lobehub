import {
  type ActivityMemoryItemSchema,
  type AddIdentityActionSchema,
  type ContextMemoryItemSchema,
  type ExperienceMemoryItemSchema,
  type PreferenceMemoryItemSchema,
  type RemoveIdentityActionSchema,
  type UpdateIdentityActionSchema,
} from '@lobechat/memory-user-memory/schemas';
import {
  type ActivityListParams,
  type ActivityListResult,
  type AddActivityMemoryResult,
  type AddContextMemoryResult,
  type AddExperienceMemoryResult,
  type AddIdentityMemoryResult,
  type AddPreferenceMemoryResult,
  type ExperienceListParams,
  type ExperienceListResult,
  type IdentityListParams,
  type IdentityListResult,
  type LayersEnum,
  type QueryTaxonomyOptionsParams,
  type QueryTaxonomyOptionsResult,
  type RemoveIdentityMemoryResult,
  type SearchMemoryParams,
  type SearchMemoryResult,
  type TypesEnum,
  type UpdateIdentityMemoryResult,
} from '@lobechat/types';
import { type z } from 'zod';

import { restClient } from '@/libs/rest';
import type { PersonaData } from '@/store/userMemory/initialState';
import type { IdentityForInjection } from '@/store/userMemory/types';
import type { QueryIdentityRolesResult, QueryTagsResult } from '@/types/userMemory';

class UserMemoryService {
  addActivityMemory = async (
    params: z.infer<typeof ActivityMemoryItemSchema>,
  ): Promise<AddActivityMemoryResult> => {
    return restClient.post('/user-memory/add-activity', { body: params });
  };

  addContextMemory = async (
    params: z.infer<typeof ContextMemoryItemSchema>,
  ): Promise<AddContextMemoryResult> => {
    return restClient.post('/user-memory/add-context', { body: params });
  };

  addExperienceMemory = async (
    params: z.infer<typeof ExperienceMemoryItemSchema>,
  ): Promise<AddExperienceMemoryResult> => {
    return restClient.post('/user-memory/add-experience', { body: params });
  };

  addIdentityMemory = async (
    params: z.infer<typeof AddIdentityActionSchema>,
  ): Promise<AddIdentityMemoryResult> => {
    return restClient.post('/user-memory/add-identity', { body: params });
  };

  addPreferenceMemory = async (
    params: z.infer<typeof PreferenceMemoryItemSchema>,
  ): Promise<AddPreferenceMemoryResult> => {
    return restClient.post('/user-memory/add-preference', { body: params });
  };

  removeIdentityMemory = async (
    params: z.infer<typeof RemoveIdentityActionSchema>,
  ): Promise<RemoveIdentityMemoryResult> => {
    return restClient.post('/user-memory/remove-identity', { body: params });
  };

  getMemoryDetail = async (params: { id: string; layer: LayersEnum }): Promise<any> => {
    return restClient.get(`/user-memory/${params.id}`, {
      params: { layer: params.layer } as any,
    });
  };

  getPersona = async (): Promise<PersonaData | null> => {
    return restClient.get('/user-memory/persona');
  };

  queryExperiences = async (params?: ExperienceListParams): Promise<ExperienceListResult> => {
    return restClient.get('/user-memory/query/experiences', { params: params as any });
  };

  queryActivities = async (params?: ActivityListParams): Promise<ActivityListResult> => {
    return restClient.get('/user-memory/query/activities', { params: params as any });
  };

  queryIdentities = async (params?: IdentityListParams): Promise<IdentityListResult> => {
    return restClient.get('/user-memory/query/identities', { params: params as any });
  };

  retrieveMemory = async (params: SearchMemoryParams): Promise<SearchMemoryResult> => {
    return restClient.post('/user-memory/search', { body: params });
  };

  retrieveMemoryForTopic = async (topicId: string): Promise<SearchMemoryResult> => {
    return restClient.get('/user-memory/retrieve-for-topic', {
      params: { topicId } as any,
    });
  };

  searchMemory = async (params: SearchMemoryParams): Promise<SearchMemoryResult> => {
    return restClient.post('/user-memory/search', { body: params });
  };

  queryTags = async (params?: {
    layers?: LayersEnum[];
    page?: number;
    size?: number;
  }): Promise<QueryTagsResult[]> => {
    return restClient.get('/user-memory/tags', { params: params as any });
  };

  queryIdentityRoles = async (params?: {
    page?: number;
    size?: number;
  }): Promise<QueryIdentityRolesResult> => {
    return restClient.get('/user-memory/identity-roles', { params: params as any });
  };

  queryTaxonomyOptions = async (
    params?: QueryTaxonomyOptionsParams,
  ): Promise<QueryTaxonomyOptionsResult> => {
    return restClient.get('/user-memory/taxonomy-options', { params: params as any });
  };

  queryIdentitiesForInjection = async (params?: {
    limit?: number;
  }): Promise<IdentityForInjection[]> => {
    return restClient.get('/user-memory/identities-for-injection', { params: params as any });
  };

  queryMemories = async (params?: {
    categories?: string[];
    layer?: LayersEnum;
    order?: 'asc' | 'desc';
    page?: number;
    pageSize?: number;
    q?: string;
    sort?:
      | 'capturedAt'
      | 'scoreConfidence'
      | 'scoreImpact'
      | 'scorePriority'
      | 'scoreUrgency'
      | 'startsAt';
    status?: string[];
    tags?: string[];
    types?: TypesEnum[];
  }) => {
    return restClient.get('/user-memory', { params: params as any });
  };

  updateIdentityMemory = async (
    params: z.infer<typeof UpdateIdentityActionSchema>,
  ): Promise<UpdateIdentityMemoryResult> => {
    return restClient.post('/user-memory/update-identity', { body: params });
  };
}

export const userMemoryService = new UserMemoryService();
export { memoryCRUDService } from './crud';
export { memoryExtractionService } from './extraction';
