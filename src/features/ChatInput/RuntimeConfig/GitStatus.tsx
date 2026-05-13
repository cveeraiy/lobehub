import { memo } from 'react';

interface GitStatusProps {
  isGithub: boolean;
  path: string;
}

// Desktop git IPC removed for enterprise web-only build
const GitStatus = memo<GitStatusProps>(() => null);

GitStatus.displayName = 'GitStatus';

export default GitStatus;
