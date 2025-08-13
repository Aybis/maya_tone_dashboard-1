import React, { useState } from 'react';
export default function ArtifactListItem({ artifact, selected, onSelect, onTogglePin, onRename, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(artifact.label);
  const commit = () => { onRename(artifact.id, value.trim() || artifact.label); setEditing(false); };
  return (
    <div className={`group rounded border p-1 mb-1 ${selected ? 'bg-blue-600/30 border-blue-500' : 'bg-slate-800/40 border-slate-700 hover:border-slate-500'}`}> 
      <div className="flex items-center gap-1">
        <button onClick={() => onSelect(artifact.id)} className="flex-1 text-left px-1 py-0.5 text-[11px] font-medium truncate text-slate-200 flex items-center gap-1">
          {artifact.pinned && <span className="text-amber-400" title="Pinned">★</span>}
          {!editing && <span className="truncate">{artifact.label}</span>}
          {editing && (
            <input autoFocus value={value} onChange={e=>setValue(e.target.value)} onBlur={commit} onKeyDown={e=>{ if(e.key==='Enter') commit(); if(e.key==='Escape'){ setValue(artifact.label); setEditing(false);} }} className="bg-slate-900/70 border border-slate-600 rounded px-1 py-0.5 text-[10px] w-32" />
          )}
        </button>
        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition">
          <button title={artifact.pinned?'Unpin':'Pin'} onClick={()=>onTogglePin(artifact.id)} className="px-1 py-0.5 rounded bg-slate-700 hover:bg-slate-600 text-[10px]">{artifact.pinned?'Unpin':'Pin'}</button>
          <button title="Rename" onClick={()=>setEditing(true)} className="px-1 py-0.5 rounded bg-slate-700 hover:bg-slate-600 text-[10px]">Edit</button>
          <button title="Delete" onClick={()=>onDelete(artifact.id)} className="px-1 py-0.5 rounded bg-red-700 hover:bg-red-600 text-[10px]">Del</button>
        </div>
      </div>
    </div>
  );
}
