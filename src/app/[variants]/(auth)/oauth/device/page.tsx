'use client';

import { Navigate, useSearchParams } from 'react-router-dom';

import { authEnv } from '@/envs/auth';

import DeviceCodeInput from './DeviceCodeInput';

const getErrorMessage = (error?: string): string | undefined => {
  if (!error) return undefined;

  const errorMap: Record<string, string> = {
    'already been used': 'device.error.alreadyUsed',
    'interaction was aborted': 'device.error.aborted',
    'code has expired': 'device.error.expired',
    'code was not found': 'device.error.notFound',
    'no code': 'device.error.noCode',
  };

  for (const [key, i18nKey] of Object.entries(errorMap)) {
    if (error.toLowerCase().includes(key)) return i18nKey;
  }

  return 'device.error.unknown';
};

const DeviceInputPage = () => {
  const [searchParams] = useSearchParams();

  if (!authEnv.ENABLE_OIDC) return <Navigate replace to="/" />;

  return (
    <DeviceCodeInput
      errorKey={getErrorMessage(searchParams.get('error') || undefined)}
      userCode={searchParams.get('user_code') || undefined}
      xsrf={searchParams.get('xsrf') || undefined}
    />
  );
};

export default DeviceInputPage;
