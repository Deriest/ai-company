// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor, act, cleanup } from "@testing-library/react";

// Vitest globals are off, so @testing-library/react's auto-cleanup never
// registers — unmount explicitly between tests or the composer buttons from a
// previous render leak into the next one.
afterEach(() => cleanup());

const mocks = vi.hoisted(() => ({
  executeAgent: vi.fn(),
}));
vi.mock("../lib/api/chat", () => ({ chatApi: { executeAgent: mocks.executeAgent } }));
vi.mock("../lib/api/conversations", () => ({
  conversationsApi: {
    list: vi.fn().mockResolvedValue([]),
    search: vi.fn().mockResolvedValue([]),
    create: vi.fn().mockResolvedValue({
      id: "conv-1",
      title: "New Session",
      folder_id: null,
      is_archived: false,
      is_favorite: false,
      is_pinned: false,
      tags: [],
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    }),
    getMany: vi.fn().mockResolvedValue([]),
    listMessages: vi.fn().mockResolvedValue([]),
    delete: vi.fn().mockResolvedValue(undefined),
    duplicate: vi.fn().mockResolvedValue({}),
    updateMessage: vi.fn().mockResolvedValue({}),
  },
}));
vi.mock("../lib/api/providers", () => ({
  providersApi: {
    list: vi.fn().mockResolvedValue([]),
    fetchModelsAndUpdate: vi.fn(),
  },
}));
vi.mock("../lib/api/provider_manage", () => ({
  providerManageApi: {
    getEnvConfig: vi.fn().mockResolvedValue({
      base_url: "",
      api_key: "",
      provider_name: "",
      thinker: "",
      crafter: "",
      sprinter: "",
      vision: "",
    }),
    updateEnvConfig: vi.fn().mockResolvedValue({ success: true }),
  },
}));
vi.mock("../lib/api/projects", () => ({
  projectsApi: {
    list: vi.fn().mockResolvedValue([]),
    getActive: vi.fn().mockResolvedValue(null),
    activate: vi.fn().mockResolvedValue(undefined),
    create: vi.fn().mockResolvedValue({}),
  },
}));

import { ChatView } from "./ChatView";

describe("M1 — clarify releases the send lock", () => {
  beforeEach(() => {
    mocks.executeAgent.mockReset().mockResolvedValue(() => {}); // returns an abort function
    try { sessionStorage.clear(); } catch { /* jsdom no-op */ }
  });

  it("unlocks the composer and renders the clarify block when the backend asks for details", async () => {
    const view = <ChatView health="ok" currentProvider={null} newSessionSignal={0} />;
    render(view);

    // Find the textarea placeholder visible initially (activeId is null)
    const textarea = await screen.findByPlaceholderText(/type a message/i);
    expect(textarea).toBeTruthy();

    // Sanity: not sending yet — the button offers to send.
    expect(screen.getByLabelText("Send message")).toBeTruthy();

    fireEvent.change(textarea as HTMLTextAreaElement, { target: { value: "build me a thing" } });

    fireEvent.click(screen.getByLabelText("Send message"));

    // Wait for executeAgent to be called (the API was mocked and immediately resolved)
    await waitFor(() => expect(mocks.executeAgent).toHaveBeenCalledTimes(1));

    // While streaming, the composer is locked (Stop generation)
    expect(screen.getByLabelText("Stop generation")).toBeTruthy();

    const callbacks = mocks.executeAgent.mock.calls[0][1];

    // Simulate the backend's clarify event
    await act(async () => {
      callbacks.onClarify({
        reason: "Missing project",
        questions: [
          { id: "proj", question: "Which repo should I work in?", options: ["blog", "api"] },
        ],
      });
    });

    // Structured question block is rendered via ClarifyBlock
    expect(screen.getByText("Which repo should I work in?")).toBeTruthy();

    // And the composer is unlocked so the user can answer (M1).
    expect(screen.getByLabelText("Send message")).toBeTruthy();
    expect(screen.queryByLabelText("Stop generation")).toBeFalsy();
  });

  it("a late done after clarify is a no-op (message stays clarified, lock stays released)", async () => {
    const view = <ChatView health="ok" currentProvider={null} newSessionSignal={0} />;
    render(view);

    const textarea = await screen.findByPlaceholderText(/type a message/i);
    expect(textarea).toBeTruthy();
    fireEvent.change(textarea as HTMLTextAreaElement, { target: { value: "build me a thing" } });
    fireEvent.click(screen.getByLabelText("Send message"));

    await waitFor(() => expect(mocks.executeAgent).toHaveBeenCalledTimes(1));
    const callbacks = mocks.executeAgent.mock.calls[0][1];

    await act(async () => {
      callbacks.onClarify({
        reason: "Need details",
        questions: [{ id: "q1", question: "What's your goal?" }],
      });
    });

    // Ensure the question is still there before onDone fires
    expect(screen.getByText("What's your goal?")).toBeTruthy();

    // A later done from this stream must be a no-op due to ownership guard.
    await act(async () => {
      callbacks.onDone?.("");
    });

    // The question should still be rendered (clarify content preserved, not overwritten).
    expect(screen.getByText("What's your goal?")).toBeTruthy();
    // Lock remains released (no Stop button appears again).
    expect(screen.queryByLabelText("Stop generation")).toBeFalsy();
  });
});
