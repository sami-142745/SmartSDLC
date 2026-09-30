import { useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { getRepositoryMetrics } from '../api/dashboard';
import {
  performCodeAction,
  sendAssistantMessage,
} from '../api/assistant';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Spinner } from '../components/ui/Spinner';
import { PageContainer } from '../components/PageContainer';
import { PageHeader } from '../components/PageHeader';
import { ErrorState } from '../components/ErrorState';
import { Badge } from '../components/ui/Badge';
import { useAsync } from '../hooks/useAsync';
import { cn } from '../lib/cn';
import type {
  AssistantChatResponse,
  AssistantCodeActionResponse,
  AssistantContext,
  AssistantContextType,
  AssistantMode,
  AssistantMessage,
  ScmProvider,
} from '../types';
import { ASSISTANT_MODE_LABELS } from '../types';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  createdAt: number;
  cached?: boolean;
  model?: string | null;
  warnings?: string[];
}

const MODES: AssistantMode[] = [
  'explain_code',
  'explain_finding',
  'explain_architecture',
  'explain_repository',
  'explain_security',
  'explain_dependency',
  'debug_error',
  'refactor_code',
  'generate_tests',
  'explain_documentation',
  'explain_workflow',
];

const CONTEXT_TYPES: { value: AssistantContextType; label: string }[] = [
  { value: 'repository', label: 'Repository' },
  { value: 'file', label: 'File' },
  { value: 'code', label: 'Code' },
  { value: 'architecture_node', label: 'Architecture' },
  { value: 'security_finding', label: 'Security Finding' },
  { value: 'dependency', label: 'Dependency' },
  { value: 'workflow_event', label: 'Workflow' },
  { value: 'test_result', label: 'Test Result' },
];

const SUGGESTIONS = [
  'What is my current security posture?',
  'Which repositories are the biggest risk?',
  'Summarise recent review activity',
  'What do reviewers usually accept?',
  'Where should we focus next?',
];

/**
 * AI Developer Assistant.
 *
 * The assistant is context-aware: it receives only relevant SmartSDLC data,
 * never an entire repository. It uses local intelligence first, falling back
 * to Gemini only when language reasoning is actually needed.
 *
 * The UI clearly shows:
 * - Active context (what data the assistant can see)
 * - Mode (what kind of question is being asked)
 * - Whether the answer was cached (local) or required the LLM
 * - Warnings from the assistant
 */
export function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [thinking, setThinking] = useState(false);
  const [mode, setMode] = useState<AssistantMode>('explain_code');
  const [contextType, setContextType] = useState<AssistantContextType>('repository');
  const [contextData, setContextData] = useState<Record<string, string>>({});
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const repos = useAsync(() => getRepositoryMetrics(1, 50), []);
  const [searchParams] = useSearchParams();
  const provider: ScmProvider = searchParams.get('provider') === 'gitlab' ? 'gitlab' : 'github';

  const repoList = repos.data?.repositories ?? [];
  const [selectedRepo, setSelectedRepo] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedRepo && repoList.length > 0) {
      setSelectedRepo(`${repoList[0].owner}/${repoList[0].repository}`);
    }
  }, [repoList, selectedRepo]);

  const buildContext = (): AssistantContext | null => {
    if (!selectedRepo) return null;
    const [owner, repository] = selectedRepo.split('/');
    const base: AssistantContext = {
      context_type: contextType,
      repository_id: selectedRepo,
      owner,
      repository,
    };

    switch (contextType) {
      case 'file':
        return { ...base, file_path: contextData.file_path || undefined, file_language: contextData.file_language || undefined };
      case 'code':
        return { ...base, code_snippet: contextData.code_snippet || undefined };
      case 'security_finding':
        return {
          ...base,
          finding_title: contextData.finding_title || undefined,
          finding_description: contextData.finding_description || undefined,
          finding_severity: contextData.finding_severity || undefined,
          finding_file: contextData.finding_file || undefined,
        };
      case 'dependency':
        return {
          ...base,
          dependency_name: contextData.dependency_name || undefined,
          dependency_version: contextData.dependency_version || undefined,
        };
      default:
        return base;
    }
  };

  const send = async (text: string) => {
    const question = text.trim();
    if (!question || thinking) return;
    const now = Date.now();
    setMessages((prev) => [
      ...prev,
      { id: `u-${now}`, role: 'user', content: question, createdAt: now },
    ]);
    setInput('');
    setThinking(true);
    setError(null);

    try {
      const context = buildContext();
      const response = await sendAssistantMessage(
        selectedRepo?.split('/')[0] || '',
        selectedRepo?.split('/')[1] || '',
        {
          message: question,
          mode,
          context: context || undefined,
          conversation_id: conversationId || undefined,
        },
      );
      setConversationId(response.conversation_id);
      setMessages((prev) => [
        ...prev,
        {
          id: response.message.message_id,
          role: 'assistant',
          content: response.message.content,
          createdAt: Date.now(),
          cached: response.cached,
          model: response.model,
          warnings: response.warnings,
        },
      ]);
    } catch (err) {
      const msg = err && typeof err === 'object' && 'message' in err
        ? String(err.message)
        : err instanceof Error
          ? err.message
          : 'Failed to get response';
      setError(msg);
    } finally {
      setThinking(false);
    }
  };

  const performAction = async (actionType: 'explain' | 'refactor' | 'generate_tests' | 'suggest_fix') => {
    if (thinking) return;
    const context = buildContext();
    if (!context) return;
    setThinking(true);
    setError(null);
    try {
      const response = await performCodeAction(
        selectedRepo?.split('/')[0] || '',
        selectedRepo?.split('/')[1] || '',
        { action_type: actionType, context },
      );
      const now = Date.now();
      setMessages((prev) => [
        ...prev,
        {
          id: `a-${now}`,
          role: 'assistant',
          content: response.explanation,
          createdAt: now,
          cached: false,
          model: response.model,
        },
      ]);
    } catch (err) {
      const msg = err && typeof err === 'object' && 'message' in err
        ? String(err.message)
        : err instanceof Error
          ? err.message
          : 'Failed to perform action';
      setError(msg);
    } finally {
      setThinking(false);
    }
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' });
  }, [messages, thinking]);

  if (repos.loading) {
    return (
      <PageContainer>
        <div className="flex h-64 items-center justify-center">
          <Spinner />
        </div>
      </PageContainer>
    );
  }

  if (repos.error) {
    return (
      <ErrorState
        title="Could not load the AI Assistant"
        message={repos.error ?? undefined}
        retry={repos.refetch}
      />
    );
  }

  return (
    <PageContainer className="space-y-6">
      <PageHeader
        eyebrow="Assistant"
        title="AI Chat"
        description="Context-aware assistant that uses SmartSDLC data. Local intelligence first, Gemini when needed."
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
        {/* Left: Context & Mode */}
        <div className="space-y-4">
          <Card>
            <CardHeader title="Context" description="What the assistant can see" />
            <CardBody className="space-y-3">
              <div>
                <label className="text-[11px] uppercase tracking-wide text-ink-subtle">
                  Repository
                </label>
                <select
                  value={selectedRepo || ''}
                  onChange={(e) => setSelectedRepo(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-white/[0.09] bg-surface-2 px-3 py-2 text-[13px] text-ink"
                >
                  {repoList.map((repo) => (
                    <option key={`${repo.owner}/${repo.repository}`} value={`${repo.owner}/${repo.repository}`}>
                      {repo.owner}/{repo.repository}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-wide text-ink-subtle">
                  Context Type
                </label>
                <select
                  value={contextType}
                  onChange={(e) => setContextType(e.target.value as AssistantContextType)}
                  className="mt-1 w-full rounded-lg border border-white/[0.09] bg-surface-2 px-3 py-2 text-[13px] text-ink"
                >
                  {CONTEXT_TYPES.map((ct) => (
                    <option key={ct.value} value={ct.value}>
                      {ct.label}
                    </option>
                  ))}
                </select>
              </div>
              {contextType === 'file' && (
                <div>
                  <label className="text-[11px] uppercase tracking-wide text-ink-subtle">
                    File Path
                  </label>
                  <input
                    value={contextData.file_path || ''}
                    onChange={(e) => setContextData((prev) => ({ ...prev, file_path: e.target.value }))}
                    placeholder="src/main.py"
                    className="mt-1 w-full rounded-lg border border-white/[0.09] bg-surface-2 px-3 py-2 text-[13px] text-ink"
                  />
                </div>
              )}
              {contextType === 'code' && (
                <div>
                  <label className="text-[11px] uppercase tracking-wide text-ink-subtle">
                    Code Snippet
                  </label>
                  <textarea
                    value={contextData.code_snippet || ''}
                    onChange={(e) => setContextData((prev) => ({ ...prev, code_snippet: e.target.value }))}
                    placeholder="Paste code here..."
                    rows={4}
                    className="mt-1 w-full rounded-lg border border-white/[0.09] bg-surface-2 px-3 py-2 font-mono text-[12px] text-ink"
                  />
                </div>
              )}
              {contextType === 'security_finding' && (
                <>
                  <div>
                    <label className="text-[11px] uppercase tracking-wide text-ink-subtle">
                      Finding Title
                    </label>
                    <input
                      value={contextData.finding_title || ''}
                      onChange={(e) => setContextData((prev) => ({ ...prev, finding_title: e.target.value }))}
                      className="mt-1 w-full rounded-lg border border-white/[0.09] bg-surface-2 px-3 py-2 text-[13px] text-ink"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] uppercase tracking-wide text-ink-subtle">
                      Description
                    </label>
                    <textarea
                      value={contextData.finding_description || ''}
                      onChange={(e) => setContextData((prev) => ({ ...prev, finding_description: e.target.value }))}
                      rows={3}
                      className="mt-1 w-full rounded-lg border border-white/[0.09] bg-surface-2 px-3 py-2 text-[13px] text-ink"
                    />
                  </div>
                </>
              )}
              {contextType === 'dependency' && (
                <>
                  <div>
                    <label className="text-[11px] uppercase tracking-wide text-ink-subtle">
                      Dependency Name
                    </label>
                    <input
                      value={contextData.dependency_name || ''}
                      onChange={(e) => setContextData((prev) => ({ ...prev, dependency_name: e.target.value }))}
                      className="mt-1 w-full rounded-lg border border-white/[0.09] bg-surface-2 px-3 py-2 text-[13px] text-ink"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] uppercase tracking-wide text-ink-subtle">
                      Version
                    </label>
                    <input
                      value={contextData.dependency_version || ''}
                      onChange={(e) => setContextData((prev) => ({ ...prev, dependency_version: e.target.value }))}
                      className="mt-1 w-full rounded-lg border border-white/[0.09] bg-surface-2 px-3 py-2 text-[13px] text-ink"
                    />
                  </div>
                </>
              )}
              {repos.data && (
                <p className="text-[11px] text-ink-faint">Context loaded</p>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Mode" description="What kind of question" />
            <CardBody>
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value as AssistantMode)}
                className="w-full rounded-lg border border-white/[0.09] bg-surface-2 px-3 py-2 text-[13px] text-ink"
              >
                {MODES.map((m) => (
                  <option key={m} value={m}>
                    {ASSISTANT_MODE_LABELS[m]}
                  </option>
                ))}
              </select>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Code Actions" />
            <CardBody className="space-y-2">
              <Button variant="secondary" size="sm" onClick={() => performAction('explain')} disabled={thinking} className="w-full">
                Explain Code
              </Button>
              <Button variant="secondary" size="sm" onClick={() => performAction('refactor')} disabled={thinking} className="w-full">
                Refactor
              </Button>
              <Button variant="secondary" size="sm" onClick={() => performAction('generate_tests')} disabled={thinking} className="w-full">
                Generate Tests
              </Button>
              <Button variant="secondary" size="sm" onClick={() => performAction('suggest_fix')} disabled={thinking} className="w-full">
                Suggest Fix
              </Button>
            </CardBody>
          </Card>
        </div>

        {/* Center: Chat */}
        <div className="lg:col-span-3">
          <Card className="flex h-[700px] flex-col overflow-hidden">
            <CardBody className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4 sm:p-5">
              {messages.length === 0 ? (
                <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-accent-violet/20 bg-accent-violet/10">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-5 w-5 text-accent-lavender" aria-hidden="true">
                      <path d="M12 3l1.9 4.6L18.5 9.5 13.9 11.4 12 16l-1.9-4.6L5.5 9.5l4.6-1.9L12 3Z" strokeLinejoin="round" />
                    </svg>
                  </div>
                  <p className="max-w-sm text-[13px] leading-relaxed text-ink-subtle">
                    Ask about your code, findings, architecture, or dependencies. The assistant uses SmartSDLC data to answer.
                  </p>
                </div>
              ) : (
                messages.map((message) => (
                  <div
                    key={message.id}
                    className={cn('flex', message.role === 'user' ? 'justify-end' : 'justify-start')}
                  >
                    <div
                      className={cn(
                        'max-w-[85%] rounded-2xl px-4 py-3 text-[13px] leading-relaxed whitespace-pre-wrap',
                        message.role === 'user'
                          ? 'rounded-br-md bg-accent-violet text-white'
                          : 'glass-subtle rounded-bl-md text-ink-muted',
                      )}
                    >
                      {message.content}
                      {message.cached && (
                        <span className="mt-1 block text-[10px] text-ink-faint">
                          Answered locally (no LLM)
                        </span>
                      )}
                      {message.warnings && message.warnings.length > 0 && (
                        <div className="mt-2 space-y-1">
                          {message.warnings.map((warning, i) => (
                            <p key={i} className="text-[10px] text-amber-300">
                              {warning}
                            </p>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}

              {thinking ? (
                <div className="flex justify-start">
                  <div className="glass-subtle flex items-center gap-2 rounded-2xl rounded-bl-md px-4 py-3 text-[13px] text-ink-faint">
                    <Spinner size="sm" />
                    Thinking...
                  </div>
                </div>
              ) : null}

              {error ? (
                <div className="rounded-lg border border-rose-500/25 bg-rose-500/[0.06] px-3 py-2 text-[12px] text-rose-300">
                  {error}
                </div>
              ) : null}

              <div ref={bottomRef} />
            </CardBody>

            <div className="border-t border-white/[0.06] p-3 sm:p-4">
              {messages.length === 0 ? (
                <div className="mb-3 flex flex-wrap gap-1.5">
                  {SUGGESTIONS.map((suggestion) => (
                    <button
                      key={suggestion}
                      type="button"
                      onClick={() => send(suggestion)}
                      className="chip border-white/[0.08] bg-white/[0.04] text-ink-subtle transition-colors hover:border-accent-violet/30 hover:text-ink"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              ) : null}

              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  send(input);
                }}
                className="flex items-center gap-2"
              >
                <input
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  placeholder="Ask about your code..."
                  aria-label="Message"
                  className="field flex-1"
                />
                <Button type="submit" variant="primary" disabled={thinking || input.trim().length === 0}>
                  Send
                </Button>
              </form>
            </div>
          </Card>
        </div>
      </div>
    </PageContainer>
  );
}
