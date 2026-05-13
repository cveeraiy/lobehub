import { memo, type PropsWithChildren } from 'react';

interface BranchSwitcherProps extends PropsWithChildren {
  currentBranch: string;
  onAfterCheckout?: () => void;
  onExternalRefresh?: () => Promise<void>;
  onOpenChange?: (open: boolean) => void;
  open?: boolean;
  path: string;
}

// Desktop git IPC removed for enterprise web-only build
const BranchSwitcher = memo<BranchSwitcherProps>(({ children }) => <>{children}</>);

BranchSwitcher.displayName = 'BranchSwitcher';

export default BranchSwitcher;
