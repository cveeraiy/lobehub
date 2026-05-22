import { NuqsAdapter } from 'nuqs/adapters/react-router/v6';
import { type PropsWithChildren, useEffect, useState } from 'react';
import { Outlet } from 'react-router-dom';

import BusinessAuthProvider from '@/business/client/BusinessAuthProvider';
import type { SPAServerConfig } from '@/types/spaServerConfig';

import AuthContainer from './_layout';
import { AuthServerConfigProvider } from './_layout/AuthServerConfigProvider';

const AuthLayout = ({ children }: PropsWithChildren) => {
  const [serverConfig, setServerConfig] = useState<SPAServerConfig | undefined>(
    window.__SERVER_CONFIG__,
  );

  useEffect(() => {
    if (serverConfig) return;
    fetch('/api/__server_config__')
      .then((r) => (r.ok ? r.json() : undefined))
      .then((data) => {
        if (data) setServerConfig(data);
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <NuqsAdapter>
      <BusinessAuthProvider>
        <AuthServerConfigProvider
          featureFlags={serverConfig?.featureFlags as any}
          isMobile={serverConfig?.isMobile}
          serverConfig={serverConfig?.config as any}
        >
          <AuthContainer>{children || <Outlet />}</AuthContainer>
        </AuthServerConfigProvider>
      </BusinessAuthProvider>
    </NuqsAdapter>
  );
};

export default AuthLayout;
