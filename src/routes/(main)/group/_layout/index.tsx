import { Flexbox } from '@lobehub/ui';
import { type FC } from 'react';
import { Outlet } from 'react-router-dom';

import { useInitGroupConfig } from '@/hooks/useInitGroupConfig';

import GroupIdSync from './GroupIdSync';
import RegisterHotkeys from './RegisterHotkeys';
import Sidebar from './Sidebar';
import { styles } from './style';

const Layout: FC = () => {
  useInitGroupConfig();

  return (
    <>
      <Sidebar />
      <Flexbox className={styles.mainContainer} flex={1} height={'100%'}>
        <Outlet />
      </Flexbox>
      <RegisterHotkeys />
      <GroupIdSync />
    </>
  );
};

export default Layout;
