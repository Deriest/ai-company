import { useCallback, useEffect, useRef, useState } from "react";
import { api, configureClient, streamMessage } from "../lib/runtimeClient";
import { friendlyError } from "../lib/errors";
import type { Msg, View } from "../types";

/**
 * Extract the conversational response text from any API response shape.
 * Returns an empty string if no usable text is found.
 */
function extractResponseText(res: unknown): string {
  if (typeof res === "string") return res;
  if (!res || typeof res !== "object") return "";
  const obj = res as Record<string, unknown>;
  for (const key of ["response", "content", "text", "message"] as const) {
    const v = obj[key];
    if (typeof v === "string" && v.trim()) return v;
  }
  if (obj.data && typeof obj.data === "object") {
    const nested = obj.data as Record<string, unknown>;
    for (const key of ["response", "content", "text", "message"] as const) {
      const v = nested[key];
      if (typeof v === "string" && v.trim()) return v;
    }
  }
  return "";
}

export interface UseChatOptions {
  token: string | null;
  engineUrl: string;
  view: View;
  log: (line: string) => void;
  refreshAll: () => Promise<void>;
}

export interface ChatState {
  conversationId: string | null;
  setConversationId: React.Dispatch<React.SetStateAction<string | null>>;
  conversationList: Array<{ id: string; title: string; updated_at: string }>;
  convSearch: string;
  setConvSearch: React.Dispatch<React.SetStateAction<string>>;
  messages: Msg[];
  setMessages: React.Dispatch<React.SetStateAction<Msg[]>>;
  draft: string;
  setDraft: React.Dispatch<React.SetStateAction<string>>;
  sending: boolean;
  logRef: React.RefObject<HTMLDivElement | null>;
  loadConversations: () => Promise<void>;
  switchConversation: (id: string) => Promise<void>;
  deleteConv: (id: string, e: React.MouseEvent) => Promise<void>;
  sendChat: () => Promise<void>;
}

export function useChat(opts: UseChatOptions): ChatState {
  const { token, engineUrl, view, log, refreshAll } = opts;

  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversationList, setConversationList] = useState<Array<{ id: string; title: string; updated_at: string }>>([]);
  const [convSearch, setConvSearch] = useState("");
  const [messages, setMessages] = useState<Msg[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  const loadConversations = useCallback(async () => {
    if (!token) return;
    try {
      const convs = await api.conversations();
      if (Array.isArray(convs)) {
        setConversationList(
          convs
            .map((c: unknown) => {
              const o = c as Record<string, unknown>;
              return { id: String(o.id || ""), title: String(o.title || "Untitled"), updated_at: String(o.updated_at || o.created_at || new Date().toISOString()) };
            })
            .slice(0, 50)
        );
      }
    } catch {
      /* ignore */
    }
  }, [token]);

  useEffect(() => {
    if ((view === "chat" || view === "overview") && token) void loadConversations();
  }, [view, token, loadConversations]);

  const switchConversation = useCallback(async (id: string) => {
    setConversationId(id);
    void window.aic?.storeSet("conversationId", id);
    try {
      const msgs = await api.messages(id);
      if (Array.isArray(msgs)) {
        const loaded: Msg[] = (msgs as Array<Record<string, unknown>>)
          .map((o) => ({
            role: (String(o.role || o.sender || "") === "user" ? "user" : "assistant") as "user" | "assistant",
            content: extractResponseText(o),
          }))
          .filter((m) => m.content);
        setMessages(loaded);
      }
    } catch {
      /* ignore */
    }
  }, []);

  const deleteConv = useCallback(
    async (id: string, e: React.MouseEvent) => {
      e.stopPropagation();
      try {
        await api.deleteConversation(id);
        setConversationList((prev) => prev.filter((c) => c.id !== id));
        if (conversationId === id) {
          setConversationId(null);
          setMessages([]);
          void window.aic?.storeSet("conversationId", null);
        }
      } catch {
        /* ignore */
      }
    },
    [conversationId]
  );

  const ensureConversation = async (prompt?: string) => {
    if (conversationId) return conversationId;
    const initialTitle = prompt ? prompt.slice(0, 50).trim() || "New Conversation" : "New Conversation";
    const c = await api.createConversation(initialTitle);
    setConversationId(c.id);
    void window.aic?.storeSet("conversationId", c.id);
    void loadConversations();
    return c.id;
  };

  const sendChat = async () => {
    const text = draft.trim();
    if (!text || sending) return;
    setSending(true);
    setMessages((m) => [...m, { role: "user", content: text }, { role: "assistant", content: "" }]);
    setDraft("");
    try {
      const isFirst = !conversationId || messages.length === 0;
      const id = await ensureConversation(text);

      // Auto-title update on first prompt
      if (isFirst && text) {
        const derivedTitle = text.slice(0, 50).trim();
        if (derivedTitle) {
          api
            .updateConversation(id, { title: derivedTitle })
            .then(() => loadConversations())
            .catch(() => {});
        }
      }

      let acc = "";
      try {
        await streamMessage(id, text, (chunk) => {
          acc += chunk;
          setMessages((m) => {
            const copy = [...m];
            copy[copy.length - 1] = { role: "assistant", content: acc };
            return copy;
          });
        });
        if (!acc) {
          const res = await api.sendMessage(id, text);
          const content = extractResponseText(res);
          setMessages((m) => {
            const copy = [...m];
            copy[copy.length - 1] = { role: "assistant", content };
            return copy;
          });
        }
      } catch {
        const res = await api.sendMessage(id, text);
        const content = extractResponseText(res);
        setMessages((m) => {
          const copy = [...m];
          copy[copy.length - 1] = { role: "assistant", content };
          return copy;
        });
      }
      log("message sent to Hermes");
      void refreshAll();
      void loadConversations();
    } catch (e) {
      const fe = friendlyError(e);
      const errorMsg = fe.title
        ? `${fe.title}: ${fe.message}`
        : e instanceof Error
          ? e.message
          : "Request failed";
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = { role: "assistant", content: `⚠ ${errorMsg}` };
        return copy;
      });
    } finally {
      setSending(false);
    }
  };

  // Auto-scroll messages
  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [messages]);

  return {
    conversationId,
    setConversationId,
    conversationList,
    convSearch,
    setConvSearch,
    messages,
    setMessages,
    draft,
    setDraft,
    sending,
    logRef,
    loadConversations,
    switchConversation,
    deleteConv,
    sendChat,
  };
}
