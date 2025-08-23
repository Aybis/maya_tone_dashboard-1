import React from 'react';

export default function ExportDownload({ exportData }) {
  if (!exportData) return null;
  const { filename, contentType, base64 } = exportData;
  const handleDownload = () => {
    try {
      const byteChars = atob(base64);
      const byteNumbers = new Array(byteChars.length);
      for (let i = 0; i < byteChars.length; i++)
        byteNumbers[i] = byteChars.charCodeAt(i);
      const byteArray = new Uint8Array(byteNumbers);
      const blob = new Blob([byteArray], {
        type: contentType || 'application/octet-stream',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename || 'export.bin';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error('Failed to download export', e);
    }
  };
  return (
    <button
      onClick={handleDownload}
      className="self-start text-xs bg-green-600 hover:bg-green-700 text-white px-2 py-1 rounded shadow"
    >
      Download {filename || 'file'}
    </button>
  );
}
