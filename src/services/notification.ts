import { restClient } from '@/libs/rest';

export interface NotificationItem {
  actionUrl?: null | string;
  content: string;
  createdAt: Date | string;
  id: string;
  isRead: boolean;
  title: string;
  type: string;
}

class NotificationService {
  list = (
    params: {
      category?: string;
      cursor?: string;
      limit?: number;
      unreadOnly?: boolean;
    } = {},
  ): Promise<NotificationItem[]> => {
    return restClient.get<NotificationItem[]>('/notifications', { params });
  };

  getUnreadCount = (): Promise<number> => {
    return restClient.get<number>('/notifications/unread-count');
  };

  markAsRead = (ids: string[]) => {
    return restClient.put('/notifications/read', { body: { ids } });
  };

  markAllAsRead = () => {
    return restClient.put('/notifications/read-all');
  };

  archive = (id: string) => {
    return restClient.delete(`/notifications/${id}`);
  };

  archiveAll = () => {
    return restClient.delete('/notifications');
  };
}

export const notificationService = new NotificationService();
