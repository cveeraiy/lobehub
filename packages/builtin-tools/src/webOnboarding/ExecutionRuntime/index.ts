import type { BuiltinServerRuntimeOutput, SaveUserQuestionInput } from '@lobechat/types';

import type { MarkdownPatchHunk } from '../types';
import { createDocumentReadResult, createWebOnboardingToolResult } from './utils';

export interface WebOnboardingRuntimeService {
  finishOnboarding: () => Promise<{
    content: string;
    finishedAt?: string;
    success: boolean;
  }>;
  patchDocument: (
    type: 'soul' | 'persona',
    hunks: MarkdownPatchHunk[],
  ) => Promise<{
    applied: number;
    id: string | null;
    type: 'soul' | 'persona';
  }>;
  readDocument: (type: 'soul' | 'persona') => Promise<{
    content: string | null;
    id: string | null;
  }>;
  saveUserQuestion: (input: SaveUserQuestionInput) => Promise<{
    content: string;
    ignoredFields?: string[];
    savedFields?: string[];
    success: boolean;
    unchangedFields?: string[];
  }>;
  updateDocument: (
    type: 'soul' | 'persona',
    content: string,
  ) => Promise<{
    id: string | null;
  }>;
}

export class WebOnboardingExecutionRuntime {
  constructor(private service: WebOnboardingRuntimeService) {}

  async saveUserQuestion(params: SaveUserQuestionInput): Promise<BuiltinServerRuntimeOutput> {
    const result = await this.service.saveUserQuestion(params);

    return createWebOnboardingToolResult(result);
  }

  async finishOnboarding(): Promise<BuiltinServerRuntimeOutput> {
    const result = await this.service.finishOnboarding();

    return createWebOnboardingToolResult(result);
  }

  async readDocument(params: { type: 'soul' | 'persona' }): Promise<BuiltinServerRuntimeOutput> {
    const result = await this.service.readDocument(params.type);

    return createDocumentReadResult(params.type, result.content, result.id);
  }

  async writeDocument(params: {
    content: string;
    type: 'soul' | 'persona';
  }): Promise<BuiltinServerRuntimeOutput> {
    const result = await this.service.updateDocument(params.type, params.content);

    if (!result.id) {
      return { content: `Failed to write ${params.type} document.`, success: false };
    }

    return {
      content: `Wrote ${params.type} document (${result.id}).`,
      state: { id: result.id, type: params.type },
      success: true,
    };
  }

  async updateDocument(params: {
    hunks: MarkdownPatchHunk[];
    type: 'soul' | 'persona';
  }): Promise<BuiltinServerRuntimeOutput> {
    const updated = await this.service.patchDocument(params.type, params.hunks);
    if (!updated.id) {
      return { content: `Failed to update ${params.type} document.`, success: false };
    }

    return {
      content: `Updated ${params.type} document (${updated.id}). Applied ${updated.applied} hunk(s).`,
      state: { applied: updated.applied, id: updated.id, type: params.type },
      success: true,
    };
  }
}
