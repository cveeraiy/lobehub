import type { CheckpointConfig, TaskAutomationMode, TaskStatus } from '@lobechat/types';

import { restClient } from '@/libs/rest';

class TaskService {
  // ── Queries ──

  find = async (id: string) => restClient.get(`/tasks/${id}`);

  getDetail = async (id: string) => restClient.get(`/tasks/${id}/detail`);

  list = async (params: {
    assigneeAgentId?: string;
    limit?: number;
    offset?: number;
    parentIdentifier?: string;
    parentTaskId?: string | null;
    priorities?: number[];
    statuses?: TaskStatus[];
  }) => restClient.get('/tasks', { params: params as any });

  groupList = async (params: {
    assigneeAgentId?: string;
    groups: Array<{
      key: string;
      limit?: number;
      offset?: number;
      statuses: string[];
    }>;
    parentTaskId?: string | null;
  }) => restClient.post('/tasks/group-list', { body: params });

  getSubtasks = async (id: string) => restClient.get(`/tasks/${id}/subtasks`);

  getTaskTree = async (id: string) => restClient.get(`/tasks/${id}/tree`);

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
  }) => restClient.post('/tasks', { body: params });

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
  ) => restClient.put(`/tasks/${id}`, { body: data });

  delete = async (id: string) => restClient.delete(`/tasks/${id}`);

  clearAll = async () => restClient.delete('/tasks');

  updateStatus = async (id: string, status: TaskStatus, error?: string) =>
    restClient.put(`/tasks/${id}/status`, { body: { error, status } });

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

  updateReview = async (id: string, review: Record<string, unknown>) =>
    restClient.put(`/tasks/${id}/review`, { body: { review } });

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
