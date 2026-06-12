import { DEFAULT_LANG } from '@/const/locale';

import type resources from './default';

export const locales = ['en-US', 'zh-CN', 'zh-TW', 'ja-JP', 'ko-KR', 'fr-FR', 'ar'] as const;

export type DefaultResources = typeof resources;
export type NS = keyof DefaultResources;
export type Locales = (typeof locales)[number];

export const normalizeLocale = (locale?: string): Locales => {
  if (!locale) return DEFAULT_LANG;

  for (const l of locales) {
    if (l.startsWith(locale)) {
      return l;
    }
  }

  return DEFAULT_LANG;
};

type LocaleOptions = {
  label: string;
  value: Locales;
}[];

export const localeOptions: LocaleOptions = [
  {
    label: 'English',
    value: 'en-US',
  },
  {
    label: '简体中文',
    value: 'zh-CN',
  },
  {
    label: '繁體中文',
    value: 'zh-TW',
  },
  {
    label: '日本語',
    value: 'ja-JP',
  },
  {
    label: '한국어',
    value: 'ko-KR',
  },
  {
    label: 'Français',
    value: 'fr-FR',
  },
  {
    label: 'العربية',
    value: 'ar',
  },
] as LocaleOptions;

export const supportLocales: string[] = [...locales, 'en'];
