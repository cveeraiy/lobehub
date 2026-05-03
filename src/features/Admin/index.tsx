import { Avatar, Tag } from '@lobehub/ui';
import { App, Button, Popconfirm, Select, Table, type TableColumnType } from 'antd';
import { memo, useCallback, useEffect, useState } from 'react';

import { admin } from '@/libs/better-auth/auth-client';

import UserSettingsDrawer from './UserSettingsDrawer';

interface UserRecord {
  banned: boolean;
  email: string;
  id: string;
  image: string | null;
  name: string;
  role: string;
}

const AdminPanel = memo(() => {
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const { message } = App.useApp();

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const res = await admin.listUsers({ query: { limit: '100' } });
      if (res.data) {
        setUsers(
          res.data.users.map((u: any) => ({
            banned: u.banned ?? false,
            email: u.email,
            id: u.id,
            image: u.image,
            name: u.name,
            role: u.role ?? 'user',
          })),
        );
      }
    } catch {
      message.error('Failed to load users');
    } finally {
      setLoading(false);
    }
  }, [message]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const handleRoleChange = async (userId: string, newRole: string) => {
    try {
      await admin.setRole({ role: newRole, userId });
      message.success('Role updated');
      fetchUsers();
    } catch {
      message.error('Failed to update role');
    }
  };

  const handleBan = async (userId: string) => {
    try {
      await admin.banUser({ userId });
      message.success('User banned');
      fetchUsers();
    } catch {
      message.error('Failed to ban user');
    }
  };

  const handleUnban = async (userId: string) => {
    try {
      await admin.unbanUser({ userId });
      message.success('User unbanned');
      fetchUsers();
    } catch {
      message.error('Failed to unban user');
    }
  };

  const handleRemove = async (userId: string) => {
    try {
      await admin.removeUser({ userId });
      message.success('User removed');
      fetchUsers();
    } catch {
      message.error('Failed to remove user');
    }
  };

  const handleRowClick = (record: UserRecord) => {
    setSelectedUserId(record.id);
    setDrawerOpen(true);
  };

  const columns: TableColumnType<UserRecord>[] = [
    {
      dataIndex: 'image',
      key: 'avatar',
      render: (image: string | null, record: UserRecord) => (
        <Avatar avatar={image || undefined} size={32} title={record.name} />
      ),
      title: '',
      width: 60,
    },
    { dataIndex: 'name', key: 'name', title: 'Name' },
    { dataIndex: 'email', key: 'email', title: 'Email' },
    {
      dataIndex: 'role',
      key: 'role',
      render: (role: string, record: UserRecord) => (
        <Select
          size="small"
          value={role}
          options={[
            { label: 'User', value: 'user' },
            { label: 'Admin', value: 'admin' },
          ]}
          onChange={(value) => handleRoleChange(record.id, value)}
          onClick={(e) => e.stopPropagation()}
        />
      ),
      title: 'Role',
      width: 120,
    },
    {
      dataIndex: 'banned',
      key: 'status',
      render: (banned: boolean) => (
        <Tag color={banned ? 'red' : 'green'}>{banned ? 'Banned' : 'Active'}</Tag>
      ),
      title: 'Status',
      width: 100,
    },
    {
      key: 'actions',
      render: (_: any, record: UserRecord) => (
        <div style={{ display: 'flex', gap: 8 }} onClick={(e) => e.stopPropagation()}>
          {record.banned ? (
            <Button size="small" onClick={() => handleUnban(record.id)}>
              Unban
            </Button>
          ) : (
            <Button size="small" onClick={() => handleBan(record.id)}>
              Ban
            </Button>
          )}
          <Popconfirm
            cancelText="Cancel"
            okText="Remove"
            okType="danger"
            title="Are you sure you want to remove this user?"
            onConfirm={() => handleRemove(record.id)}
          >
            <Button danger size="small">
              Remove
            </Button>
          </Popconfirm>
        </div>
      ),
      title: 'Actions',
      width: 200,
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <h2>User Management</h2>
      <Table
        columns={columns}
        dataSource={users}
        loading={loading}
        rowKey="id"
        size="middle"
        onRow={(record) => ({
          onClick: () => handleRowClick(record),
          style: { cursor: 'pointer' },
        })}
      />
      <UserSettingsDrawer
        open={drawerOpen}
        userId={selectedUserId}
        onClose={() => setDrawerOpen(false)}
      />
    </div>
  );
});

AdminPanel.displayName = 'AdminPanel';

export default AdminPanel;
