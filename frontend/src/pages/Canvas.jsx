import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from 'chart.js';
import { marked } from 'marked';
import { useParams, useNavigate } from 'react-router-dom';
import ChatInput from '../components/chat/ChatInput';
import MessageList from '../components/chat/MessageList';
import ChatHero from '../components/chat/ChatHero';
import { useChatContext } from '../context/ChatContext';
import { useChatCanvas } from '../helpers/chat/useChatCanvas';

ChartJS.register(
  ArcElement,
  BarElement,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
);

// Avatar now moved into components/chat/Avatar.jsx

// Configure marked once
marked.setOptions({
  gfm: true,
  breaks: true,
  mangle: true,
  headerIds: true,
});

import { extractChartSpec } from '../utils/markdown';

export default function Canvas() {
  const {
    activeChatId,
    setActiveChatHasMessages,
    setActiveChatId,
    refreshChats,
  } = useChatContext();
  const { chatId } = useParams();
  const navigate = useNavigate();
  const {
    messages,
    hasInteracted,
    input,
    setInput,
    loading,
    error,
    send,
    getExportForId,
    transformAssistantContent,
    sanitizeRender,
    endRef,
  } = useChatCanvas({
    activeChatId,
    setActiveChatHasMessages,
    setActiveChatId,
    refreshChats,
    navigate,
    chatIdParam: chatId,
  });

  return (
    <div className="flex flex-col h-screen bg-zinc-800 text-slate-50">
      <div className="flex-1 overflow-y-auto px-3 sm:px-6 py-4">
        <div className="mx-auto w-full max-w-6xl space-y-6 pt-4">
          {!hasInteracted && !messages.length && !loading && (
            <ChatHero onSubmit={send} disabled={loading} />
          )}
          {(hasInteracted || messages.length > 0) && (
            <MessageList
              messages={messages.map((m, idx) => ({ ...m, id: idx }))}
              getExportForId={getExportForId}
              extractChartSpec={(c) => extractChartSpec(c || '')}
              sanitizeRender={sanitizeRender}
              transformAssistantContent={transformAssistantContent}
            />
          )}
          {loading && (
            <div className="flex w-full">
              <div className="bg-zinc-800/70 rounded-xl px-4 py-4 border border-zinc-700/70 text-sm flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-zinc-400 animate-pulse" />
                <div className="w-2 h-2 rounded-full bg-zinc-400 animate-pulse [animation-delay:0.15s]" />
                <div className="w-2 h-2 rounded-full bg-zinc-400 animate-pulse [animation-delay:0.3s]" />
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>
      </div>
      {error && (
        <p className="text-red-400 text-center text-xs sm:text-sm mb-2 px-4">
          {error}
        </p>
      )}
      {(hasInteracted || messages.length > 0) && (
        <ChatInput
          value={input}
          onChange={setInput}
          onSubmit={send}
          disabled={loading}
        />
      )}
    </div>
  );
}
