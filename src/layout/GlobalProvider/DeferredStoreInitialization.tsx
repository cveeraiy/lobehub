'use client';

import { memo } from 'react';

import { useAiInfraStore } from '@/store/aiInfra';
import { useUserMemoryStore } from '@/store/userMemory';

interface DeferredStoreInitializationProps {
  isLogin: boolean;
}

const DeferredStoreInitialization = memo<DeferredStoreInitializationProps>(({ isLogin }) => {
  const useInitAiProviderKeyVaults = useAiInfraStore((s) => s.useFetchAiProviderRuntimeState);
  const useFetchPersona = useUserMemoryStore((s) => s.useFetchPersona);

  useInitAiProviderKeyVaults(isLogin, false);
  useFetchPersona(isLogin);

  return null;
});

export default DeferredStoreInitialization;
