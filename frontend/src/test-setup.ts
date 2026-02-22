// This file runs before every test.
// It adds helpful matchers like toBeInTheDocument().
import "@testing-library/jest-dom/vitest";

// Mock localStorage for jsdom
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value;
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
    get length() {
      return Object.keys(store).length;
    },
    key: (index: number) => Object.keys(store)[index] || null,
  };
})();

Object.defineProperty(globalThis, "localStorage", {
  value: localStorageMock,
});

// Auto-import React for JSX in tests
import React from "react";
// eslint-disable-next-line @typescript-eslint/no-explicit-any
(globalThis as any).React = React;
