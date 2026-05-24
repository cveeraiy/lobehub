/**
 * User service backed by the Python REST API.
 */
import { type MarkdownPatchHunk } from '@lobechat/builtin-tools';
import { type PartialDeep } from 'type-fest';

import { restClient } from '@/libs/rest';
import {
  type SaveUserQuestionInput,
  type SSOProvider,
  type UserAgentOnboarding,
  type UserAgentOnboardingContext,
  type UserGuide,
  type UserInitializationState,
  type UserOnboarding,
  type UserPreference,
} from '@/types/user';
import { type UserSettings } from '@/types/user/settings';

interface WebOnboardingToolActionResult {
  content?: string;
  error?: {
    message?: string;
    type?: string;
  };
  ignoredFields?: string[];
  savedFields?: string[];
  success: boolean;
  unchangedFields?: string[];
}

const BASE = '/user';

const toRestSettingsBody = (value: PartialDeep<UserSettings>) => ({
  default_agent: value.defaultAgent,
  general: value.general,
  hotkey: value.hotkey,
  image: value.image,
  key_vaults: value.keyVaults,
  language_model: value.languageModel,
  market: value.market,
  memory: value.memory,
  notification: value.notification,
  system_agent: value.systemAgent,
  tool: value.tool,
  tts: value.tts,
});

export class UserService {
  getUserRegistrationDuration = async (): Promise<{
    createdAt: string;
    duration: number;
    updatedAt: string;
  }> => {
    return restClient.get(`${BASE}/registration-duration`);
  };

  getUserState = async (): Promise<UserInitializationState> => {
    return restClient.get(`${BASE}/state`);
  };

  getUserSSOProviders = async (): Promise<SSOProvider[]> => {
    return restClient.get(`${BASE}/sso-providers`);
  };

  // ── Onboarding (agent-driven flow) ────────────────────────────────

  getOrCreateOnboardingState = async (): Promise<{
    agentId: string;
    agentOnboarding: UserAgentOnboarding;
    context: UserAgentOnboardingContext;
    feedbackSubmitted: boolean;
    topicId: string;
  }> => {
    return restClient.get(`${BASE}/onboarding/state`);
  };

  getOnboardingAgentContext = async (): Promise<{
    personaContent: string | null;
    phaseGuidance: string;
    soulContent: string | null;
  }> => {
    return restClient.get(`${BASE}/onboarding/agent-context`);
  };

  saveUserQuestion = async (
    params: SaveUserQuestionInput,
  ): Promise<WebOnboardingToolActionResult> => {
    return restClient.post<WebOnboardingToolActionResult>(`${BASE}/onboarding/save-question`, {
      body: params,
    });
  };

  finishOnboarding = async (): Promise<WebOnboardingToolActionResult> => {
    return restClient.post<WebOnboardingToolActionResult>(`${BASE}/onboarding/finish`);
  };

  readOnboardingDocument = async (type: 'soul' | 'persona') => {
    return restClient.get<{ content: string; id: string | null; type: 'soul' | 'persona' }>(
      `${BASE}/onboarding/document`,
      { params: { type } },
    );
  };

  updateOnboardingDocument = async (type: 'soul' | 'persona', content: string) => {
    return restClient.put<{ id: string; type: 'soul' | 'persona' }>(`${BASE}/onboarding/document`, {
      body: { content, type },
    });
  };

  patchOnboardingDocument = async (type: 'soul' | 'persona', hunks: MarkdownPatchHunk[]) => {
    return restClient.patch<{ applied: number; id: string; type: 'soul' | 'persona' }>(
      `${BASE}/onboarding/document`,
      { body: { hunks, type } },
    );
  };

  makeUserOnboarded = async () => {
    return restClient.post(`${BASE}/onboarded`);
  };

  resetAgentOnboarding = async () => {
    return restClient.post<UserAgentOnboarding>(`${BASE}/agent-onboarding/reset`);
  };

  updateAgentOnboarding = async (agentOnboarding: UserAgentOnboarding) => {
    return restClient.put(`${BASE}/agent-onboarding`, { body: agentOnboarding });
  };

  updateOnboarding = async (onboarding: UserOnboarding) => {
    return restClient.put(`${BASE}/onboarding`, { body: onboarding });
  };

  // ── Profile ───────────────────────────────────────────────────────

  updateAvatar = async (avatar: string) => {
    return restClient.put(`${BASE}/avatar`, { body: { avatar } });
  };

  updateInterests = async (interests: string[]) => {
    return restClient.put(`${BASE}/interests`, { body: { interests } });
  };

  updateFullName = async (fullName: string) => {
    return restClient.put(`${BASE}/fullname`, { body: { fullName } });
  };

  updateUsername = async (username: string) => {
    return restClient.put(`${BASE}/username`, { body: { username } });
  };

  // ── Preference & Guide ────────────────────────────────────────────

  updatePreference = async (preference: Partial<UserPreference>) => {
    return restClient.put(`${BASE}/preference`, { body: preference });
  };

  updateGuide = async (guide: Partial<UserGuide>) => {
    return restClient.put(`${BASE}/guide`, { body: guide });
  };

  // ── Settings ──────────────────────────────────────────────────────

  updateUserSettings = async (value: PartialDeep<UserSettings>, signal?: AbortSignal) => {
    return restClient.put(`${BASE}/settings`, { body: toRestSettingsBody(value), signal });
  };

  resetUserSettings = async () => {
    return restClient.delete(`${BASE}/settings`);
  };
}

export const userService = new UserService();
