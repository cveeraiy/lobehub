import { NuqsAdapter } from 'nuqs/adapters/react-router/v6';
import { type PropsWithChildren } from 'react';
import { Outlet } from 'react-router-dom';

import BusinessAuthProvider from '@/business/client/BusinessAuthProvider';
import type { SPAServerConfig } from '@/types/spaServerConfig';

import AuthContainer from './_layout';
import { AuthServerConfigProvider } from './_layout/AuthServerConfigProvider';

const AuthLayout = ({ children }: PropsWithChildren) => {
  const serverConfig: SPAServerConfig | undefined = window.__SERVER_CONFIG__;

  return (
    <NuqsAdapter>
      <BusinessAuthProvider>
        <AuthServerConfigProvider
          featureFlags={serverConfig?.featureFlags}
          isMobile={serverConfig?.isMobile}
          serverConfig={serverConfig?.config}
        >
          <AuthContainer>{children || <Outlet />}</AuthContainer>
        </AuthServerConfigProvider>
      </BusinessAuthProvider>
    </NuqsAdapter>
  );
};

export default AuthLayout;
