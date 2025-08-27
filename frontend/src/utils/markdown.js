import { marked } from 'marked';

// Configure marked globally if not already
marked.setOptions({
  gfm: true,
  breaks: false,
  mangle: false,
  headerIds: false,
});

/**
 * Split ticket markdown into individual cards and wrap each one.
 * Falls back to normal markdown if only one ticket.
 */
export const renderCardMarkdown = (raw) => {
  try {
    const text = raw || '';
    if (!text.trim()) return '';

    const ticketHeader = /^\s*(?:#{1,6}\s*)?📋\s*Ticket:/;
    const aiNotesHeader = /^\s*(?:#{1,6}\s*)?🧠\s*AI Notes/i;

    const lines = text.split(/\n/);
    const segments = []; // {type:'ticket'|'ai', content:string}
    let current = null; // {type, lines:[]}

    const pushCurrent = () => {
      if (current && current.lines.length) {
        segments.push({
          type: current.type,
          content: current.lines.join('\n'),
        });
      }
      current = null;
    };

    for (const rawLine of lines) {
      const line = rawLine; // keep original spacing except leading trim for headers
      if (ticketHeader.test(line)) {
        pushCurrent();
        current = { type: 'ticket', lines: [line.trimStart()] };
      } else if (aiNotesHeader.test(line)) {
        pushCurrent();
        current = { type: 'ai', lines: [line.trimStart()] };
      } else if (current) {
        current.lines.push(line);
      } else {
        // Content before first ticket or AI header -> treat as plain (ai meta)
        current = { type: 'ai', lines: [line] };
      }
    }
    pushCurrent();

    if (!segments.length) return marked.parse(text);

    // If only one segment just return plain markdown (no card wrapping)
    if (segments.length === 1) {
      return marked.parse(segments[0].content);
    }

    return segments
      .map((seg, idx) => {
        if (seg.type === 'ticket') {
          return `<article class="md-card border text-sm border-zinc-700/60 bg-zinc-700/40 rounded-lg p-4 shadow-lg">${marked.parse(
            seg.content,
          )}</article>`;
        }
        const hasTicket = segments.some((s) => s.type === 'ticket');
        const isOpener = idx === 0 && hasTicket;
        if (isOpener) {
          // opener sits above first card without card styling
          return `<div class="md-opener mb-3 text-zinc-300">${marked.parse(
            seg.content,
          )}</div>`;
        }
        // trailing AI notes: inline subtle separator not a second full card

        // Post-process: extract trailing generic closing notes from ticket segments
        const closingNoteRegex =
          /^(?:if you need|let me know|feel free|reach out|butuh.*lagi)/i;
        const processed = [];
        segments.forEach((seg) => {
          if (seg.type !== 'ticket') {
            processed.push(seg);
            return;
          }
          const lines = seg.content.split(/\n/);
          // walk backwards skipping blank lines
          let idx = lines.length - 1;
          while (idx >= 0 && !lines[idx].trim()) idx--;
          let noteStart = -1;
          for (let i = idx; i >= 0; i--) {
            const line = lines[i].trim();
            if (!line) continue;
            if (closingNoteRegex.test(line)) {
              noteStart = i;
              // allow multi-line small note (previous line if continues sentence)
              while (
                noteStart > 0 &&
                lines[noteStart - 1].trim() &&
                /[,.]$/.test(lines[noteStart - 1].trim()) === false &&
                lines[noteStart - 1].length < 90
              ) {
                // merge potential preceding line fragment (rare)
                noteStart--;
              }
            }
            // Stop scanning once we hit a metadata line typical to tickets
            if (/Updated:|Reporter:|Created:|Summary:|Assignee:/.test(line))
              break;
          }
          if (noteStart >= 0) {
            const ticketPart = lines.slice(0, noteStart).join('\n').trimEnd();
            const notePart = lines.slice(noteStart).join('\n').trim();
            if (ticketPart) {
              processed.push({ type: 'ticket', content: ticketPart });
            }
            if (notePart) {
              processed.push({ type: 'ai', content: notePart });
            }
          } else {
            processed.push(seg);
          }
        });

        // Replace with processed segments
        segments.splice(0, segments.length, ...processed);
        return `<div class="md-ai-notes mt-4 pt-3 border-t border-zinc-700/40 text-zinc-400 text-sm leading-relaxed">${marked.parse(
          seg.content,
        )}</div>`;
      })
      .join('');
  } catch (e) {
    return raw;
  }
};

/** Extract first chart spec JSON inside ```chart ... ``` block */
export const extractChartSpec = (content) => {
  const match = content?.match(/```chart\s*\n([\s\S]*?)```/i);
  if (!match) return null;
  try {
    return JSON.parse(match[1]);
  } catch (e) {
    return null;
  }
};

/** Extract export data payload inside [EXPORT_DATA]...[/EXPORT_DATA] */
export const extractExportData = (raw) => {
  if (!raw) return { cleaned: raw, downloadData: null };
  const match = raw.match(/\[EXPORT_DATA\]([\s\S]*?)\[\/EXPORT_DATA\]/i);
  if (!match) return { cleaned: raw, downloadData: null };
  let inner = match[1].trim();
  inner = inner.replace(/```[a-zA-Z]*\n([\s\S]*?)```/g, '$1').trim();
  let downloadData = null;
  try {
    downloadData = JSON.parse(inner);
  } catch (e) {
    const link = inner.match(/"download_link"\s*:\s*"([^"]+)"/);
    const filename = inner.match(/"filename"\s*:\s*"([^"]+)"/);
    if (link) {
      downloadData = {
        download_link: link[1],
        filename: filename ? filename[1] : 'export.pdf',
      };
    }
  }
  const cleaned = raw
    .replace(/\[EXPORT_DATA\][\s\S]*?\[\/EXPORT_DATA\]/i, '')
    .trim();
  return { cleaned, downloadData };
};

/** Remove export payload blocks before rendering */
export const sanitizeRender = (content) =>
  (content || '')
    .replace(/\[EXPORT_DATA\][\s\S]*?\[\/EXPORT_DATA\]/gi, '')
    .trim();
