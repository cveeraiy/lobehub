import { Form as AntdForm, type FormInstance } from 'antd';
import { useMemo } from 'react';

interface NetworkProxySettings {
  enableProxy?: boolean;
  proxyPassword?: string;
  proxyPort?: number;
  proxyRequireAuth?: boolean;
  proxyServer?: string;
  proxyType?: string;
  proxyUsername?: string;
}

const WATCH_FIELDS: readonly (keyof NetworkProxySettings)[] = [
  'enableProxy',
  'proxyType',
  'proxyServer',
  'proxyPort',
  'proxyRequireAuth',
  'proxyUsername',
  'proxyPassword',
];

const normalize = (v: unknown) => (v === undefined || v === null ? '' : v);

export const useProxyDirty = (
  form: FormInstance,
  saved: NetworkProxySettings | undefined,
): { isDirty: boolean } => {
  const values = AntdForm.useWatch([], form);

  const isDirty = useMemo(() => {
    if (!saved || !values) return false;
    return WATCH_FIELDS.some((key) => normalize(values[key]) !== normalize(saved[key]));
  }, [values, saved]);

  return { isDirty };
};
