import { BUILTIN_AGENT_SLUGS } from '@lobechat/builtin-agents';
import {
  type UpdateDocumentArgs,
  WebOnboardingApiName,
  WebOnboardingIdentifier,
} from '@lobechat/builtin-tools';
import {
  createDocumentReadResult,
  createWebOnboardingToolResult,
} from '@lobechat/builtin-tools/webOnboardingUtils';
import { type BuiltinToolContext, type BuiltinToolResult } from '@lobechat/types';
import { BaseExecutor } from '@lobechat/types';

import { RestClientError } from '@/libs/rest';
import { userService } from '@/services/user';
import { useAgentStore } from '@/store/agent';
import { useUserStore } from '@/store/user';

const syncUserOnboardingState = async () => {
  try {
    await useUserStore.getState().refreshUserState();
  } catch (error) {
    console.error(error);
  }
};

const getStructuredPatchError = (error: unknown) => {
  if (!(error instanceof RestClientError)) return;

  const detail = error.meta?.detail;
  if (!detail || typeof detail !== 'object' || !('error' in detail)) return;

  const patchError = (detail as { error?: unknown }).error;
  if (!patchError || typeof patchError !== 'object') return;

  const detailContent = (detail as { content?: unknown }).content;
  const content = typeof detailContent === 'string' ? detailContent : error.message;
  const type =
    typeof (patchError as { code?: unknown }).code === 'string'
      ? (patchError as { code: string }).code
      : error.code || 'MarkdownPatchError';

  return { content, patchError, type };
};

class WebOnboardingExecutor extends BaseExecutor<typeof WebOnboardingApiName> {
  readonly identifier = WebOnboardingIdentifier;
  protected readonly apiEnum = WebOnboardingApiName;

  saveUserQuestion = async (
    params: Parameters<typeof userService.saveUserQuestion>[0],
    _ctx: BuiltinToolContext,
  ): Promise<BuiltinToolResult> => {
    const result = await userService.saveUserQuestion(params);
    await Promise.all([
      syncUserOnboardingState(),
      useAgentStore.getState().refreshBuiltinAgent(BUILTIN_AGENT_SLUGS.webOnboarding),
      useAgentStore.getState().refreshBuiltinAgent(BUILTIN_AGENT_SLUGS.inbox),
    ]);

    return createWebOnboardingToolResult(result);
  };

  finishOnboarding = async (_params: Record<string, never>, _ctx: BuiltinToolContext) => {
    const result = await userService.finishOnboarding();
    await syncUserOnboardingState();

    return createWebOnboardingToolResult(result);
  };

  readDocument = async (params: { type: 'soul' | 'persona' }): Promise<BuiltinToolResult> => {
    const result = await userService.readOnboardingDocument(params.type);

    return createDocumentReadResult(params.type, result.content, result.id);
  };

  writeDocument = async (
    params: { content: string; type: 'soul' | 'persona' },
    _ctx: BuiltinToolContext,
  ): Promise<BuiltinToolResult> => {
    const result = await userService.updateOnboardingDocument(params.type, params.content);

    if (!result.id) {
      return { content: `Failed to write ${params.type} document.`, success: false };
    }

    return {
      content: `Wrote ${params.type} document (${result.id}).`,
      state: { id: result.id, type: params.type },
      success: true,
    };
  };

  updateDocument = async (
    params: UpdateDocumentArgs,
    _ctx: BuiltinToolContext,
  ): Promise<BuiltinToolResult> => {
    try {
      const result = await userService.patchOnboardingDocument(params.type, params.hunks);

      if (!result.id) {
        return { content: `Failed to update ${params.type} document.`, success: false };
      }

      return {
        content: `Updated ${params.type} document (${result.id}). Applied ${result.applied} hunk(s).`,
        state: { applied: result.applied, id: result.id, type: params.type },
        success: true,
      };
    } catch (error) {
      const structuredError = getStructuredPatchError(error);
      if (structuredError) {
        return {
          content: structuredError.content,
          error: {
            body: structuredError.patchError,
            message: structuredError.content,
            type: structuredError.type,
          },
          state: { error: structuredError.patchError, type: params.type },
          success: false,
        };
      }

      const message = error instanceof Error ? error.message : String(error);
      return {
        content: message,
        error: { message, type: 'MarkdownPatchError' },
        state: { type: params.type },
        success: false,
      };
    }
  };
}

export const webOnboardingExecutor = new WebOnboardingExecutor();
