import type {
  CheckpointConfig,
  TaskAutomationMode,
  TaskDetailData,
  TaskItem,
  TaskListItem,
  TaskStatus,
} from '@lobechat/types';

import type { RestApiResponse } from '@/libs/rest';
import { restClient } from '@/libs/rest';

const TASK_STATUS_ALIAS_MAP = {
  cancelled: 'canceled',
  done: 'completed',
  in_progress: 'running',
  pending: 'backlog',
} as const satisfies Partial<Record<string, TaskStatus>>;

const REST_STATUS_FILTER_ALIASES = {
  backlog: ['pending'],
  canceled: ['cancelled'],
  completed: ['done'],
  running: ['in_progress'],
} as const satisfies Partial<Record<TaskStatus, string[]>>;

const normalizeTaskStatus = (status: string): string =>
  (TASK_STATUS_ALIAS_MAP as Partial<Record<string, TaskStatus>>)[status] ?? status;

const expandRestStatusFilters = (statuses: string[]): string[] => [
  ...new Set(
    statuses.flatMap((status) => [
      status,
      ...((REST_STATUS_FILTER_ALIASES as Partial<Record<TaskStatus, string[]>>)[
        status as TaskStatus
      ] ?? []),
    ]),
  ),
];

interface TaskApiResponse<T> extends RestApiResponse<T> {
  data: T;
}

interface TaskListApiResponse<T> extends TaskApiResponse<T> {
  total: number;
}

const toTaskListParams = (params: {
  assigneeAgentId?: string;
  limit?: number;
  offset?: number;
  parentIdentifier?: string;
  parentTaskId?: string | null;
  priorities?: number[];
  statuses?: TaskStatus[];
}) => ({
  assigneeAgentId: params.assigneeAgentId,
  limit: params.limit,
  offset: params.offset,
  parentIdentifier: params.parentIdentifier,
  parentTaskId: params.parentTaskId ?? undefined,
  priorities: params.priorities?.join(','),
  statuses: params.statuses ? expandRestStatusFilters(params.statuses).join(',') : undefined,
});

interface TaskGroupItem {
  hasMore: boolean;
  key: string;
  limit: number;
  offset: number;
  tasks: TaskItem[];
  total: number;
}

interface TaskReviewConfig {
  autoRetry?: boolean;
  enabled: boolean;
  judge?: {
    model?: string;
    provider?: string;
  };
  maxIterations?: number;
  rubrics: Array<{
    config: Record<string, unknown>;
    extractor?: Record<string, unknown>;
    id: string;
    name: string;
    threshold?: number;
    type: string;
    weight?: number;
  }>;
}

type RawTaskGroupMap = Record<
  string,
  {
    hasMore?: boolean;
    limit?: number;
    offset?: number;
    tasks: TaskItem[];
    total: number;
  }
>;

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === 'object' && !Array.isArray(value);

const isTaskLike = (value: Record<string, unknown>): boolean =>
  'identifier' in value ||
  'parentTaskId' in value ||
  'sortOrder' in value ||
  'subtasks' in value ||
  'children' in value;

const normalizeTaskPayload = <T>(value: T): T => {
  if (Array.isArray(value)) return value.map((item) => normalizeTaskPayload(item)) as T;

  if (!isRecord(value)) return value;

  const normalized: Record<string, unknown> = { ...value };

  if (typeof normalized.status === 'string' && isTaskLike(normalized)) {
    normalized.status = normalizeTaskStatus(normalized.status);
  }

  for (const [key, child] of Object.entries(normalized)) {
    if (isRecord(child) || Array.isArray(child)) {
      normalized[key] = normalizeTaskPayload(child);
    }
  }

  return normalized as T;
};

const normalizeTaskEnvelope = <T>(value: T | TaskApiResponse<T>): TaskApiResponse<T> => {
  const response = isRecord(value) && 'success' in value ? value : { data: value, success: true };

  return normalizeTaskPayload(response) as TaskApiResponse<T>;
};

const normalizeGroupListResponse = (
  response: RestApiResponse<TaskGroupItem[] | RawTaskGroupMap>,
  groups: Array<{ key: string; limit?: number; offset?: number }>,
): TaskApiResponse<TaskGroupItem[]> => {
  if (Array.isArray(response.data)) {
    return normalizeTaskPayload(response as TaskApiResponse<TaskGroupItem[]>);
  }

  const rawGroups = response.data ?? {};
  const data = groups.map((group) => {
    const raw = rawGroups[group.key] ?? { tasks: [], total: 0 };
    const limit = raw.limit ?? group.limit ?? 50;
    const offset = raw.offset ?? group.offset ?? 0;
    const tasks = raw.tasks ?? [];

    return {
      hasMore: raw.hasMore ?? offset + tasks.length < raw.total,
      key: group.key,
      limit,
      offset,
      tasks,
      total: raw.total,
    };
  });

  return normalizeTaskPayload({ ...response, data });
};

class TaskService {
  // ── Queries ──

  find = async (id: string): Promise<TaskApiResponse<TaskItem>> =>
    normalizeTaskEnvelope(
      await restClient.get<TaskItem | TaskApiResponse<TaskItem>>(`/tasks/${id}`),
    );

  getDetail = async (id: string): Promise<TaskApiResponse<TaskDetailData>> =>
    normalizeTaskEnvelope(
      await restClient.get<TaskDetailData | TaskApiResponse<TaskDetailData>>(`/tasks/${id}/detail`),
    );

  list = async (params: {
    assigneeAgentId?: string;
    limit?: number;
    offset?: number;
    parentIdentifier?: string;
    parentTaskId?: string | null;
    priorities?: number[];
    statuses?: TaskStatus[];
  }): Promise<TaskListApiResponse<TaskListItem[]>> =>
    normalizeTaskPayload(
      await restClient.get<TaskListApiResponse<TaskListItem[]>>('/tasks', {
        params: toTaskListParams(params),
      }),
    );

  groupList = async (params: {
    assigneeAgentId?: string;
    groups: Array<{
      key: string;
      limit?: number;
      offset?: number;
      statuses: string[];
    }>;
    parentTaskId?: string | null;
  }): Promise<TaskApiResponse<TaskGroupItem[]>> => {
    const response = await restClient.post<RestApiResponse<TaskGroupItem[] | RawTaskGroupMap>>(
      '/tasks/group-list',
      {
        body: {
          ...params,
          groups: params.groups.map((group) => ({
            ...group,
            statuses: expandRestStatusFilters(group.statuses),
          })),
        },
      },
    );

    return normalizeGroupListResponse(response, params.groups);
  };

  getSubtasks = async (id: string): Promise<TaskApiResponse<TaskItem[]>> =>
    normalizeTaskEnvelope(
      await restClient.get<TaskItem[] | TaskApiResponse<TaskItem[]>>(`/tasks/${id}/subtasks`),
    );

  getTaskTree = async (id: string): Promise<TaskApiResponse<TaskDetailData>> =>
    normalizeTaskEnvelope(
      await restClient.get<TaskDetailData | TaskApiResponse<TaskDetailData>>(`/tasks/${id}/tree`),
    );

  getTopics = async (id: string) => restClient.get(`/tasks/${id}/topics`);

  getDependencies = async (id: string) => restClient.get(`/tasks/${id}/dependencies`);

  getPinnedDocuments = async (id: string) => restClient.get(`/tasks/${id}/pinned-documents`);

  getCheckpoint = async (id: string) => restClient.get(`/tasks/${id}/checkpoint`);

  getReview = async (id: string) => restClient.get(`/tasks/${id}/review`);

  // ── Mutations ──

  create = async (params: {
    assigneeAgentId?: string;
    assigneeUserId?: string;
    createdByAgentId?: string;
    description?: string;
    identifierPrefix?: string;
    instruction: string;
    name?: string;
    parentTaskId?: string;
    priority?: number;
  }): Promise<TaskApiResponse<TaskItem>> =>
    normalizeTaskEnvelope(
      await restClient.post<TaskItem | TaskApiResponse<TaskItem>>('/tasks', { body: params }),
    );

  update = async (
    id: string,
    data: {
      assigneeAgentId?: string | null;
      assigneeUserId?: string | null;
      automationMode?: TaskAutomationMode | null;
      config?: Record<string, unknown>;
      context?: Record<string, unknown>;
      description?: string;
      heartbeatInterval?: number;
      heartbeatTimeout?: number | null;
      instruction?: string;
      name?: string;
      priority?: number;
      schedulePattern?: string | null;
      scheduleTimezone?: string | null;
    },
  ): Promise<TaskApiResponse<TaskItem | null>> =>
    normalizeTaskEnvelope(
      await restClient.put<TaskApiResponse<TaskItem | null>>(`/tasks/${id}`, { body: data }),
    );

  delete = async (id: string): Promise<RestApiResponse<TaskItem | undefined>> => {
    if (!id) throw new Error('Task id is required');

    await restClient.delete<{ ok: boolean }>(`/tasks/${encodeURIComponent(id)}`);
    return { success: true };
  };

  clearAll = async () => restClient.delete('/tasks');

  updateStatus = async (
    id: string,
    status: TaskStatus,
    error?: string,
  ): Promise<TaskApiResponse<TaskItem | null>> =>
    normalizeTaskPayload(
      await restClient.put<TaskApiResponse<TaskItem | null>>(`/tasks/${id}/status`, {
        body: { error, status },
      }),
    );

  run = async (id: string, params?: { continueTopicId?: string; prompt?: string }) =>
    restClient.post(`/tasks/${id}/run`, { body: params });

  addComment = async (id: string, content: string, opts?: { briefId?: string; topicId?: string }) =>
    restClient.post(`/tasks/${id}/comments`, { body: { content, ...opts } });

  deleteComment = async (commentId: string) => restClient.delete(`/tasks/comments/${commentId}`);

  updateComment = async (commentId: string, content: string) =>
    restClient.put(`/tasks/comments/${commentId}`, { body: { content } });

  addDependency = async (
    taskId: string,
    dependsOnId: string,
    type: 'blocks' | 'relates' = 'blocks',
  ) => restClient.post(`/tasks/${taskId}/dependencies`, { body: { dependsOnId, type } });

  removeDependency = async (taskId: string, dependsOnId: string) =>
    restClient.delete(`/tasks/${taskId}/dependencies/${dependsOnId}`);

  reorderSubtasks = async (id: string, order: string[]) =>
    restClient.put(`/tasks/${id}/subtasks/order`, { body: { order } });

  cancelTopic = async (topicId: string) => restClient.post(`/tasks/topics/${topicId}/cancel`);

  deleteTopic = async (topicId: string) => restClient.delete(`/tasks/topics/${topicId}`);

  updateConfig = async (id: string, config: Record<string, unknown>) =>
    restClient.put(`/tasks/${id}/config`, { body: { config } });

  updateCheckpoint = async (id: string, checkpoint: CheckpointConfig) =>
    restClient.put(`/tasks/${id}/checkpoint`, { body: { checkpoint } });

  updateReview = async (params: { id: string; review: TaskReviewConfig }) =>
    restClient.put(`/tasks/${params.id}/review`, { body: { review: params.review } });

  runReview = async (id: string, params?: { content?: string; topicId?: string }) =>
    restClient.post(`/tasks/${id}/review/run`, { body: params });

  pinDocument = async (taskId: string, documentId: string, pinnedBy?: string) =>
    restClient.post(`/tasks/${taskId}/pinned-documents`, { body: { documentId, pinnedBy } });

  unpinDocument = async (taskId: string, documentId: string) =>
    restClient.delete(`/tasks/${taskId}/pinned-documents/${documentId}`);

  // ── Brief operations ──

  resolveBrief = async (id: string, opts?: { action?: string; comment?: string }) =>
    restClient.post(`/briefs/${id}/resolve`, { body: opts });

  markBriefRead = async (id: string) => restClient.put(`/briefs/${id}/read`);
}

export const taskService = new TaskService();
