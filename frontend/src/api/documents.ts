import { http } from './client';
import type {
  DocumentationListResponse,
  GeneratedDocumentation,
  GenerateDocumentationRequest,
} from '../types';

export async function generateDocumentation(
  payload: GenerateDocumentationRequest,
): Promise<GeneratedDocumentation> {
  const { data } = await http.post<GeneratedDocumentation>('/documents/generate', payload);
  return data;
}

export async function getDocumentations(params: {
  page?: number;
  perPage?: number;
  repository?: string;
  owner?: string;
} = {}): Promise<DocumentationListResponse> {
  const { data } = await http.get<DocumentationListResponse>('/documents', {
    params: {
      page: params.page ?? 1,
      per_page: params.perPage ?? 20,
      ...(params.repository ? { repository: params.repository } : {}),
      ...(params.owner ? { owner: params.owner } : {}),
    },
  });
  return data;
}

export async function getDocumentation(id: string): Promise<GeneratedDocumentation> {
  const { data } = await http.get<GeneratedDocumentation>(
    `/documents/${encodeURIComponent(id)}`,
  );
  return data;
}

export async function getRepositoryDocumentation(
  owner: string,
  repository: string,
  pullRequest?: number,
): Promise<GeneratedDocumentation> {
  const { data } = await http.get<GeneratedDocumentation>(
    `/documents/repository/${encodeURIComponent(owner)}/${encodeURIComponent(repository)}`,
    { params: pullRequest ? { pull_request: pullRequest } : {} },
  );
  return data;
}