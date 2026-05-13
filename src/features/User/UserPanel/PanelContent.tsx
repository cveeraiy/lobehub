import { ENABLE_BUSINESS_FEATURES } from '@lobechat/business-const';
import { Flexbox } from '@lobehub/ui';
import { type FC } from 'react';
import { Link } from 'react-router-dom';

import BusinessPanelContent from '@/business/client/features/User/BusinessPanelContent';
import Menu from '@/components/Menu';
import UserInfo from '@/features/User/UserInfo';
import { useSession } from '@/libs/better-auth/auth-client';
import { useUserStore } from '@/store/user';
import { authSelectors } from '@/store/user/selectors';

import DataStatistics from '../DataStatistics';
import UserLoginOrSignup from '../UserLoginOrSignup';
import LangButton from './LangButton';
import { useMenu } from './useMenu';

const PanelContent: FC<{ closePopover: () => void }> = ({ closePopover }) => {
  const isLoginWithAuth = useUserStore(authSelectors.isLoginWithAuth);
  const [openSignIn, signOut] = useUserStore((s) => [s.openLogin, s.logout]);
  const { mainItems, logoutItems } = useMenu();
  const { data: session } = useSession();
  const isAdmin = session?.user?.role === 'admin';

  const handleSignIn = () => {
    openSignIn();
    closePopover();
  };

  const handleSignOut = () => {
    signOut();
    closePopover();
  };

  return (
    <Flexbox gap={2} style={{ minWidth: 300 }}>
      {isLoginWithAuth ? (
        <>
          <UserInfo avatarProps={{ clickable: false }} />
          {isAdmin && (
            <Link style={{ color: 'inherit' }} to={'/settings/stats'}>
              <DataStatistics />
            </Link>
          )}
          {isAdmin && ENABLE_BUSINESS_FEATURES && <BusinessPanelContent />}
        </>
      ) : (
        <UserLoginOrSignup onClick={handleSignIn} />
      )}

      <Menu items={mainItems} onClick={closePopover} />
      {isAdmin && <LangButton placement={'right' as any} />}
      <Menu items={logoutItems} onClick={handleSignOut} />
    </Flexbox>
  );
};

export default PanelContent;
