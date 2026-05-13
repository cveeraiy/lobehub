import { memo } from 'react';

interface SubscriptionIframeWrapperProps {
  page: 'billing' | 'credits' | 'plans' | 'referral' | 'usage';
}

// Desktop webview component removed for enterprise web-only build
export const SubscriptionIframeWrapper = memo<SubscriptionIframeWrapperProps>(() => null);

SubscriptionIframeWrapper.displayName = 'SubscriptionIframeWrapper';
