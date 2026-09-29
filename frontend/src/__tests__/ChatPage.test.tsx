import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const mocks = vi.hoisted(() => ({
  getDashboard: vi.fn(),
  getFeedbackSummary: vi.fn(),
  getRepositoryMetrics: vi.fn(),
  getHistory: vi.fn(),
  getInsights: vi.fn(),
  getDocumentations: vi.fn(),
  getFeedbackLearning: vi.fn(),
  sendAssistantMessage: vi.fn(),
  performCodeAction: vi.fn(),
}));

vi.mock('../api/dashboard', () => mocks);
vi.mock('../api/insights', () => ({
  getInsights: mocks.getInsights,
  generateInsight: vi.fn(),
  getLatestRepositoryInsight: vi.fn(),
  getInsight: vi.fn(),
}));
vi.mock('../api/documents', () => ({
  getDocumentations: mocks.getDocumentations,
  generateDocumentation: vi.fn(),
  getDocumentation: vi.fn(),
  getRepositoryDocumentation: vi.fn(),
}));
vi.mock('../api/feedback_learning', () => ({ getFeedbackLearning: mocks.getFeedbackLearning }));
vi.mock('../api/assistant', () => ({
  sendAssistantMessage: mocks.sendAssistantMessage,
  performCodeAction: mocks.performCodeAction,
}));

import { ChatPage } from '../pages/ChatPage';
import { dashboardSummary, feedbackSummary, repoMetrics, TEST_TOKEN } from '../test/fixtures';
import { renderWithProviders } from '../test/utils';

beforeEach(() => {
  mocks.getDashboard.mockReset().mockResolvedValue(dashboardSummary);
  mocks.getFeedbackSummary.mockReset().mockResolvedValue(feedbackSummary);
  mocks.getRepositoryMetrics.mockReset().mockResolvedValue(repoMetrics);
  mocks.getHistory.mockReset().mockResolvedValue({
    items: [],
    page: 1,
    per_page: 5,
    total: 0,
    total_pages: 0,
  });
  mocks.getInsights.mockReset().mockResolvedValue({
    items: [],
    page: 1,
    per_page: 5,
    total: 0,
    total_pages: 0,
  });
  mocks.getDocumentations.mockReset().mockResolvedValue({
    items: [],
    page: 1,
    per_page: 10,
    total: 0,
    total_pages: 0,
  });
  mocks.getFeedbackLearning.mockReset().mockResolvedValue({
    profiles: [],
    repositories: [],
    categories: [],
    total_feedback: 0,
    data_available: false,
  });
  mocks.sendAssistantMessage.mockReset().mockImplementation((_owner, _repo, request) => {
    const message = (request.message || '').toLowerCase();
    let reply: string;
    if (message.includes('security posture')) {
      reply = 'Your weighted posture score is 72 out of 100. Across 5 reviews there are 23 findings, including 2 critical and 7 high.';
    } else if (message.includes('biggest risk')) {
      reply = 'Biggest risk concentration: acme/webapp has the highest exposure with 12 findings.';
    } else if (message.includes('focus next') || message.includes('where should we focus')) {
      reply = 'Based on your data, you should focus on security testing and code quality improvements.';
    } else if (!message) {
      reply = 'Context loaded';
    } else {
      reply = 'Here is what I found in your repository data.';
    }
    return Promise.resolve({
      message: {
        message_id: 'msg_1',
        role: 'assistant',
        content: reply,
        created_at: '2026-01-01T00:00:00Z',
        cached: true,
      },
      conversation_id: 'conv_1',
      cached: true,
      warnings: [],
    });
  });
  mocks.performCodeAction.mockReset().mockResolvedValue({
    original_code: 'const x = 1;',
    generated_code: 'const x = 2;',
    explanation: 'Refactored for clarity.',
    diff: '- const x = 1;\n+ const x = 2;',
  });
});

describe('ChatPage', () => {
  it('renders the assistant with the loaded context summary', async () => {
    renderWithProviders(<ChatPage />, { route: '/chat', authToken: TEST_TOKEN });

    expect(await screen.findByRole('heading', { name: 'AI Chat' })).toBeInTheDocument();
    expect(await screen.findByText('Context loaded')).toBeInTheDocument();
    expect(screen.getByLabelText('Message')).toBeInTheDocument();
  });

  it('answers a security posture question from the loaded dashboard data', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ChatPage />, { route: '/chat', authToken: TEST_TOKEN });

    const input = await screen.findByLabelText('Message');
    await user.type(input, 'What is my current security posture?');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(screen.getByText(/weighted posture score is/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/Across 5 reviews there are 23 findings, including 2 critical and 7 high/i)).toBeInTheDocument();
  });

  it('answers a risky-repository question by ranking exposure', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ChatPage />, { route: '/chat', authToken: TEST_TOKEN });

    const input = await screen.findByLabelText('Message');
    await user.type(input, 'Which repositories are the biggest risk?');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() => {
      expect(screen.getByText(/Biggest risk concentration/i)).toBeInTheDocument();
    });
    expect(screen.getAllByText(/acme\/webapp/).length).toBeGreaterThan(0);
  });

  it('uses the suggested prompts to seed the composer', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ChatPage />, { route: '/chat', authToken: TEST_TOKEN });

    const suggestion = await screen.findByRole('button', {
      name: 'Where should we focus next?',
    });
    await user.click(suggestion);

    expect(screen.getByText('Where should we focus next?')).toBeInTheDocument();
  });
});
