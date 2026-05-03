import { App, Descriptions, Drawer, Spin, Switch } from 'antd';
import { memo, useCallback, useEffect, useState } from 'react';

import { lambdaClient } from '@/libs/trpc/client';

interface UserSettingsDrawerProps {
  onClose: () => void;
  open: boolean;
  userId: string | null;
}

interface SettingsPermissions {
  agentSettings: boolean;
  systemSettings: boolean;
}

const UserSettingsDrawer = memo<UserSettingsDrawerProps>(({ open, onClose, userId }) => {
  const [loading, setLoading] = useState(false);
  const [settings, setSettings] = useState<any>(null);
  const [permissions, setPermissions] = useState<SettingsPermissions>({
    agentSettings: false,
    systemSettings: false,
  });
  const { message } = App.useApp();

  const fetchSettings = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    try {
      const result = await lambdaClient.admin.getUserSettings.query({ userId });
      setSettings(result.settings);
      setPermissions(result.permissions ?? { agentSettings: false, systemSettings: false });
    } catch {
      message.error('Failed to load user settings');
    } finally {
      setLoading(false);
    }
  }, [userId, message]);

  useEffect(() => {
    if (open && userId) {
      fetchSettings();
    }
  }, [open, userId, fetchSettings]);

  const handlePermissionChange = async (key: keyof SettingsPermissions, value: boolean) => {
    if (!userId) return;
    const newPermissions = { ...permissions, [key]: value };
    setPermissions(newPermissions);
    try {
      await lambdaClient.admin.updateUserPermissions.mutate({
        permissions: newPermissions,
        userId,
      });
      message.success('Permissions updated');
    } catch {
      message.error('Failed to update permissions');
      setPermissions(permissions);
    }
  };

  return (
    <Drawer open={open} title="User Settings" width={520} onClose={onClose}>
      {loading ? (
        <Spin style={{ display: 'block', marginTop: 40, textAlign: 'center' }} />
      ) : (
        <>
          <Descriptions bordered column={1} size="small" title="General Settings">
            <Descriptions.Item label="Language">
              {settings?.general?.language || 'auto'}
            </Descriptions.Item>
            <Descriptions.Item label="Font Size">
              {settings?.general?.fontSize ?? 14}
            </Descriptions.Item>
            <Descriptions.Item label="Theme Mode">
              {settings?.general?.themeMode || 'auto'}
            </Descriptions.Item>
          </Descriptions>

          <Descriptions
            bordered
            column={1}
            size="small"
            style={{ marginTop: 24 }}
            title="Settings Permissions"
          >
            <Descriptions.Item label="Agent Settings">
              <Switch
                checked={permissions.agentSettings}
                onChange={(v) => handlePermissionChange('agentSettings', v)}
              />
            </Descriptions.Item>
            <Descriptions.Item label="System Settings">
              <Switch
                checked={permissions.systemSettings}
                onChange={(v) => handlePermissionChange('systemSettings', v)}
              />
            </Descriptions.Item>
          </Descriptions>
        </>
      )}
    </Drawer>
  );
});

UserSettingsDrawer.displayName = 'UserSettingsDrawer';

export default UserSettingsDrawer;
