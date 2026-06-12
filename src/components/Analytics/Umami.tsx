'use client';

import { memo, useEffect } from 'react';

interface UmamiAnalyticsProps {
  scriptUrl: string;
  websiteId?: string;
}

const UmamiAnalytics = memo<UmamiAnalyticsProps>(({ scriptUrl, websiteId }) => {
  useEffect(() => {
    if (!websiteId) return;

    const script = document.createElement('script');
    script.src = scriptUrl;
    script.defer = true;
    script.dataset.websiteId = websiteId;
    document.head.appendChild(script);
  }, [scriptUrl, websiteId]);

  return null;
});

export default UmamiAnalytics;
