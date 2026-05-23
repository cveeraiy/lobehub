import { CalculatorApiName, CalculatorIdentifier } from '@lobechat/builtin-tools';

import { callPythonBackend } from '@/server/utils/pythonBackend';

import type { ToolExecutionContext } from '../types';
import type { ServerRuntimeRegistration } from './types';

interface PythonToolRunResponse {
  result: string;
}

class CalculatorPythonRuntime {
  constructor(private context: ToolExecutionContext) {}

  private async run(apiName: string, args: unknown) {
    if (!this.context.userId) {
      throw new Error('userId is required for calculator execution');
    }

    const response = await callPythonBackend<PythonToolRunResponse>(
      '/api/tools/run',
      this.context.userId,
      {
        body: {
          arguments: args,
          tool_name: `${CalculatorIdentifier}__${apiName}`,
        },
      },
    );

    return JSON.parse(response.result);
  }

  base = (args: unknown) => this.run(CalculatorApiName.base, args);
  calculate = (args: unknown) => this.run(CalculatorApiName.calculate, args);
  defintegrate = (args: unknown) => this.run(CalculatorApiName.defintegrate, args);
  differentiate = (args: unknown) => this.run(CalculatorApiName.differentiate, args);
  evaluate = (args: unknown) => this.run(CalculatorApiName.evaluate, args);
  execute = (args: unknown) => this.run(CalculatorApiName.execute, args);
  integrate = (args: unknown) => this.run(CalculatorApiName.integrate, args);
  limit = (args: unknown) => this.run(CalculatorApiName.limit, args);
  solve = (args: unknown) => this.run(CalculatorApiName.solve, args);
  sort = (args: unknown) => this.run(CalculatorApiName.sort, args);
}

export const calculatorRuntime: ServerRuntimeRegistration = {
  factory: (context) => new CalculatorPythonRuntime(context),
  identifier: CalculatorIdentifier,
};
