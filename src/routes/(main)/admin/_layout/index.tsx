import { Flexbox } from '@lobehub/ui';
import { memo } from 'react';
import { Outlet } from 'react-router-dom';

const AdminLayout = memo(() => {
  return (
    <Flexbox height={'100%'} style={{ overflow: 'auto', position: 'relative' }} width={'100%'}>
      <Outlet />
    </Flexbox>
  );
});

AdminLayout.displayName = 'AdminLayout';

export default AdminLayout;
