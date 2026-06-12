import type { EdgeConfigClient } from '@vercel/edge-config';
import { createClient } from '@vercel/edge-config';
import createDebug from 'debug';

import { appEnv } from '@/envs/app';

const debug = createDebug('lobe-server:edge-config');

export interface BillboardItemLocaleFields {
  description?: string;
  linkLabel?: string;
  title?: string;
}

export interface BillboardItem {
  cover?: null | string;
  description: string;
  i18n?: Record<string, BillboardItemLocaleFields>;
  id: number;
  linkLabel?: null | string;
  linkUrl?: null | string;
  title: string;
}

export interface BillboardLocaleFields {
  title?: string;
}

export interface BillboardSet {
  endAt: string;
  i18n?: Record<string, BillboardLocaleFields>;
  id: number;
  items: BillboardItem[];
  slug: string;
  startAt: string;
  title: string;
}

export type BillboardSnapshot = BillboardSet | null;

export interface EdgeConfigData {
  assistant_blacklist?: string[];
  assistant_whitelist?: string[];
  billboards?: BillboardSnapshot;
  feature_flags?: Record<string, boolean | string[]>;
}

export type EdgeConfigKeys = keyof EdgeConfigData;

export class EdgeConfig {
  get client(): EdgeConfigClient {
    if (!appEnv.VERCEL_EDGE_CONFIG) {
      throw new Error('VERCEL_EDGE_CONFIG is not set');
    }
    return createClient(appEnv.VERCEL_EDGE_CONFIG);
  }

  static isEnabled() {
    const isEnabled = !!appEnv.VERCEL_EDGE_CONFIG;
    debug('VERCEL_EDGE_CONFIG env var: %s', appEnv.VERCEL_EDGE_CONFIG ? 'SET' : 'NOT SET');
    debug('EdgeConfig enabled: %s', isEnabled);
    return isEnabled;
  }

  async getValue<K extends EdgeConfigKeys>(key: K) {
    return this.client.get<EdgeConfigData[K]>(key);
  }

  async getValues<const K extends EdgeConfigKeys>(keys: K[]) {
    return this.client.getAll<Pick<EdgeConfigData, K>>(keys);
  }

  getAgentRestrictions = async () => {
    const { assistant_blacklist: blacklist, assistant_whitelist: whitelist } = await this.getValues(
      ['assistant_blacklist', 'assistant_whitelist'],
    );
    return { blacklist, whitelist };
  };

  getFeatureFlags = async () => {
    const featureFlags = await this.getValue('feature_flags');
    debug('Feature flags retrieved: %O', featureFlags);
    return featureFlags;
  };

  getBillboards = async () => {
    const billboards = await this.getValue('billboards');
    debug('Billboards retrieved: %O', billboards);
    return billboards;
  };
}
