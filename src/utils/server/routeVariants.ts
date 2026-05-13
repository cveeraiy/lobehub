import { type DynamicLayoutProps } from '@/types/next';

export { LOBE_LOCALE_COOKIE } from '@/const/locale';

export const DEFAULT_LANG = 'en-US';

export const locales = [
  'ar',
  'bg-BG',
  'de-DE',
  'en-US',
  'es-ES',
  'fr-FR',
  'ja-JP',
  'ko-KR',
  'pt-BR',
  'ru-RU',
  'tr-TR',
  'zh-CN',
  'zh-TW',
  'vi-VN',
  'fa-IR',
  'it-IT',
  'pl-PL',
  'nl-NL',
] as const;

export type Locales = (typeof locales)[number];

export interface IRouteVariants {
  isMobile: boolean;
  locale: Locales;
  neutralColor?: string;
  primaryColor?: string;
}

export const DEFAULT_VARIANTS: IRouteVariants = {
  isMobile: false,
  locale: DEFAULT_LANG,
};

const SPLITTER = '__';

class RouteVariantsBase {
  static serializeVariants = (variants: IRouteVariants): string =>
    [variants.locale, Number(variants.isMobile)].join(SPLITTER);

  static deserializeVariants = (serialized: string): IRouteVariants => {
    try {
      const [locale, isMobile] = serialized.split(SPLITTER);
      return {
        isMobile: isMobile === '1',
        locale: RouteVariantsBase.isValidLocale(locale)
          ? (locale as Locales)
          : DEFAULT_VARIANTS.locale,
      };
    } catch {
      return { ...DEFAULT_VARIANTS };
    }
  };

  static createVariants = (options: Partial<IRouteVariants> = {}): IRouteVariants => ({
    ...DEFAULT_VARIANTS,
    ...options,
  });

  private static isValidLocale = (locale: string): boolean => locales.includes(locale as any);
}

class NextRouteVariants extends RouteVariantsBase {
  static getVariantsFromProps = async (props: DynamicLayoutProps) => {
    const { variants } = await props.params;
    return super.deserializeVariants(variants);
  };
  static getIsMobile = async (props: DynamicLayoutProps) => {
    const { variants } = await props.params;
    const { isMobile } = super.deserializeVariants(variants);
    return isMobile;
  };
  static getLocale = async (props: DynamicLayoutProps) => {
    const { variants } = await props.params;
    const { locale } = super.deserializeVariants(variants);
    return locale;
  };
}

export { NextRouteVariants as RouteVariants };
