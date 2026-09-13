import { http } from './client';
import type { Workflow, WorkflowListResponse } from '../types';

export async function getWorkflows(params?: {
  page?: number;
  per_page?: number;
  status?: string;
  repository?: string;
}): Promise<WorkflowListResponse> {
  const { data } = await http.get<WorkflowListResponse>('/workflows', { params });
  return data;
}

export async function getWorkflow(workflowId: string): Promise<Workflow> {
  const { data } = await http.get<Workflow>(`/workflows/${workflowId}`);
  return data;
}