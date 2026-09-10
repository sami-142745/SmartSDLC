import { http } from './client';
import type {
  DashboardSummary,
  FeedbackSummary,
  HistoryResponse,
  RepoMetricsResponse,
} from '../types';

export async function getDashboard(): Promise<DashboardSummary> {
  const { data } = await http.get<DashboardSummary>('/dashboard');
  return data;
}

export async function getHistory(params: {
  page: number;
  perPage: number;
  repository?: string;
  status?: string;
}): Promise<HistoryResponse> {
  const { data } = await http.get<HistoryResponse>('/history', {
    params: {
      page: params.page,
      per_page: params.perPage,
      repository: params.repository || undefined,
      status: params.status || undefined,
    },
  });
  return data;
}

export async function getRepositoryMetrics(
  page = 1,
  perPage = 20,
): Promise<RepoMetricsResponse> {
  const { data } = await http.get<RepoMetricsResponse>('/dashboard/repositories', {
    params: { page, per_page: perPage },
  });
  return data;
}

export async function getFeedbackSummary(): Promise<FeedbackSummary> {
  const { data } = await http.get<FeedbackSummary>('/dashboard/feedback-summary');
  return data;
}