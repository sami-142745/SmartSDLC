import { http } from './client';
import type { FeedbackLearningResponse } from '../types';

export async function getFeedbackLearning(): Promise<FeedbackLearningResponse> {
  const { data } = await http.get<FeedbackLearningResponse>('/feedback/learning');
  return data;
}