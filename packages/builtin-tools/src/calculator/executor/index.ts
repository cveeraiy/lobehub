import type { BuiltinToolContext, BuiltinToolResult } from '@lobechat/types';
import { BaseExecutor } from '@lobechat/types';

import { restClient } from '@/libs/rest';

import type {
  BaseParams,
  CalculateParams,
  DefintegrateParams,
  DifferentiateParams,
  EvaluateParams,
  ExecuteParams,
  IntegrateParams,
  LimitParams,
  SolveParams,
  SortParams,
} from '../types';
import { CalculatorApiName, CalculatorIdentifier } from '../types';

interface PythonToolRunResponse {
  result: string;
}

const runPythonCalculator = async (
  apiName: string,
  params: unknown,
): Promise<BuiltinToolResult> => {
  const response = await restClient.post<PythonToolRunResponse>('/tools/run', {
    body: {
      arguments: params,
      tool_name: `${CalculatorIdentifier}__${apiName}`,
    },
  });

  return JSON.parse(response.result) as BuiltinToolResult;
};

class CalculatorExecutor extends BaseExecutor<typeof CalculatorApiName> {
  readonly identifier = CalculatorIdentifier;
  protected readonly apiEnum = CalculatorApiName;

  base = async (params: BaseParams, _ctx?: BuiltinToolContext) =>
    runPythonCalculator(CalculatorApiName.base, params);

  calculate = async (params: CalculateParams, _ctx?: BuiltinToolContext) =>
    runPythonCalculator(CalculatorApiName.calculate, params);

  defintegrate = async (params: DefintegrateParams, _ctx?: BuiltinToolContext) =>
    runPythonCalculator(CalculatorApiName.defintegrate, params);

  differentiate = async (params: DifferentiateParams, _ctx?: BuiltinToolContext) =>
    runPythonCalculator(CalculatorApiName.differentiate, params);

  evaluate = async (params: EvaluateParams, _ctx?: BuiltinToolContext) =>
    runPythonCalculator(CalculatorApiName.evaluate, params);

  execute = async (params: ExecuteParams, _ctx?: BuiltinToolContext) =>
    runPythonCalculator(CalculatorApiName.execute, params);

  integrate = async (params: IntegrateParams, _ctx?: BuiltinToolContext) =>
    runPythonCalculator(CalculatorApiName.integrate, params);

  limit = async (params: LimitParams, _ctx?: BuiltinToolContext) =>
    runPythonCalculator(CalculatorApiName.limit, params);

  solve = async (params: SolveParams, _ctx?: BuiltinToolContext) =>
    runPythonCalculator(CalculatorApiName.solve, params);

  sort = async (params: SortParams, _ctx?: BuiltinToolContext) =>
    runPythonCalculator(CalculatorApiName.sort, params);
}

export const calculatorExecutor = new CalculatorExecutor();
