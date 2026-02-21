// Tests for type constants.
// Verifies that our status/role constants have the expected values.

import { describe, it, expect } from "vitest";
import {
  TaskStatus,
  PlanStatus,
  SubtaskStatus,
  AgentStatus,
  RiskSeverity,
  RiskSource,
  UserRole,
  PricingType,
} from "./types";

describe("Type constants", () => {
  it("TaskStatus has all expected values", () => {
    expect(TaskStatus.PENDING).toBe("pending");
    expect(TaskStatus.ASSIGNED).toBe("assigned");
    expect(TaskStatus.IN_PROGRESS).toBe("in_progress");
    expect(TaskStatus.COMPLETED).toBe("completed");
    expect(TaskStatus.FAILED).toBe("failed");
    expect(TaskStatus.CANCELLED).toBe("cancelled");
  });

  it("PlanStatus has all expected values", () => {
    expect(PlanStatus.DRAFT).toBe("draft");
    expect(PlanStatus.PENDING_PM_APPROVAL).toBe("pending_pm_approval");
    expect(PlanStatus.APPROVED).toBe("approved");
    expect(PlanStatus.REJECTED).toBe("rejected");
    expect(PlanStatus.EXECUTED).toBe("executed");
  });

  it("SubtaskStatus has all expected values", () => {
    expect(SubtaskStatus.PENDING).toBe("pending");
    expect(SubtaskStatus.DRAFT_GENERATED).toBe("draft_generated");
    expect(SubtaskStatus.IN_REVIEW).toBe("in_review");
    expect(SubtaskStatus.APPROVED).toBe("approved");
    expect(SubtaskStatus.FINALIZED).toBe("finalized");
    expect(SubtaskStatus.REJECTED).toBe("rejected");
  });

  it("AgentStatus has all expected values", () => {
    expect(AgentStatus.PENDING).toBe("pending");
    expect(AgentStatus.ONLINE).toBe("online");
    expect(AgentStatus.BUSY).toBe("busy");
    expect(AgentStatus.OFFLINE).toBe("offline");
    expect(AgentStatus.ERROR).toBe("error");
  });

  it("RiskSource has all expected values", () => {
    expect(RiskSource.MERGE_CONFLICT).toBe("merge_conflict");
    expect(RiskSource.CI_FAILURE).toBe("ci_failure");
    expect(RiskSource.INTEGRATION).toBe("integration");
    expect(RiskSource.DEPENDENCY).toBe("dependency");
    expect(RiskSource.SECURITY).toBe("security");
    expect(RiskSource.REVIEWER).toBe("reviewer");
  });

  it("RiskSeverity has all expected values", () => {
    expect(RiskSeverity.LOW).toBe("low");
    expect(RiskSeverity.MEDIUM).toBe("medium");
    expect(RiskSeverity.HIGH).toBe("high");
    expect(RiskSeverity.CRITICAL).toBe("critical");
  });

  it("UserRole has all expected values", () => {
    expect(UserRole.ADMIN).toBe("admin");
    expect(UserRole.PM).toBe("pm");
    expect(UserRole.DEVELOPER).toBe("developer");
  });

  it("PricingType has all expected values", () => {
    expect(PricingType.FREE).toBe("free");
    expect(PricingType.USAGE_BASED).toBe("usage_based");
  });
});
