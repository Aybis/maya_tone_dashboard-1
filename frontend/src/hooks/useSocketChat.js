import { useState, useEffect, useRef, useCallback } from "react";
import { io } from "socket.io-client";

/**
 * Manages socket connection + initial fetch + streaming updates + sending user messages.
 */
export function useSocketChat({
  activeChatId,
  chats,
  finalizeTempChat,
  activeProvider,
  setActiveChatHasMessages,
}) {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const socketRef = useRef(null);

  // Initialise socket + streaming listeners
  useEffect(() => {
    socketRef.current = io("http://localhost:4000");
    const sock = socketRef.current;
    const safeChat = () => activeChatId;

    sock.on("assistant_start", ({ chat_id }) => {
      if (chat_id === safeChat()) {
        setIsLoading(true);
        setMessages((prev) => [...prev, { sender: "assistant", content: "" }]);
      }
    });
    sock.on("assistant_delta", ({ chat_id, delta }) => {
      if (chat_id === safeChat()) {
        setMessages((prev) => {
          const copy = [...prev];
          for (let i = copy.length - 1; i >= 0; i--) {
            if (copy[i].sender === "assistant") {
              copy[i] = {
                ...copy[i],
                content: (copy[i].content || "") + delta,
              };
              break;
            }
          }
          return copy;
        });
      }
    });
    sock.on("assistant_end", ({ chat_id, content }) => {
      if (chat_id === safeChat()) {
        setMessages((prev) => {
          const copy = [...prev];
          for (let i = copy.length - 1; i >= 0; i--) {
            if (copy[i].sender === "assistant") {
              copy[i] = { ...copy[i], content };
              break;
            }
          }
          return copy;
        });
        setIsLoading(false);
      }
    });
    sock.on("assistant_error", ({ chat_id, error }) => {
      if (chat_id === safeChat()) {
        setError(error);
        setIsLoading(false);
      }
    });
    sock.on("new_message", (data) => {
      if (data.chat_id === safeChat()) {
        setMessages((prev) => [
          ...prev,
          { sender: data.sender, content: data.content },
        ]);
        setIsLoading(false);
      }
    });
    return () => {
      sock.disconnect();
    };
  }, [activeChatId]);

  // Fetch existing messages when chat changes
  useEffect(() => {
    if (!activeChatId) return;
    let cancelled = false;
    (async () => {
      setIsLoading(true);
      setError("");
      try {
        const res = await fetch(`/api/chat/${activeChatId}`);
        if (!res.ok) throw new Error("Failed");
        const data = await res.json();
        if (!cancelled) {
          setMessages(data);
          socketRef.current?.emit("join_chat", { chat_id: activeChatId });
        }
      } catch (e) {
        if (!cancelled) setError("Failed to fetch messages.");
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeChatId]);

  const sendUserMessage = useCallback(
    async ({ content }) => {
      if (!content.trim() || !activeChatId || isLoading) return false;
      const userMessage = { sender: "user", content };
      setMessages((prev) => [...prev, userMessage]);
      const chatMeta = chats.find((c) => c.id === activeChatId);
      let realChatId = activeChatId;
      try {
        setIsLoading(true);
        setError("");
        if (chatMeta && chatMeta._temp) {
          realChatId = await finalizeTempChat(activeChatId, activeProvider);
        }
        await fetch(`/api/chat/${realChatId}/ask_stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: content }),
        });
        setActiveChatHasMessages(true);
        return true;
      } catch (e) {
        setError(`Failed to send message: ${e.message}`);
        setMessages((prev) => prev.filter((m) => m !== userMessage));
        return false;
      } finally {
        setIsLoading(false);
      }
    },
    [
      activeChatId,
      chats,
      finalizeTempChat,
      activeProvider,
      isLoading,
      setActiveChatHasMessages,
    ],
  );

  return { messages, setMessages, isLoading, error, sendUserMessage };
}
