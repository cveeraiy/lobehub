import { type PropsWithChildren } from 'react';
import { Navigate } from 'react-router-dom';

import { authEnv } from '@/envs/auth';

const ResetPasswordLayout = ({ children }: PropsWithChildren) => {
  if (authEnv.AUTH_DISABLE_EMAIL_PASSWORD) {
    return <Navigate replace to="/signin" />;
  }

  return children;
};

export default ResetPasswordLayout;
