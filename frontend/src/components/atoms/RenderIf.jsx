import React from 'react';

export default function RenderIf({ condition, children }) {
  return condition ? <>{children}</> : null;
}
