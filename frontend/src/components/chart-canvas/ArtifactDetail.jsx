import React from 'react';
import ChartRenderer from './ChartRenderer';
export default function ArtifactDetail({ artifact, exportPNG, exportCSV, exportJSON }) {
  if (!artifact) return <div className="text-xs text-slate-400">Select a chart or table.</div>;
  const { type, data } = artifact;
  return (
  <div className="space-y-2">
      {type === 'chart' && (
    <div className="bg-white dark:bg-slate-800/40 rounded border border-slate-300 dark:border-slate-700 p-2">
          <ChartRenderer spec={data} />
        </div>
      )}
      {type === 'table' && (
    <div className="overflow-x-auto max-h-80 border border-slate-300 dark:border-slate-700 rounded bg-white dark:bg-transparent">
          <table className="w-full text-xs">
            <thead className="bg-slate-700/60">
              <tr>{data.columns.map(col=> <th key={col} className="px-2 py-1 text-left font-medium">{col}</th>)}</tr>
            </thead>
            <tbody>
              {data.rows.map((row,i)=>(
                <tr key={i} className="odd:bg-slate-800/30 even:bg-slate-800/10">
                  {row.map((cell,j)=><td key={j} className="px-2 py-1 whitespace-nowrap">{cell}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="flex gap-2 flex-wrap">
        {type==='chart' && <button onClick={()=>exportPNG(artifact)} className="px-2 py-1 rounded bg-slate-700 hover:bg-slate-600 text-xs">PNG</button>}
        {type && <button onClick={()=>exportCSV(artifact)} className="px-2 py-1 rounded bg-slate-700 hover:bg-slate-600 text-xs">CSV</button>}
        {type && <button onClick={()=>exportJSON(artifact)} className="px-2 py-1 rounded bg-slate-700 hover:bg-slate-600 text-xs">JSON</button>}
      </div>
    </div>
  );
}
