import { type ChildProcess, spawn } from 'node:child_process';
import dotenv from 'dotenv';
import net from 'node:net';

dotenv.config();

const HONO_HOST = 'localhost';

/**
 * Resolve the Hono dev port.
 * Priority: -p CLI flag > PORT env var > 3010.
 */
const resolveHonoPort = (): number => {
  const pIndex = process.argv.indexOf('-p');
  if (pIndex !== -1 && process.argv[pIndex + 1]) {
    return Number(process.argv[pIndex + 1]);
  }
  if (process.env.PORT) return Number(process.env.PORT);
  return 3010;
};

const HONO_PORT = resolveHonoPort();
const HONO_ROOT_URL = `http://${HONO_HOST}:${HONO_PORT}/`;
const HONO_READY_TIMEOUT_MS = 60_000;
const HONO_READY_RETRY_MS = 400;

const npmCommand = process.platform === 'win32' ? 'npm.cmd' : 'npm';

let honoProcess: ChildProcess | undefined;
let viteProcess: ChildProcess | undefined;
let shuttingDown = false;

const runNpmScript = (scriptName: string) =>
  spawn(npmCommand, ['run', scriptName], {
    env: process.env,
    stdio: 'inherit',
    shell: process.platform === 'win32',
  });

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const isPortOpen = (host: string, port: number) =>
  new Promise<boolean>((resolve) => {
    const socket = net.createConnection({ host, port });
    const onDone = (result: boolean) => {
      socket.removeAllListeners();
      socket.destroy();
      resolve(result);
    };

    socket.once('connect', () => onDone(true));
    socket.once('error', () => onDone(false));
    socket.setTimeout(1_000, () => onDone(false));
  });

const waitForHonoReady = async () => {
  const startedAt = Date.now();

  while (Date.now() - startedAt < HONO_READY_TIMEOUT_MS) {
    if (await isPortOpen(HONO_HOST, HONO_PORT)) return;
    await wait(HONO_READY_RETRY_MS);
  }

  throw new Error(
    `Hono server was not ready within ${HONO_READY_TIMEOUT_MS / 1000}s on ${HONO_HOST}:${HONO_PORT}`,
  );
};

const runHonoBackgroundTasks = () => {
  setTimeout(() => {
    console.log(`🔁 Hono server URL: ${HONO_ROOT_URL}`);
  }, 2_000);

  void (async () => {
    try {
      await waitForHonoReady();
      console.log(`✅ Hono server ready at ${HONO_ROOT_URL}`);
    } catch (error) {
      console.warn('⚠️ Hono readiness check skipped:', error);
    }
  })();
};

const terminateChild = (child?: ChildProcess) => {
  if (!child || child.killed) return;
  child.kill('SIGTERM');
};

const shutdownAll = (signal: NodeJS.Signals) => {
  if (shuttingDown) return;
  shuttingDown = true;

  terminateChild(viteProcess);
  terminateChild(honoProcess);

  process.exitCode = signal === 'SIGINT' ? 130 : 143;
};

const watchChildExit = (child: ChildProcess, name: 'hono' | 'vite') => {
  child.once('exit', (code, signal) => {
    if (!shuttingDown) {
      console.error(
        `❌ ${name} exited unexpectedly (code: ${code ?? 'null'}, signal: ${signal ?? 'null'})`,
      );
      shutdownAll('SIGTERM');
    }
  });
};

const main = async () => {
  process.once('SIGINT', () => shutdownAll('SIGINT'));
  process.once('SIGTERM', () => shutdownAll('SIGTERM'));

  honoProcess = runNpmScript('dev:hono');
  watchChildExit(honoProcess, 'hono');

  viteProcess = runNpmScript('dev:spa');
  watchChildExit(viteProcess, 'vite');
  runHonoBackgroundTasks();

  await Promise.race([
    new Promise((resolve) => honoProcess?.once('exit', resolve)),
    new Promise((resolve) => viteProcess?.once('exit', resolve)),
  ]);
};

void main().catch((error) => {
  console.error('❌ dev startup sequence failed:', error);
  shutdownAll('SIGTERM');
});
