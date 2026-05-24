/**
 * This file contains the root router of Ethos tRPC-backend
 */
import { accountDeletionRouter } from '@/business/server/lambda-routers/accountDeletion';
import { referralRouter } from '@/business/server/lambda-routers/referral';
import { spendRouter } from '@/business/server/lambda-routers/spend';
import { subscriptionRouter } from '@/business/server/lambda-routers/subscription';
import { taskTemplateRouter } from '@/business/server/lambda-routers/taskTemplate';
import { topUpRouter } from '@/business/server/lambda-routers/topUp';
import { publicProcedure, router } from '@/libs/trpc/lambda';

import { adminRouter } from './admin';
import { agentRouter } from './agent';
import { agentBotProviderRouter } from './agentBotProvider';
import { agentCronJobRouter } from './agentCronJob';
import { agentDocumentRouter } from './agentDocument';
import { agentEvalRouter } from './agentEval';
import { agentEvalExternalRouter } from './agentEvalExternal';
import { agentGroupRouter } from './agentGroup';
import { agentNotifyRouter } from './agentNotify';
import { agentSkillsRouter } from './agentSkills';
import { aiChatRouter } from './aiChat';
import { aiModelRouter } from './aiModel';
import { aiProviderRouter } from './aiProvider';
import { apiKeyRouter } from './apiKey';
import { botMessageRouter } from './botMessage';
import { briefRouter } from './brief';
import { chunkRouter } from './chunk';
import { comfyuiRouter } from './comfyui';
import { configRouter } from './config';
import { deviceRouter } from './device';
import { documentRouter } from './document';
import { exporterRouter } from './exporter';
import { fileRouter } from './file';
import { followUpActionRouter } from './followUpAction';
import { generationRouter } from './generation';
import { generationBatchRouter } from './generationBatch';
import { generationTopicRouter } from './generationTopic';
import { homeRouter } from './home';
import { imageRouter } from './image';
import { importerRouter } from './importer';
import { klavisRouter } from './klavis';
import { knowledgeRouter } from './knowledge';
import { knowledgeBaseRouter } from './knowledgeBase';
import { marketRouter } from './market';
import { messageRouter } from './message';
import { notificationRouter } from './notification';
import { pluginRouter } from './plugin';
import { ragEvalRouter } from './ragEval';
import { recentRouter } from './recent';
import { sessionRouter } from './session';
import { sessionGroupRouter } from './sessionGroup';
import { shareRouter } from './share';
import { taskRouter } from './task';
import { threadRouter } from './thread';
import { topicRouter } from './topic';
import { uploadRouter } from './upload';
import { usageRouter } from './usage';
import { userRouter } from './user';
import { videoRouter } from './video';

export const lambdaRouter = router({
  admin: adminRouter,
  agent: agentRouter,
  agentBotProvider: agentBotProviderRouter,
  agentNotify: agentNotifyRouter,
  botMessage: botMessageRouter,
  agentCronJob: agentCronJobRouter,
  agentDocument: agentDocumentRouter,
  agentEval: agentEvalRouter,
  agentEvalExternal: agentEvalExternalRouter,
  agentSkills: agentSkillsRouter,
  task: taskRouter,
  brief: briefRouter,
  aiChat: aiChatRouter,
  aiModel: aiModelRouter,
  aiProvider: aiProviderRouter,
  apiKey: apiKeyRouter,
  chunk: chunkRouter,
  comfyui: comfyuiRouter,
  config: configRouter,
  device: deviceRouter,
  document: documentRouter,
  exporter: exporterRouter,
  file: fileRouter,
  followUpAction: followUpActionRouter,
  generation: generationRouter,
  generationBatch: generationBatchRouter,
  generationTopic: generationTopicRouter,
  group: agentGroupRouter,
  healthcheck: publicProcedure.query(() => "i'm live!"),
  home: homeRouter,
  image: imageRouter,
  importer: importerRouter,
  klavis: klavisRouter,
  knowledge: knowledgeRouter,
  knowledgeBase: knowledgeBaseRouter,
  market: marketRouter,
  message: messageRouter,
  notification: notificationRouter,
  plugin: pluginRouter,
  ragEval: ragEvalRouter,
  recent: recentRouter,
  session: sessionRouter,
  sessionGroup: sessionGroupRouter,
  share: shareRouter,
  thread: threadRouter,
  topic: topicRouter,
  upload: uploadRouter,
  usage: usageRouter,
  user: userRouter,
  video: videoRouter,
  accountDeletion: accountDeletionRouter,
  referral: referralRouter,
  spend: spendRouter,
  subscription: subscriptionRouter,
  taskTemplate: taskTemplateRouter,
  topUp: topUpRouter,
});

export type LambdaRouter = typeof lambdaRouter;
