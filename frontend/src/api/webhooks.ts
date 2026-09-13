import { http } from './client';
import type { WebhookEventListResponse } from '../types';

export async function getWebhookEvents(params?: { page?: number; per_page?: number }): Promise<WebhookEventListResponse> {
  const { data } = await http.get<WebhookEventListResponse>('/webhook/events', { params });
  return data;
}