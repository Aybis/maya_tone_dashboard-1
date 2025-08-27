import React from 'react';
import Avatar from './Avatar';
import MessageBubble from './MessageBubble';
import DateSeparator from './DateSeparator';
import ExportDownload from './ExportDownload';
import ChartRenderer from './ChartRenderer';

export default function MessageList({
  messages,
  getExportForId,
  extractChartSpec,
  sanitizeRender,
  transformAssistantContent,
}) {
  function isDifferentDay(date1, date2) {
    if (!date1 || !date2) return false;
    const d1 = new Date(date1);
    const d2 = new Date(date2);
    return (
      d1.getFullYear() !== d2.getFullYear() ||
      d1.getMonth() !== d2.getMonth() ||
      d1.getDate() !== d2.getDate()
    );
  }

  return (
    <div className="flex flex-col gap-6 w-full">
      {messages.map((msg, idx) => {
        const isUser = msg.sender === 'user';
        const chartSpec = extractChartSpec(msg.content);
        const exportData = getExportForId(msg.id);
        const prevMsg = idx > 0 ? messages[idx - 1] : null;
        const showDateSeparator =
          idx === 0 || isDifferentDay(msg.timestamp, prevMsg?.timestamp);
        const isLast = idx === messages.length - 1;
        return (
          <React.Fragment key={msg.id}>
            {showDateSeparator && <DateSeparator date={msg.timestamp} />}
            <div
              className={`flex items-start w-full gap-4 ${
                isUser ? 'justify-end' : ''
              }`}
            >
              <div
                className={`flex flex-col gap-2 max-w-full ${
                  isUser ? 'items-end' : 'w-full'
                }`}
              >
                <MessageBubble
                  message={msg}
                  isUser={isUser}
                  sanitizeRender={sanitizeRender}
                  transformAssistantContent={transformAssistantContent}
                  showTimeOnly={isLast}
                />
                {chartSpec && <ChartRenderer spec={chartSpec} />}
                {!isUser && exportData && (
                  <ExportDownload exportData={exportData} />
                )}
              </div>
            </div>
          </React.Fragment>
        );
      })}
    </div>
  );
}
