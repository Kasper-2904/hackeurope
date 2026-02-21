import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './App.css'

const queryClient = new QueryClient()

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <div className="min-h-screen bg-gray-50 text-gray-900">
          <nav className="p-4 bg-white shadow flex justify-between">
            <h1 className="text-xl font-bold">HackEurope Orchestrator</h1>
          </nav>
          <main className="p-8">
            <Routes>
              <Route path="/" element={<div className="text-center mt-10 text-2xl">Welcome to Orchestrator</div>} />
              <Route path="/dashboard" element={<div>Dashboard</div>} />
            </Routes>
          </main>
        </div>
      </Router>
    </QueryClientProvider>
  )
}

export default App
