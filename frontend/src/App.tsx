import { BrowserRouter as Router, Routes, Route, Link } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/components/ui/tooltip";

import TaskListPage from "@/pages/TaskListPage";
import TaskDetailPage from "@/pages/TaskDetailPage";
import MarketplacePage from "@/pages/MarketplacePage";
import AgentDetailPage from "@/pages/AgentDetailPage";
import ContextExplorerPage from "@/pages/ContextExplorerPage";

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Router>
          <div className="min-h-screen bg-background text-foreground">
            {/* Top navigation bar */}
            <nav className="border-b bg-card px-6 py-3 flex items-center gap-6">
              <h1 className="text-lg font-semibold">Orchestrator</h1>
              <div className="flex gap-4 text-sm">
                <Link to="/" className="text-muted-foreground hover:text-foreground transition-colors">
                  Home
                </Link>
                <Link to="/tasks" className="text-muted-foreground hover:text-foreground transition-colors">
                  Tasks
                </Link>
                <Link to="/marketplace" className="text-muted-foreground hover:text-foreground transition-colors">
                  Marketplace
                </Link>
                <Link to="/context" className="text-muted-foreground hover:text-foreground transition-colors">
                  Context
                </Link>
              </div>
            </nav>

            {/* Page content */}
            <main className="p-6 max-w-7xl mx-auto">
              <Routes>
                {/* Home / landing */}
                <Route
                  path="/"
                  element={
                    <div className="text-center mt-10 text-2xl text-muted-foreground">
                      Welcome to the Orchestrator
                    </div>
                  }
                />

                {/* Martin's pages */}
                <Route path="/tasks" element={<TaskListPage />} />
                <Route path="/tasks/:id" element={<TaskDetailPage />} />
                <Route path="/marketplace" element={<MarketplacePage />} />
                <Route path="/marketplace/:agentId" element={<AgentDetailPage />} />
                <Route path="/context" element={<ContextExplorerPage />} />

                {/* Marin's pages (placeholders) */}
                <Route path="/dashboard" element={<div>Dashboard — Marin M1-T4</div>} />
                <Route path="/projects" element={<div>Projects — Marin M2-T4</div>} />
                <Route path="/projects/:id" element={<div>Project Detail — Marin M2-T4</div>} />
                <Route path="/billing" element={<div>Billing — Marin M3-T4</div>} />
              </Routes>
            </main>
          </div>
        </Router>
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
