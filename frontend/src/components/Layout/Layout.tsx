import { Outlet } from 'react-router-dom';

import { Header } from './Header';
import { MobileNav, Sidebar } from './Sidebar';

export function Layout() {
  return (
    <div className="flex min-h-screen flex-col bg-slate-100 md:flex-row">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header />
        <MobileNav />
        <main className="flex-1 p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}