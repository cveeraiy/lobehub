import { memo } from 'react';

import AdminPanel from '@/features/Admin';

const AdminPage = memo(() => {
  return <AdminPanel />;
});

AdminPage.displayName = 'AdminPage';

export default AdminPage;
