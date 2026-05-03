import { DEFAULT_SETTINGS } from '@lobechat/config';
import { type UserSettings } from '@lobechat/types';
import { type PartialDeep } from 'type-fest';

export interface SettingsPermissions {
  agentSettings: boolean;
  systemSettings: boolean;
}

export interface UserSettingsState {
  defaultSettings: UserSettings;
  settings: PartialDeep<UserSettings>;
  settingsPermissions: SettingsPermissions;
  updateSettingsSignal?: AbortController;
}

export const initialSettingsState: UserSettingsState = {
  defaultSettings: DEFAULT_SETTINGS,
  settings: {},
  settingsPermissions: { agentSettings: false, systemSettings: false },
};
