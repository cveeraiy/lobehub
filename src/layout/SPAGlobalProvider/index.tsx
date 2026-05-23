'use client';

import { TooltipGroup } from '@lobehub/ui';
import { StyleProvider } from 'antd-style';
import { domMax, LazyMotion } from 'motion/react';
import type { PropsWithChildren } from 'react';
import { lazy, memo, Suspense, useEffect, useLayoutEffect, useState } from 'react';

import { LobeAnalyticsProviderWrapper } from '@/components/Analytics/LobeAnalyticsProviderWrapper';
import { DragUploadProvider } from '@/components/DragUploadZone/DragUploadProvider';
import AuthProvider from '@/layout/AuthProvider';
import AppTheme from '@/layout/GlobalProvider/AppTheme';
import DynamicFavicon from '@/layout/GlobalProvider/DynamicFavicon';
import { FaviconProvider } from '@/layout/GlobalProvider/FaviconProvider';
import { GroupWizardProvider } from '@/layout/GlobalProvider/GroupWizardProvider';
import ImportSettings from '@/layout/GlobalProvider/ImportSettings';
import NextThemeProvider from '@/layout/GlobalProvider/NextThemeProvider';
import QueryProvider from '@/layout/GlobalProvider/Query';
import StoreInitialization from '@/layout/GlobalProvider/StoreInitialization';
import { ServerConfigStoreProvider } from '@/store/serverConfig/Provider';
import type { SPAServerConfig } from '@/types/spaServerConfig';

import Locale from './Locale';

const ModalHost = lazy(() => import('@lobehub/ui').then((m) => ({ default: m.ModalHost })));
const BaseModalHost = lazy(() =>
  import('@lobehub/ui/base-ui').then((m) => ({ default: m.ModalHost })),
);
const ToastHost = lazy(() => import('@lobehub/ui/base-ui').then((m) => ({ default: m.ToastHost })));
const ContextMenuHost = lazy(() =>
  import('@lobehub/ui').then((m) => ({ default: m.ContextMenuHost })),
);

const SPAGlobalProvider = memo<PropsWithChildren>(({ children }) => {
  const [serverConfig, setServerConfig] = useState<SPAServerConfig | undefined>(
    () => window.__SERVER_CONFIG__,
  );

  useLayoutEffect(() => {
    document.getElementById('loading-screen')?.remove();
  }, []);

  useEffect(() => {
    if (serverConfig) return;

    const controller = new AbortController();

    fetch('/api/__server_config__', {
      credentials: 'include',
      signal: controller.signal,
    })
      .then(async (res) => {
        if (!res.ok) return;

        const config = (await res.json()) as SPAServerConfig;
        window.__SERVER_CONFIG__ = config;
        setServerConfig(config);
      })
      .catch(() => {
        // The SPA can still boot with default config while the API is unavailable.
      });

    return () => controller.abort();
  }, [serverConfig]);

  const locale = document.documentElement.lang || 'en-US';
  const isMobile =
    serverConfig?.isMobile ?? (typeof __MOBILE__ !== 'undefined' ? __MOBILE__ : false);

  return (
    <Locale defaultLang={locale}>
      <NextThemeProvider>
        <AppTheme>
          <ServerConfigStoreProvider
            featureFlags={serverConfig?.featureFlags}
            isMobile={isMobile}
            serverConfig={serverConfig?.config}
          >
            <QueryProvider>
              <AuthProvider>
                <StoreInitialization />

                <FaviconProvider>
                  <DynamicFavicon />
                  <GroupWizardProvider>
                    <DragUploadProvider>
                      <LazyMotion features={domMax}>
                        <TooltipGroup layoutAnimation={false}>
                          <StyleProvider speedy={import.meta.env.PROD}>
                            <LobeAnalyticsProviderWrapper>{children}</LobeAnalyticsProviderWrapper>
                          </StyleProvider>
                        </TooltipGroup>
                        <Suspense>
                          <ModalHost />
                          <BaseModalHost />
                          <ToastHost />
                          <ContextMenuHost />
                        </Suspense>
                      </LazyMotion>
                    </DragUploadProvider>
                  </GroupWizardProvider>
                </FaviconProvider>
              </AuthProvider>
            </QueryProvider>
            <Suspense>
              <ImportSettings />
              {/* DevPanel disabled in SPA: depends on node:fs */}
            </Suspense>
          </ServerConfigStoreProvider>
        </AppTheme>
      </NextThemeProvider>
    </Locale>
  );
});

SPAGlobalProvider.displayName = 'SPAGlobalProvider';

export default SPAGlobalProvider;
