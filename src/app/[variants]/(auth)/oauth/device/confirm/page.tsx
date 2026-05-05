'use client';

import { Navigate, useSearchParams } from 'react-router-dom';

import { authEnv } from '@/envs/auth';

import DeviceCodeConfirm from './DeviceCodeConfirm';

const DeviceConfirmPage = () => {
  const [searchParams] = useSearchParams();

  if (!authEnv.ENABLE_OIDC) return <Navigate replace to="/" />;

  const userCode = searchParams.get('user_code');
  if (!userCode) return <Navigate replace to="/" />;

  return (
    <DeviceCodeConfirm
      clientName={
        searchParams.get('client_name') || searchParams.get('client_id') || 'Unknown Application'
      }
      userCode={userCode}
      xsrf={searchParams.get('xsrf') || undefined}
    />
  );
};

export default DeviceConfirmPage;
