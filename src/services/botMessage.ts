import { restClient } from '@/libs/rest';

const actionPathMap: Record<string, string> = {
  createPoll: '/bot-message/create-poll',
  createThread: '/bot-message/create-thread',
  deleteMessage: '/bot-message/delete-message',
  editMessage: '/bot-message/edit-message',
  getChannelInfo: '/bot-message/channel-info',
  getMemberInfo: '/bot-message/member-info',
  getReactions: '/bot-message/get-reactions',
  listChannels: '/bot-message/list-channels',
  listPins: '/bot-message/list-pins',
  listThreads: '/bot-message/list-threads',
  pinMessage: '/bot-message/pin-message',
  reactToMessage: '/bot-message/react-to-message',
  readMessages: '/bot-message/read-messages',
  replyToThread: '/bot-message/reply-to-thread',
  searchMessages: '/bot-message/search-messages',
  sendDirectMessage: '/bot-message/send-direct-message',
  sendMessage: '/bot-message/send-message',
  unpinMessage: '/bot-message/unpin-message',
};

const toSnakeBody = (params: Record<string, unknown>) => ({
  after: params.after,
  author_id: params.authorId,
  before: params.before,
  bot_id: params.botId,
  channel_id: params.channelId,
  content: params.content,
  cursor: params.cursor,
  duration: params.duration,
  emoji: params.emoji,
  embeds: params.embeds,
  end_time: params.endTime,
  filter: params.filter,
  limit: params.limit,
  member_id: params.memberId,
  message_id: params.messageId,
  multiple_answers: params.multipleAnswers,
  name: params.name,
  options: params.options,
  query: params.query,
  question: params.question,
  reply_to: params.replyTo,
  server_id: params.serverId,
  start_time: params.startTime,
  thread_id: params.threadId,
  user_id_target: params.userId,
});

class BotMessageService {
  call = async (apiName: string, params: Record<string, unknown>, method: 'mutate' | 'query') => {
    const path = actionPathMap[apiName];
    if (!path) throw new Error(`Unknown message API: ${apiName}`);

    const body = toSnakeBody(params);
    if (method === 'query') {
      return restClient.get(path, {
        params: body as Record<string, string | number | boolean | undefined>,
      });
    }

    return restClient.post(path, { body });
  };
}

export const botMessageService = new BotMessageService();
