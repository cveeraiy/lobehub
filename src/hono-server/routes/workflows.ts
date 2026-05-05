import { Hono } from 'hono';

import { POST as executeTestCase } from '@/handlers/api/workflows/agent-eval-run/execute-test-case/route';
import { POST as finalizeRun } from '@/handlers/api/workflows/agent-eval-run/finalize-run/route';
import { POST as onThreadComplete } from '@/handlers/api/workflows/agent-eval-run/on-thread-complete/route';
import { POST as onTrajectoryComplete } from '@/handlers/api/workflows/agent-eval-run/on-trajectory-complete/route';
import { POST as paginateTestCases } from '@/handlers/api/workflows/agent-eval-run/paginate-test-cases/route';
import { POST as resumeAgentTrajectory } from '@/handlers/api/workflows/agent-eval-run/resume-agent-trajectory/route';
import { POST as resumeThreadTrajectory } from '@/handlers/api/workflows/agent-eval-run/resume-thread-trajectory/route';
import { POST as runAgentTrajectory } from '@/handlers/api/workflows/agent-eval-run/run-agent-trajectory/route';
import { POST as runBenchmark } from '@/handlers/api/workflows/agent-eval-run/run-benchmark/route';
import { POST as runThreadTrajectory } from '@/handlers/api/workflows/agent-eval-run/run-thread-trajectory/route';

const workflows = new Hono();

// ============ Agent Eval Run Workflows ============ //
workflows.post('/api/workflows/agent-eval-run/execute-test-case', (c) =>
  executeTestCase(c.req.raw),
);
workflows.post('/api/workflows/agent-eval-run/finalize-run', (c) => finalizeRun(c.req.raw));
workflows.post('/api/workflows/agent-eval-run/on-thread-complete', (c) =>
  onThreadComplete(c.req.raw),
);
workflows.post('/api/workflows/agent-eval-run/on-trajectory-complete', (c) =>
  onTrajectoryComplete(c.req.raw),
);
workflows.post('/api/workflows/agent-eval-run/paginate-test-cases', (c) =>
  paginateTestCases(c.req.raw),
);
workflows.post('/api/workflows/agent-eval-run/resume-agent-trajectory', (c) =>
  resumeAgentTrajectory(c.req.raw),
);
workflows.post('/api/workflows/agent-eval-run/resume-thread-trajectory', (c) =>
  resumeThreadTrajectory(c.req.raw),
);
workflows.post('/api/workflows/agent-eval-run/run-agent-trajectory', (c) =>
  runAgentTrajectory(c.req.raw),
);
workflows.post('/api/workflows/agent-eval-run/run-benchmark', (c) => runBenchmark(c.req.raw));
workflows.post('/api/workflows/agent-eval-run/run-thread-trajectory', (c) =>
  runThreadTrajectory(c.req.raw),
);

export default workflows;
