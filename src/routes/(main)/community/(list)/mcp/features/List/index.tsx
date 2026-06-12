import { memo } from 'react';

interface McpListProps {
  data?: any[];
}

const McpList = memo<McpListProps>(() => null);

McpList.displayName = 'McpList';

export default McpList;
