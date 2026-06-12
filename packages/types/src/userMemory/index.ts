export * from './actionSchemas';
export * from './activity';
export * from './base';
export * from './experience';
export * from './identity';
export * from './layers';
export * from './list';
export * from './shared';
export * from './tools';
export * from './trace';

export interface MemorySource {
  agentId: string | null;
  id: string;
  sessionId: string | null;
  title: string | null;
}

export interface UserMemoryBase {
  capturedAt?: Date | string;
  createdAt?: Date | string;
  id: string;
  metadata?: Record<string, unknown> | null;
  source?: MemorySource | null;
  tags?: string[] | null;
  title?: string | null;
  type?: string | null;
  updatedAt?: Date | string;
  userMemoryId?: string | null;
}

export interface DisplayPreferenceMemory extends UserMemoryBase {
  conclusionDirectives?: string | null;
  scorePriority?: number | null;
  suggestions?: string | null;
}

export interface DisplayContextMemory extends UserMemoryBase {
  associatedObjects?: Array<Record<string, unknown>> | null;
  associatedSubjects?: Array<Record<string, unknown>> | null;
  currentStatus?: string | null;
  description?: string | null;
  scoreImpact?: number | null;
  scoreUrgency?: number | null;
}

export interface AddIdentityEntryResult {
  identityId: string;
  userMemoryId: string;
}

export interface QueryTagsResult {
  count: number;
  tag: string;
}

export interface QueryIdentityRolesResult {
  roles: Array<{ count: number; role: string }>;
  tags: QueryTagsResult[];
}
