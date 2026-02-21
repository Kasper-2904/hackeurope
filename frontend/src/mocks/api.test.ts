// Tests for the mock API service.
// These verify that each function returns data in the correct shape,
// so when we swap to real API calls later, we know what to expect.

import { describe, it, expect } from "vitest";
import {
  getTasks,
  getTask,
  getSubtasks,
  getProjects,
  getProject,
  getTeamMembers,
  getPlans,
  getRiskSignals,
  getMarketplaceCatalog,
  getMarketplaceAgent,
  getDeveloperDashboard,
} from "./api";

describe("getTasks", () => {
  it("returns an array of tasks", async () => {
    const tasks = await getTasks();
    expect(Array.isArray(tasks)).toBe(true);
    expect(tasks.length).toBeGreaterThan(0);
  });

  it("each task has required fields", async () => {
    const tasks = await getTasks();
    for (const task of tasks) {
      expect(task).toHaveProperty("id");
      expect(task).toHaveProperty("title");
      expect(task).toHaveProperty("status");
      expect(task).toHaveProperty("progress");
    }
  });
});

describe("getTask", () => {
  it("returns a task when given a valid id", async () => {
    const task = await getTask("task-1");
    expect(task).toBeDefined();
    expect(task!.id).toBe("task-1");
  });

  it("returns undefined for an unknown id", async () => {
    const task = await getTask("nonexistent");
    expect(task).toBeUndefined();
  });
});

describe("getSubtasks", () => {
  it("returns subtasks for a valid task id", async () => {
    const subtasks = await getSubtasks("task-2");
    expect(Array.isArray(subtasks)).toBe(true);
    expect(subtasks.length).toBeGreaterThan(0);
    for (const sub of subtasks) {
      expect(sub.task_id).toBe("task-2");
    }
  });

  it("returns empty array for a task with no subtasks", async () => {
    const subtasks = await getSubtasks("nonexistent");
    expect(subtasks).toEqual([]);
  });
});

describe("getProjects", () => {
  it("returns an array of projects", async () => {
    const projects = await getProjects();
    expect(Array.isArray(projects)).toBe(true);
    expect(projects.length).toBeGreaterThan(0);
  });

  it("each project has required fields", async () => {
    const projects = await getProjects();
    for (const project of projects) {
      expect(project).toHaveProperty("id");
      expect(project).toHaveProperty("name");
      expect(project).toHaveProperty("goals");
    }
  });
});

describe("getProject", () => {
  it("returns a project for a valid id", async () => {
    const project = await getProject("proj-1");
    expect(project).toBeDefined();
    expect(project!.id).toBe("proj-1");
  });

  it("returns undefined for an unknown id", async () => {
    const project = await getProject("nonexistent");
    expect(project).toBeUndefined();
  });
});

describe("getTeamMembers", () => {
  it("returns team members for a valid project", async () => {
    const members = await getTeamMembers("proj-1");
    expect(Array.isArray(members)).toBe(true);
    expect(members.length).toBeGreaterThan(0);
    for (const member of members) {
      expect(member.project_id).toBe("proj-1");
    }
  });

  it("returns empty array for unknown project", async () => {
    const members = await getTeamMembers("nonexistent");
    expect(members).toEqual([]);
  });
});

describe("getPlans", () => {
  it("returns all plans when no filter", async () => {
    const plans = await getPlans();
    expect(Array.isArray(plans)).toBe(true);
    expect(plans.length).toBeGreaterThan(0);
  });

  it("filters by task id", async () => {
    const plans = await getPlans("task-2");
    for (const plan of plans) {
      expect(plan.task_id).toBe("task-2");
    }
  });
});

describe("getRiskSignals", () => {
  it("returns all risks when no filter", async () => {
    const risks = await getRiskSignals();
    expect(Array.isArray(risks)).toBe(true);
    expect(risks.length).toBeGreaterThan(0);
  });

  it("filters by task id", async () => {
    const risks = await getRiskSignals("task-2");
    for (const risk of risks) {
      expect(risk.task_id).toBe("task-2");
    }
  });
});

describe("getMarketplaceCatalog", () => {
  it("returns all marketplace agents", async () => {
    const agents = await getMarketplaceCatalog();
    expect(Array.isArray(agents)).toBe(true);
    expect(agents.length).toBeGreaterThan(0);
  });

  it("filters by category", async () => {
    const agents = await getMarketplaceCatalog("testing");
    for (const agent of agents) {
      expect(agent.category).toBe("testing");
    }
  });

  it("each agent has pricing fields", async () => {
    const agents = await getMarketplaceCatalog();
    for (const agent of agents) {
      expect(agent).toHaveProperty("pricing_type");
      expect(agent).toHaveProperty("is_verified");
      expect(agent).toHaveProperty("is_active");
    }
  });
});

describe("getMarketplaceAgent", () => {
  it("returns an agent for a valid id", async () => {
    const agent = await getMarketplaceAgent("mp-1");
    expect(agent).toBeDefined();
    expect(agent!.id).toBe("mp-1");
  });

  it("returns undefined for an unknown id", async () => {
    const agent = await getMarketplaceAgent("nonexistent");
    expect(agent).toBeUndefined();
  });
});

describe("getDeveloperDashboard", () => {
  it("returns dashboard data for a user", async () => {
    const dashboard = await getDeveloperDashboard("user-1");
    expect(dashboard.user_id).toBe("user-1");
    expect(Array.isArray(dashboard.assigned_tasks)).toBe(true);
    expect(Array.isArray(dashboard.assigned_subtasks)).toBe(true);
    expect(Array.isArray(dashboard.pending_reviews)).toBe(true);
    expect(Array.isArray(dashboard.recent_risks)).toBe(true);
    expect(typeof dashboard.workload).toBe("number");
  });
});
