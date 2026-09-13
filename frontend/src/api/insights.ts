import { http } from './client';
import type {
  GenerateInsightRequest,
  InsightListResponse,
  InsightReport,
  InsightReportType,
} from '../types';

export async function generateInsight(payload: GenerateInsightRequest): Promise<InsightReport> {
  const { data } = await http.post<InsightReport>('/insights/generate', payload);
  return data;
}

export async function getInsights(
  params: {
    page?: number;
    perPage?: number;
    repository?: string;
    reportType?: InsightReportType;
  } = {},
): Promise<InsightListResponse> {
  const { data } = await http.get<InsightListResponse>('/insights', {
    params: {
      page: params.page ?? 1,
      per_page: params.perPage ?? 20,
      ...(params.repository ? { repository: params.repository } : {}),
      ...(params.reportType ? { report_type: params.reportType } : {}),
    },
  });
  return data;
}

export async function getLatestRepositoryInsight(
  owner: string,
  repository: string,
): Promise<InsightReport> {
  const { data } = await http.get<InsightReport>(
    `/insights/repository/${encodeURIComponent(owner)}/${encodeURIComponent(repository)}`,
  );
  return data;
}

export async function getInsight(id: string): Promise<InsightReport> {
  const { data } = await http.get<InsightReport>(`/insights/${encodeURIComponent(id)}`);
  return data;
}