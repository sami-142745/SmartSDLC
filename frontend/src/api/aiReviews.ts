import { http } from './client';
import type {
  AiReview,
  AiReviewFindingsQuery,
  AiReviewFindingsResponse,
  CreateAiReviewRequest,
  ScmProvider,
} from '../types';

/**
 * Sprint 3 AI review endpoints (backend schema v2).
 *
 * These are additive and deliberately do not touch the helpers in
 * `reviews.ts`: the legacy `/reviews/{owner}/{repo}/{number}` contract is still
 * what the dashboard, insights and feedback history read, and rewriting it
 * would be a breaking change. Requests go to the root path because that is
 * where every other router in this app is mounted.
 */

export async function createAiReview(request: CreateAiReviewRequest): Promise<AiReview> {
  const { data } = await http.post<AiReview>('/reviews', request);
  return data;
}

export async function getAiReview(reviewId: string): Promise<AiReview> {
  const { data } = await http.get<AiReview>(`/reviews/${reviewId}`);
  return data;
}

export async function getAiReviewFindings(
  reviewId: string,
  query: AiReviewFindingsQuery = {},
): Promise<AiReviewFindingsResponse> {
  // Drop empty values so the request URL stays clean and cacheable.
  const params = Object.fromEntries(
    Object.entries(query).filter(([, value]) => value !== undefined && value !== ''),
  );
  const { data } = await http.get<AiReviewFindingsResponse>(`/reviews/${reviewId}/findings`, {
    params,
  });
  return data;
}

/** Convenience wrapper for the "Run AI review" button on the PR page. */
export async function runAiReview(
  owner: string,
  repository: string,
  pullRequestNumber: number,
  provider: ScmProvider = 'github',
): Promise<AiReview> {
  return createAiReview({ owner, repository, pull_request_number: pullRequestNumber, provider });
}
