'use client';

import { BookText, Cog, FlagIcon } from 'lucide-react';

import dynamic from '@/libs/next/dynamic';

import FeatureFlagViewer from './FeatureFlagViewer';
import MetadataViewer from './MetadataViewer';
import SystemInspector from './SystemInspector';

const FloatPanel = dynamic(() => import('./features/FloatPanel'), {
  ssr: false,
});

const DevPanel = () => (
  <FloatPanel
    items={[
      {
        children: <MetadataViewer />,
        icon: <BookText size={16} />,
        key: 'SEO Metadata',
      },
      {
        children: <FeatureFlagViewer />,
        icon: <FlagIcon size={16} />,
        key: 'Feature Flags',
      },
      {
        children: <SystemInspector />,
        icon: <Cog size={16} />,
        key: 'System Status',
      },
    ]}
  />
);

export default DevPanel;
