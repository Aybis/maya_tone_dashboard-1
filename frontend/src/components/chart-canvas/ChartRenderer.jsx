import React, { useEffect, useRef } from "react";
import { Chart } from "chart.js/auto";

export default function ChartRenderer({ spec }) {
  const canvasRef = useRef(null);
  const chartRef = useRef(null);
  useEffect(() => {
    if (!canvasRef.current) return;
    if (!spec || typeof spec !== "object") {
      console.warn("ChartRenderer: invalid spec", spec);
      return;
    }
    if (!spec.type || !spec.data) {
      console.warn("ChartRenderer: missing type or data", spec);
      return;
    }
    if (chartRef.current) {
      chartRef.current.destroy();
      chartRef.current = null;
    }
    try {
      const ctx = canvasRef.current.getContext("2d");
      chartRef.current = new Chart(ctx, spec);
    } catch (e) {
      console.error("Chart render error", e, spec);
    }
    return () => {
      if (chartRef.current) chartRef.current.destroy();
    };
  }, [spec]);
  return <canvas ref={canvasRef} className="max-h-72 w-full" />;
}
