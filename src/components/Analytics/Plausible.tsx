'use client';

import { memo, useEffect } from 'react';

interface PlausibleAnalyticsProps {
  domain?: string;
  scriptBaseUrl: string;
}

const PlausibleAnalytics = memo<PlausibleAnalyticsProps>(({ domain, scriptBaseUrl }) => {
  useEffect(() => {
    if (!domain) return;

    const script = document.createElement('script');
    script.src = `${scriptBaseUrl}/js/script.js`;
    script.defer = true;
    script.dataset.domain = domain;
    document.head.appendChild(script);
  }, [domain, scriptBaseUrl]);

  return null;
});

export default PlausibleAnalytics;
