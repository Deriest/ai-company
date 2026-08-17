// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import type { ReactNode } from "react";
import { render, screen, cleanup } from "@testing-library/react";
import { ErrorBoundary } from "./ErrorBoundary";

function OkChild() {
  return <div>healthy view</div>;
}

function Boom(): ReactNode {
  throw new Error("boom");
}

describe("ErrorBoundary", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders children when nothing throws", () => {
    render(
      <ErrorBoundary>
        <OkChild />
      </ErrorBoundary>
    );
    expect(screen.getByText("healthy view")).toBeTruthy();
  });

  it("shows the fallback with a Reload App button when a child throws", () => {
    // React logs caught boundary errors to console.error — silence it.
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>
    );
    expect(screen.getByText("Something went wrong")).toBeTruthy();
    expect(screen.getByText("Reload App")).toBeTruthy();
    expect(spy).toHaveBeenCalled();
  });

  it("renders a custom label when provided", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ErrorBoundary label="View failed to render">
        <Boom />
      </ErrorBoundary>
    );
    expect(screen.getByText("View failed to render")).toBeTruthy();
    expect(screen.getByText("Reload App")).toBeTruthy();
    expect(spy).toHaveBeenCalled();
  });
});