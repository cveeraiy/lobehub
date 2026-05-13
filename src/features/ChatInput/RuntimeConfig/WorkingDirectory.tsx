import { memo } from 'react';

interface WorkingDirectoryContentProps {
  agentId: string;
  onClose?: () => void;
}

// Desktop working directory picker removed for enterprise web-only build
const WorkingDirectoryContent = memo<WorkingDirectoryContentProps>(() => null);

WorkingDirectoryContent.displayName = 'WorkingDirectoryContent';

export default WorkingDirectoryContent;
