import { Navigate } from 'react-router-dom';

import { authEnv } from '@/envs/auth';

import DeviceSuccess from './DeviceSuccess';

const DeviceSuccessPage = () => {
  if (!authEnv.ENABLE_OIDC) return <Navigate replace to="/" />;

  return <DeviceSuccess />;
};

export default DeviceSuccessPage;
