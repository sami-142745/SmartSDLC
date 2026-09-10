import { http } from './client';
import type { FeedbackAction, FeedbackHistoryResponse, FeedbackItem, ReviewResponse } from '../types';

export async function runReview(
  owner: string,
  repo: string,
  number: number,
): Promise<ReviewResponse> {
  const { data } = await http.post<ReviewResponse>(
    `/reviews/${owner}/${repo}/${number}`,
  );
  return data;
}

export async function getReviews(
  owner: string,
  repo: string,
  number: number,
): Promise<ReviewResponse[]> {
  const { data } = await http.get<ReviewResponse[]>(
    `/reviews/${owner}/${repo}/${number}`,
  );
  return data;
}

export async function getReviewFindings(
  owner: string,
  repo: string,
  number: number,
): Promise<{ review_id: string; findings: ReviewResponse['findings'] }> {
  const { data } = await http.get<{
    review_id: string;
    findings: ReviewResponse['findings'];
  }>(`/reviews/${owner}/${repo}/${number}/findings`);
  return data;
}

export async function submitFeedback(
  owner: string,
  repo: string,
  number: number,
  findingId: string,
  action: FeedbackAction,
): Promise<FeedbackItem> {
  const { data } = await http.post<FeedbackItem>(
    `/reviews/${owner}/${repo}/${number}/findings/${findingId}/feedback`,
    { action },
  );
  return data;
}

export async function getFeedbackHistory(
  page = 1,
  perPage = 20,
): Promise<FeedbackHistoryResponse> {
  const { data } = await http.get<FeedbackHistoryResponse>('/reviews/feedback', {
    params: { page, per_page: perPage },
  });
  return data;
}