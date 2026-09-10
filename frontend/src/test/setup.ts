import '@testing-library/jest-dom';

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

const win = window as unknown as Record<string, unknown>;
if (!win.ResizeObserver) {
  win.ResizeObserver = ResizeObserverMock;
}