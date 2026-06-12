import { memo } from 'react';

import OllamaSetupGuide from '@/components/OllamaSetupGuide';
import { ErrorActionContainer } from '@/features/Conversation/Error/style';

const SetupGuide = memo<{ container?: boolean }>(({ container = true }) => {
  const content = <OllamaSetupGuide />;

  if (!container) return content;

  return <ErrorActionContainer style={{ paddingBlock: 0 }}>{content}</ErrorActionContainer>;
});

export default SetupGuide;
