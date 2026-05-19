import * as Icons from '@lobehub/ui/icons';
import type { FC } from 'react';
import { createElement } from 'react';

/** Known icon names from @lobehub/ui/icons that correspond to chat platforms. */
const ICON_NAMES = [
  'Discord',
  'GoogleChat',
  'Lark',
  'Line',
  'MicrosoftTeams',
  'QQ',
  'Slack',
  'Telegram',
  'WeChat',
  'WhatsApp',
] as const;

const normalizeIconKey = (value: string) => value.toLowerCase().replaceAll(/[^a-z0-9]/g, '');

/** Alias map for platforms whose display name differs from the icon name. */
const ICON_ALIASES: Record<string, string> = {
  ciscowebex: 'webex',
  feishu: 'Lark',
  teams: 'MicrosoftTeams',
};

const WebexIcon: FC<any> = ({ size = '1em', style, ...rest }) =>
  createElement(
    'svg',
    {
      fill: 'none',
      height: size,
      style: { flex: 'none', lineHeight: 1, ...style },
      viewBox: '0 0 24 24',
      width: size,
      xmlns: 'http://www.w3.org/2000/svg',
      ...rest,
    },
    createElement('title', null, 'Cisco Webex'),
    createElement('ellipse', {
      cx: 8.6,
      cy: 12,
      rx: 5.2,
      ry: 7.2,
      stroke: '#00BCEB',
      strokeLinecap: 'round',
      strokeWidth: 3,
      transform: 'rotate(-34 8.6 12)',
    }),
    createElement('ellipse', {
      cx: 15.4,
      cy: 12,
      rx: 5.2,
      ry: 7.2,
      stroke: '#42B883',
      strokeLinecap: 'round',
      strokeWidth: 3,
      transform: 'rotate(34 15.4 12)',
    }),
  );

const ICON_FALLBACKS: Record<string, FC<any>> = {
  webex: WebexIcon,
};

/**
 * Resolve icon component by matching against known icon names.
 * Accepts either a platform display name (e.g. "Feishu / Lark") or id (e.g. "discord").
 */
export function getPlatformIcon(nameOrId: string): FC<any> | undefined {
  const normalized = normalizeIconKey(nameOrId);

  const alias = ICON_ALIASES[normalized];
  if (alias) return ICON_FALLBACKS[alias] ?? (Icons as Record<string, any>)[alias];

  const fallback = ICON_FALLBACKS[normalized];
  if (fallback) return fallback;

  const name = ICON_NAMES.find((n) => normalized.includes(normalizeIconKey(n)));
  return name ? (Icons as Record<string, any>)[name] : undefined;
}
