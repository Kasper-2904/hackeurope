import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Navigate, BrowserRouter as Router, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { ProtectedRoute } from '@/components/routing/ProtectedRoute'
import { PublicOnlyRoute } from '@/components/routing/PublicOnlyRoute'
import { TooltipProvider } from '@/components/ui/tooltip'
import { AuthProvider } from '@/context/AuthContext'
import AgentDetailPage from '@/pages/AgentDetailPage'
import { DashboardPage } from '@/pages/DashboardPage'
import ContextExplorerPage from '@/pages/ContextExplorerPage'
import { LoginPage } from '@/pages/LoginPage'
import MarketplacePage from '@/pages/MarketplacePage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { RegisterPage } from '@/pages/RegisterPage'
import TaskDetailPage from '@/pages/TaskDetailPage'
import TaskListPage from '@/pages/TaskListPage'

const queryClient = new QueryClient()

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <AuthProvider>
          <Router>
            <Routes>
              <Route element={<PublicOnlyRoute />}>
                <Route path="/login" element={<LoginPage />} />
                <Route path="/register" element={<RegisterPage />} />
              </Route>

              <Route element={<ProtectedRoute />}>
                <Route element={<AppShell />}>
                  <Route path="/" element={<Navigate to="/dashboard" replace />} />
                  <Route path="/dashboard" element={<DashboardPage />} />
                  <Route path="/tasks" element={<TaskListPage />} />
                  <Route path="/tasks/:id" element={<TaskDetailPage />} />
                  <Route path="/marketplace" element={<MarketplacePage />} />
                  <Route path="/marketplace/:agentId" element={<AgentDetailPage />} />
                  <Route path="/context" element={<ContextExplorerPage />} />
                  <Route path="/projects" element={<div>Projects - Marin M2-T4</div>} />
                  <Route path="/projects/:id" element={<div>Project Detail - Marin M2-T4</div>} />
                  <Route path="/billing" element={<div>Billing - Marin M3-T4</div>} />
                </Route>
              </Route>

              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </Router>
        </AuthProvider>
      </TooltipProvider>
    </QueryClientProvider>
  )
}

export default App
