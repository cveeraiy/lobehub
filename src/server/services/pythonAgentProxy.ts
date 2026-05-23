/**
 * Python Agent Proxy Service
 *
 * Thin adapter that proxies agent-execution TRPC calls to the Python FastAPI
 * backend while keeping the same interface expected by the TS router layer.
 *
 * Only execution-related operations are proxied; DB-only procedures (Thread
 * CRUD, status queries, client task threads) remain in the TS layer.
 */

import debug from 'debug';

import {
  callPythonBackend,
  callPythonBackendStream,
  isPythonBackendEnabled,
} from '@/server/utils/pythonBackend';

const log = debug('ethos-server:python-agent-proxy');

// ── camelCase → snake_case helpers ────────────────────────────────────
function toSnakeCase(str: string): string {
  return str.replaceAll(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
}

function keysToSnakeCase(obj: unknown): unknown {
  if (obj === null || obj === undefined) return obj;
  if (Array.isArray(obj)) return obj.map(keysToSnakeCase);
  if (typeof obj === 'object') {
    return Object.fromEntries(
      Object.entries(obj as Record<string, unknown>).map(([key, value]) => [
        toSnakeCase(key),
        keysToSnakeCase(value),
      ]),
    );
  }
  return obj;
}

function toCamelCase(str: string): string {
  return str.replaceAll(/_([a-z])/g, (_, letter) => letter.toUpperCase());
}

function keysToCamelCase(obj: unknown): unknown {
  if (obj === null || obj === undefined) return obj;
  if (Array.isArray(obj)) return obj.map(keysToCamelCase);
  if (typeof obj === 'object') {
    return Object.fromEntries(
      Object.entries(obj as Record<string, unknown>).map(([key, value]) => [
        toCamelCase(key),
        keysToCamelCase(value),
      ]),
    );
  }
  return obj;
}

// ── Proxy methods ─────────────────────────────────────────────────────

export interface ExecAgentProxyInput {
  additionalPluginIds?: string[];
  agentId?: string;
  appContext?: Record<string, unknown>;
  autoStart?: boolean;
  botContext?: unknown;
  botPlatformContext?: unknown;
  clientRuntime?: string;
  deviceId?: string;
  discordContext?: unknown;
  existingMessageIds?: string[];
  fileIds?: string[];
  files?: unknown[];
  hooks?: unknown[];
  initialStepCount?: number;
  maxSteps?: number;
  model?: string;
  parentMessageId?: string;
  prompt: string;
  provider?: string;
  queueRetries?: number;
  queueRetryDelay?: number | string;
  resume?: boolean;
  resumeApproval?: Record<string, unknown>;
  signal?: AbortSignal;
  slug?: string;
  taskId?: string;
  title?: string;
  trigger?: string;
  userInterventionConfig?: Record<string, unknown>;
}

export interface ExecGroupAgentProxyInput {
  agentId: string;
  files?: string[];
  groupId: string;
  message: string;
  newTopic?: Record<string, unknown>;
  topicId?: string | null;
}

export interface ExecSubAgentTaskProxyInput {
  agentId: string;
  groupId?: string;
  instruction: string;
  parentMessageId: string;
  timeout?: number;
  title?: string;
  topicId: string;
}

export interface InterruptTaskProxyInput {
  operationId?: string;
  threadId?: string;
}

export class PythonAgentProxyService {
  private userId: string;

  constructor(userId: string) {
    this.userId = userId;
  }

  async execAgent(input: ExecAgentProxyInput): Promise<any> {
    log('proxy execAgent for user %s', this.userId);
    const body = keysToSnakeCase(input);
    const result = await callPythonBackend('/api/ai-agent/exec', this.userId, { body });
    return keysToCamelCase(result);
  }

  async execGroupAgent(input: ExecGroupAgentProxyInput): Promise<any> {
    log('proxy execGroupAgent for user %s', this.userId);
    const body = keysToSnakeCase(input);
    const result = await callPythonBackend('/api/ai-agent/exec-group', this.userId, { body });
    return keysToCamelCase(result);
  }

  async execSubAgentTask(input: ExecSubAgentTaskProxyInput): Promise<any> {
    log('proxy execSubAgentTask for user %s', this.userId);
    const body = keysToSnakeCase(input);
    const result = await callPythonBackend('/api/ai-agent/exec-sub-agent', this.userId, { body });
    return keysToCamelCase(result);
  }

  async interruptTask(input: InterruptTaskProxyInput): Promise<any> {
    log('proxy interruptTask for user %s', this.userId);
    const body = keysToSnakeCase(input);
    const result = await callPythonBackend('/api/ai-agent/interrupt', this.userId, { body });
    return keysToCamelCase(result);
  }

  async streamExecAgent(input: ExecAgentProxyInput, signal?: AbortSignal): Promise<Response> {
    log('proxy streamExecAgent for user %s', this.userId);
    const body = keysToSnakeCase(input);
    return callPythonBackendStream('/api/ai-agent/exec/stream', this.userId, {
      body,
      signal,
    });
  }
}

export { isPythonBackendEnabled };
