import { restClient } from '@/libs/rest';

class NotificationService {
  list = (
    params: {
      category?: string;
      cursor?: string;
      limit?: number;
      unreadOnly?: boolean;
    } = {},
  ) => {
    return restClient.get('/notifications', { params: params as any });
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
