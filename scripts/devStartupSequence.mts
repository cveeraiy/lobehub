import { type ChildProcess, spawn } from 'node:child_process';
import dotenv from 'dotenv';

dotenv.config();

const npmCommand = process.platform === 'win32' ? 'npm.cmd' : 'npm';

let viteProcess: ChildProcess | undefined;
let shuttingDown = false;

const runNpmScript = (scriptName: string) =>
  spawn(npmCommand, ['run', scriptName], {
    env: process.env,
    stdio: 'inherit',
    shell: process.platform === 'win32',
  });

const terminateChild = (child?: ChildProcess) => {
  if (!child || child.killed) return;
  child.kill('SIGTERM');
};

const shutdownAll = (signal: NodeJS.Signals) => {
  if (shuttingDown) return;
  shuttingDown = true;

  terminateChild(viteProcess);

  process.exitCode = signal === 'SIGINT' ? 130 : 143;
};

const watchChildExit = (child: ChildProcess, name: 'vite') => {
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

  viteProcess = runNpmScript('dev:spa');
  watchChildExit(viteProcess, 'vite');

  await new Promise((resolve) => viteProcess?.once('exit', resolve));
};

void main().catch((error) => {
  console.error('❌ dev startup sequence failed:', error);
  shutdownAll('SIGTERM');
});
