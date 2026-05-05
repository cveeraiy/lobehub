import { Navigate } from 'react-router-dom';

import { authEnv } from '@/envs/auth';

import BetterAuthSignUpForm from './BetterAuthSignUpForm';

const Page = () => {
  if (authEnv.AUTH_DISABLE_EMAIL_PASSWORD) {
    return <Navigate replace to="/signin" />;
  }

  return <BetterAuthSignUpForm />;
};

export default Page;
