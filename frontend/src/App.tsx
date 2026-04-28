import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Role = "user" | "assistant";

interface Message {
  role: Role;
  content: string;
}

const REFUSAL = "This question is outside the scope of the provided PDF.";

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [pdfName, setPdfName] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setIsUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch("/api/upload-pdf", { method: "POST", body: fd });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(`Upload failed: ${detail}`);
      }
      const data: { session_id: string; pdf_name: string } = await res.json();
      setSessionId(data.session_id);
      setPdfName(data.pdf_name);
      setMessages([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleReset() {
    if (!sessionId) return;
    setError(null);
    try {
      const res = await fetch("/api/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId }),
      });
      if (!res.ok) throw new Error(await res.text());
      setMessages([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleSend(e?: FormEvent) {
    e?.preventDefault();
    const text = input.trim();
    if (!text || !sessionId || isStreaming) return;

    setError(null);
    setInput("");
    setMessages((m) => [
      ...m,
      { role: "user", content: text },
      { role: "assistant", content: "" },
    ]);
    setIsStreaming(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: text }),
      });
      if (!res.ok || !res.body) {
        const detail = await res.text().catch(() => res.statusText);
        throw new Error(detail || "Chat request failed");
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        setMessages((m) => {
          const next = [...m];
          const last = next[next.length - 1];
          if (last && last.role === "assistant") {
            next[next.length - 1] = { ...last, content: last.content + chunk };
          }
          return next;
        });
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      setMessages((m) => {
        const next = [...m];
        const last = next[next.length - 1];
        if (last && last.role === "assistant" && last.content === "") {
          next[next.length - 1] = { ...last, content: `_Error: ${msg}_` };
        }
        return next;
      });
    } finally {
      setIsStreaming(false);
    }
  }

  function handleKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="flex h-screen w-screen bg-slate-50 text-slate-900">
      <Sidebar
        pdfName={pdfName}
        isUploading={isUploading}
        onUpload={handleUpload}
        onReset={handleReset}
        canReset={sessionId !== null && messages.length > 0 && !isStreaming}
        fileInputRef={fileInputRef}
      />

      <main className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
          <div>
            <h1 className="text-base font-semibold">PDF Chatbot</h1>
            <p className="text-xs text-slate-500">
              {pdfName ? `Chatting with ${pdfName}` : "Upload a PDF to begin"}
            </p>
          </div>
          {isStreaming && (
            <span className="flex items-center gap-2 text-xs text-slate-500">
              <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-emerald-500" />
              Generating…
            </span>
          )}
        </header>

        <div className="flex-1 overflow-y-auto px-6 py-6">
          {messages.length === 0 ? (
            <EmptyState hasPdf={!!sessionId} />
          ) : (
            <div className="mx-auto flex max-w-3xl flex-col gap-4">
              {messages.map((msg, i) => (
                <Bubble key={i} message={msg} />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {error && (
          <div className="border-t border-red-200 bg-red-50 px-6 py-2 text-xs text-red-700">
            {error}
          </div>
        )}

        <form
          onSubmit={handleSend}
          className="border-t border-slate-200 bg-white px-6 py-4"
        >
          <div className="mx-auto flex max-w-3xl items-end gap-3">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder={
                sessionId
                  ? "Ask about the PDF…  (Enter to send, Shift+Enter for newline)"
                  : "Upload a PDF first to start chatting"
              }
              disabled={!sessionId || isStreaming}
              rows={1}
              className="min-h-[44px] max-h-40 flex-1 resize-none rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-slate-500 focus:outline-none disabled:bg-slate-100"
            />
            <button
              type="submit"
              disabled={!sessionId || isStreaming || !input.trim()}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:bg-slate-300"
            >
              Send
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}

interface SidebarProps {
  pdfName: string | null;
  isUploading: boolean;
  onUpload: (e: ChangeEvent<HTMLInputElement>) => void;
  onReset: () => void;
  canReset: boolean;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
}

function Sidebar({
  pdfName,
  isUploading,
  onUpload,
  onReset,
  canReset,
  fileInputRef,
}: SidebarProps) {
  return (
    <aside className="flex w-72 flex-col border-r border-slate-200 bg-white">
      <div className="border-b border-slate-200 px-5 py-4">
        <div className="flex items-center gap-2">
          <span className="text-xl">📄</span>
          <span className="text-sm font-semibold">PDF Chatbot</span>
        </div>
        <p className="mt-1 text-xs text-slate-500">
          Strictly grounded answers with page citations.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
          Document
        </h2>

        <input
          ref={fileInputRef}
          type="file"
          accept="application/pdf"
          onChange={onUpload}
          className="hidden"
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading}
          className="w-full rounded-md border border-dashed border-slate-300 px-3 py-4 text-sm text-slate-600 transition hover:border-slate-500 hover:bg-slate-50 disabled:opacity-50"
        >
          {isUploading
            ? "Uploading…"
            : pdfName
              ? "Replace PDF"
              : "Upload a PDF"}
        </button>

        {pdfName && (
          <div className="mt-3 truncate rounded-md bg-slate-100 px-3 py-2 text-xs text-slate-700">
            <span className="font-medium">Active:</span> {pdfName}
          </div>
        )}

        <button
          type="button"
          onClick={onReset}
          disabled={!canReset}
          className="mt-3 w-full rounded-md border border-slate-300 px-3 py-1.5 text-xs text-slate-700 transition hover:bg-slate-100 disabled:opacity-40"
        >
          Reset conversation
        </button>

        <div className="mt-6 rounded-md bg-amber-50 p-3 text-xs text-amber-900">
          <div className="mb-1 font-semibold">Behavior</div>
          <ul className="list-disc space-y-1 pl-4">
            <li>Answers only from the PDF</li>
            <li>Inline page citations</li>
            <li>
              Refuses out-of-scope with:{" "}
              <em className="font-medium">{REFUSAL}</em>
            </li>
          </ul>
        </div>
      </div>

      <div className="border-t border-slate-200 px-5 py-3 text-[11px] text-slate-400">
        Powered by Gemini · FastAPI · React
      </div>
    </aside>
  );
}

function Bubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={
          isUser
            ? "max-w-[80%] rounded-2xl rounded-br-sm bg-slate-900 px-4 py-2.5 text-sm text-white whitespace-pre-wrap"
            : "max-w-[85%] rounded-2xl rounded-bl-sm border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 markdown-body"
        }
      >
        {isUser ? (
          message.content
        ) : message.content === "" ? (
          <span className="inline-flex gap-1 py-1">
            <Dot />
            <Dot delay="150ms" />
            <Dot delay="300ms" />
          </span>
        ) : (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.content}
          </ReactMarkdown>
        )}
      </div>
    </div>
  );
}

function Dot({ delay = "0ms" }: { delay?: string }) {
  return (
    <span
      className="inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400"
      style={{ animationDelay: delay }}
    />
  );
}

function EmptyState({ hasPdf }: { hasPdf: boolean }) {
  return (
    <div className="mx-auto mt-12 max-w-md text-center text-slate-500">
      <div className="mb-4 text-5xl">📄</div>
      <h2 className="mb-2 text-lg font-medium text-slate-700">
        {hasPdf ? "Ask anything about your PDF" : "Upload a PDF to get started"}
      </h2>
      <p className="text-sm">
        {hasPdf
          ? "Answers will be grounded in the document, with inline page citations. Out-of-scope questions get refused."
          : "Use the sidebar to upload a PDF. The bot will only answer using its contents and will cite pages."}
      </p>
    </div>
  );
}
