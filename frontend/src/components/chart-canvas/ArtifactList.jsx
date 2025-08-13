import React from 'react';
import ArtifactListItem from './ArtifactListItem';
export default function ArtifactList({ artifacts, selectedId, onSelect, onTogglePin, onRename, onDelete }) {
  return (
    <div className="max-h-[40vh] overflow-y-auto pr-1 custom-scrollbar">
      {artifacts.length === 0 && <div className="text-xs text-slate-400">No visual artifacts yet.</div>}
      {artifacts.map(a => (
        <ArtifactListItem key={a.id} artifact={a} selected={a.id===selectedId} onSelect={onSelect} onTogglePin={onTogglePin} onRename={onRename} onDelete={onDelete} />
      ))}
    </div>
  );
}
