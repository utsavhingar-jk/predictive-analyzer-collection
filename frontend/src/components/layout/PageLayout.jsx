import { Header } from "./Header";

export function PageLayout({ title, subtitle, children }) {
  return (
    <div className="flex flex-col h-full">
      <Header title={title} subtitle={subtitle} />
      <main className="flex-1 overflow-y-auto p-6 animate-fade-in">{children}</main>
    </div>
  );
}
