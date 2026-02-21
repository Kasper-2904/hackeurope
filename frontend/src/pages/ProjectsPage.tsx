import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { listProjects } from '@/lib/pmApi'
import { toApiErrorMessage } from '@/lib/apiClient'

export default function ProjectsPage() {
  const projectsQuery = useQuery({
    queryKey: ['projects'],
    queryFn: listProjects,
  })

  if (projectsQuery.isLoading) {
    return <p className="text-sm text-slate-600">Loading projects...</p>
  }

  if (projectsQuery.isError) {
    return <p className="text-sm text-red-600">{toApiErrorMessage(projectsQuery.error, 'Failed to load projects.')}</p>
  }

  const projects = projectsQuery.data ?? []

  if (projects.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Projects</CardTitle>
          <CardDescription>No projects found for your workspace.</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  return (
    <section className="space-y-4">
      <h2 className="text-2xl font-semibold">Projects</h2>
      <div className="grid gap-4 md:grid-cols-2">
        {projects.map((project) => (
          <Card key={project.id}>
            <CardHeader>
              <CardTitle>{project.name}</CardTitle>
              <CardDescription>{project.description ?? 'No project description available.'}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <p className="text-sm text-slate-600">Goals: {project.goals.length}</p>
              <Link className="text-sm font-medium text-sky-700 hover:underline" to={`/projects/${project.id}`}>
                Open PM dashboard
              </Link>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  )
}
