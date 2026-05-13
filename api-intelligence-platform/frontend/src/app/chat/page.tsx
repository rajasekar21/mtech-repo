"use client";

import { useEffect, useRef, useState } from "react";
import {
  Bot,
  MessageSquare,
  Plus,
  RefreshCw,
  Send,
  Sparkles,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { post, get } from "@/lib/api";
import { cn, formatRelative } from "@/lib/utils";
import Sidebar from "@/components/shared/Sidebar";
import Header from "@/components/shared/Header";
import ChatBubble from "@/components/chat/ChatBubble";
import SpecSelector from "@/components/shared/SpecSelector";
import { useCatalogStore } from "@/store/catalog";
import { useUIStore } from "@/store/ui";
import type {
  ChatMessage,
  ChatConversation,
  ChatResponse,
  ChatRequest,
} from "@/types";

const SUGGESTED_QUERIES = [
  "Explain the direct pay flow end-to-end",
  "What breaks if ReqAuthDetails schema changes?",
  "List all deprecated endpoints in this spec",
  "What authentication methods are used?",
  "Show me high-risk endpoints and why",
  "How does the bank settlement process work?",
];

function generateId(): string {
  return Math.random().toString(36).substring(2, 9);
}

export default function ChatPage() {
  const { specs, fetchSpecs } = useCatalogStore();
  const { activeSpecId } = useUIStore();

  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<
    string | null
  >(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [contextSpecId, setContextSpecId] = useState<string | null>(
    activeSpecId
  );
  const [isSending, setIsSending] = useState(false);
  const [isLoadingConvos, setIsLoadingConvos] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    fetchSpecs();
    loadConversations();
  }, [fetchSpecs]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const loadConversations = async () => {
    setIsLoadingConvos(true);
    try {
      const convos = await get<ChatConversation[]>("/api/chat/conversations");
      setConversations(convos);
    } catch {
      // Use demo conversations
      setConversations([
        {
          id: "convo-1",
          title: "Direct Pay Flow Analysis",
          spec_id: activeSpecId ?? undefined,
          message_count: 6,
          last_message: "The direct pay flow involves...",
          created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
          updated_at: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(),
        },
        {
          id: "convo-2",
          title: "ReqAuthDetails Impact",
          spec_id: activeSpecId ?? undefined,
          message_count: 4,
          last_message: "Changing ReqAuthDetails would affect...",
          created_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
          updated_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
        },
      ]);
    } finally {
      setIsLoadingConvos(false);
    }
  };

  const loadMessages = async (conversationId: string) => {
    try {
      const msgs = await get<ChatMessage[]>(
        `/api/chat/conversations/${conversationId}/messages`
      );
      setMessages(msgs);
    } catch {
      setMessages([]);
    }
  };

  const handleSelectConversation = (convo: ChatConversation) => {
    setActiveConversationId(convo.id);
    loadMessages(convo.id);
    if (convo.spec_id) setContextSpecId(convo.spec_id);
  };

  const handleNewConversation = () => {
    setActiveConversationId(null);
    setMessages([]);
  };

  const handleSend = async (messageText?: string) => {
    const text = messageText ?? input.trim();
    if (!text || isSending) return;

    const userMessage: ChatMessage = {
      id: generateId(),
      conversation_id: activeConversationId ?? "",
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsSending(true);

    const thinkingMessage: ChatMessage = {
      id: generateId() + "-thinking",
      conversation_id: activeConversationId ?? "",
      role: "assistant",
      content: "...",
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, thinkingMessage]);

    try {
      const request: ChatRequest = {
        message: text,
        conversation_id: activeConversationId ?? undefined,
        spec_id: contextSpecId ?? undefined,
      };

      const response = await post<ChatResponse>("/api/chat", request);
      const aiMessage: ChatMessage = {
        ...response.message,
        sources: response.sources,
      };

      setMessages((prev) =>
        prev
          .filter((m) => m.id !== thinkingMessage.id)
          .concat(aiMessage)
      );

      if (!activeConversationId) {
        setActiveConversationId(response.conversation_id);
        const newConvo: ChatConversation = {
          id: response.conversation_id,
          title: text.length > 40 ? text.slice(0, 40) + "..." : text,
          spec_id: contextSpecId ?? undefined,
          message_count: 2,
          last_message: response.message.content.slice(0, 80),
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        setConversations((prev) => [newConvo, ...prev]);
      }
    } catch {
      // Simulate AI response for demo
      const demoResponses: Record<string, string> = {
        default: `I can help you understand your APIs. Based on the specification context, here's what I found:

The API follows REST conventions with standard HTTP methods. Key observations:

1. **Authentication**: The spec uses OAuth2 with JWT tokens for secure endpoint access
2. **Endpoints**: There are ${Math.floor(Math.random() * 20) + 10} endpoints across various resource groups
3. **Risk Profile**: Several endpoints handle sensitive financial data and require elevated security

For more specific analysis, please ensure a spec is selected in the context panel.`,
      };

      const aiContent =
        text.toLowerCase().includes("direct pay") ||
        text.toLowerCase().includes("flow")
          ? `The **Direct Pay Flow** is the core payment processing sequence in this API:

\`\`\`
Merchant → API Gateway → Payment Gateway → PSP → Bank
\`\`\`

**Key Steps:**
1. Merchant submits payment request with card details
2. API Gateway validates JWT authentication token
3. Payment Gateway calls \`ReqAuthDetails\` to verify transaction
4. PSP processes the charge against the card network
5. Bank settles the funds transfer
6. Response propagates back to the merchant

**Critical Endpoints:**
- \`POST /v1/payments\` — Initiates the payment
- \`POST /auth/validate\` — JWT validation
- \`GET /v1/transactions/{id}\` — Status polling

The flow typically completes in 2-5 seconds for standard transactions.`
          : demoResponses.default;

      const demoMessage: ChatMessage = {
        id: generateId(),
        conversation_id: activeConversationId ?? "demo",
        role: "assistant",
        content: aiContent,
        sources: [],
        created_at: new Date().toISOString(),
      };

      setMessages((prev) =>
        prev.filter((m) => m.id !== thinkingMessage.id).concat(demoMessage)
      );

      if (!activeConversationId) {
        const newId = generateId();
        setActiveConversationId(newId);
        const newConvo: ChatConversation = {
          id: newId,
          title: text.length > 40 ? text.slice(0, 40) + "..." : text,
          spec_id: contextSpecId ?? undefined,
          message_count: 2,
          last_message: aiContent.slice(0, 80),
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        setConversations((prev) => [newConvo, ...prev]);
      }
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleDeleteConversation = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (activeConversationId === id) {
      setActiveConversationId(null);
      setMessages([]);
    }
    toast.success("Conversation deleted");
  };

  return (
    <div className="flex h-screen bg-[#080d1a] overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header title="AI Chat Workspace" />
        <div className="flex-1 flex overflow-hidden">
          {/* Conversations List */}
          <div className="w-64 border-r border-slate-800 bg-slate-900/50 flex flex-col">
            <div className="p-3 border-b border-slate-800">
              <button
                onClick={handleNewConversation}
                className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-sm bg-indigo-600 hover:bg-indigo-500 text-white transition-colors"
              >
                <Plus className="w-4 h-4" />
                New Conversation
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-2 space-y-1">
              {isLoadingConvos ? (
                <div className="flex items-center justify-center py-8">
                  <RefreshCw className="w-5 h-5 text-slate-600 animate-spin" />
                </div>
              ) : conversations.length === 0 ? (
                <div className="text-center py-8 px-4">
                  <MessageSquare className="w-8 h-8 text-slate-700 mx-auto mb-2" />
                  <p className="text-xs text-slate-500">No conversations yet</p>
                </div>
              ) : (
                conversations.map((convo) => (
                  <div
                    key={convo.id}
                    onClick={() => handleSelectConversation(convo)}
                    className={cn(
                      "group flex items-start justify-between gap-2 p-2.5 rounded-lg cursor-pointer transition-colors",
                      activeConversationId === convo.id
                        ? "bg-indigo-600/15 border border-indigo-500/20"
                        : "hover:bg-slate-800/60"
                    )}
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-medium text-slate-300 truncate">
                        {convo.title}
                      </p>
                      {convo.last_message && (
                        <p className="text-xs text-slate-600 truncate mt-0.5">
                          {convo.last_message}
                        </p>
                      )}
                      <p className="text-xs text-slate-700 mt-0.5">
                        {formatRelative(convo.updated_at)}
                      </p>
                    </div>
                    <button
                      onClick={(e) => handleDeleteConversation(convo.id, e)}
                      className="opacity-0 group-hover:opacity-100 p-0.5 text-slate-600 hover:text-red-400 transition-all"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Chat Area */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Context Bar */}
            <div className="flex items-center gap-3 px-4 py-2.5 border-b border-slate-800 bg-slate-900/20">
              <Sparkles className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" />
              <span className="text-xs text-slate-500">Context:</span>
              <div className="w-48">
                <SpecSelector
                  specs={specs}
                  value={contextSpecId}
                  onChange={setContextSpecId}
                  placeholder="All specs"
                  compact
                />
              </div>
              {contextSpecId && (
                <span className="text-xs text-indigo-400">
                  AI has context of selected spec
                </span>
              )}
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-center">
                  <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mb-4">
                    <Bot className="w-8 h-8 text-indigo-400" />
                  </div>
                  <h2 className="text-xl font-semibold text-slate-300 mb-2">
                    API Intelligence AI
                  </h2>
                  <p className="text-slate-500 text-sm max-w-md mb-8">
                    Ask me anything about your APIs — flows, dependencies,
                    security, governance, or impact analysis.
                  </p>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-2xl">
                    {SUGGESTED_QUERIES.map((query) => (
                      <button
                        key={query}
                        onClick={() => handleSend(query)}
                        className="text-left p-3 rounded-xl bg-slate-800/60 border border-slate-700/50 hover:border-indigo-500/30 hover:bg-slate-800 transition-colors group"
                      >
                        <p className="text-sm text-slate-400 group-hover:text-slate-300 transition-colors">
                          {query}
                        </p>
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <>
                  {messages.map((msg) => (
                    <ChatBubble key={msg.id} message={msg} />
                  ))}
                  <div ref={messagesEndRef} />
                </>
              )}
            </div>

            {/* Input Area */}
            <div className="p-4 border-t border-slate-800">
              <div className="relative bg-slate-800 border border-slate-700 rounded-xl focus-within:border-indigo-500/50 focus-within:ring-1 focus-within:ring-indigo-500/20 transition-all">
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask about your APIs... (Enter to send, Shift+Enter for new line)"
                  rows={3}
                  disabled={isSending}
                  className="w-full px-4 pt-3 pb-10 bg-transparent text-sm text-slate-200 placeholder-slate-500 resize-none focus:outline-none"
                />
                <div className="absolute bottom-2 right-2 flex items-center gap-2">
                  <span className="text-xs text-slate-600">
                    {input.length > 0 && `${input.length} chars`}
                  </span>
                  <button
                    onClick={() => handleSend()}
                    disabled={!input.trim() || isSending}
                    className={cn(
                      "p-2 rounded-lg transition-all",
                      input.trim() && !isSending
                        ? "bg-indigo-600 hover:bg-indigo-500 text-white"
                        : "bg-slate-700 text-slate-500 cursor-not-allowed"
                    )}
                  >
                    {isSending ? (
                      <RefreshCw className="w-4 h-4 animate-spin" />
                    ) : (
                      <Send className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>
              <p className="text-xs text-slate-600 mt-2 text-center">
                AI responses are based on your uploaded API specifications and may not reflect real-time data.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
