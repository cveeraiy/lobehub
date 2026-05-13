import { Block } from '@lobehub/ui';
import { memo } from 'react';

import OllamaSetupGuide from '@/components/OllamaSetupGuide';

const SetupGuide = memo<{ id?: string }>(() => {
  return (
    <Block
      align={'center'}
      gap={8}
      padding={16}
      variant={'outlined'}
      style={{
        overflow: 'hidden',
        position: 'relative',
        width: '100%',
      }}
    >
      <OllamaSetupGuide />
    </Block>
  );
});

export default SetupGuide;
