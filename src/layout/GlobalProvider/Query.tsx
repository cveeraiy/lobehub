'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { type PropsWithChildren } from 'react';
import React, { useState } from 'react';
import { SWRConfig } from 'swr';

import { swrCacheProvider } from '@/libs/swr/localStorageProvider';

import SWRMutateInitializer from './SWRMutateInitializer';

const QueryProvider = ({ children }: PropsWithChildren) => {
  const [queryClient] = useState(() => new QueryClient());
  // Use useState to ensure the provider is only created once
  const [provider] = useState(swrCacheProvider);

  return (
    <SWRConfig value={{ provider }}>
      <SWRMutateInitializer>
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      </SWRMutateInitializer>
    </SWRConfig>
  );
};

export default QueryProvider;
