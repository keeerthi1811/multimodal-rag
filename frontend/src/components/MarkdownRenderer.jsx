import React from "react";

export function formatInlineBold(text) {
  if (!text) return null;
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, idx) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={idx} className="font-semibold text-stone-900">
          {part.slice(2, -2)}
        </strong>
      );
    }
    return part;
  });
}

export default function MarkdownRenderer({ content, className = "" }) {
  if (!content) return null;

  const lines = content.split("\n");
  const renderedElements = [];
  let tableRows = [];
  let inTable = false;

  const flushTable = (keyPrefix) => {
    if (tableRows.length === 0) return;
    const header = tableRows[0];
    const dataRows = tableRows.slice(1);

    renderedElements.push(
      <div key={`table-${keyPrefix}`} className="overflow-x-auto my-3 border border-[#E5E1D8] rounded-xl bg-[#FAF9F6]/40 shadow-xs">
        <table className="w-full text-xs text-left border-collapse">
          <thead>
            <tr className="bg-[#EFECE6] border-b border-[#E5E1D8] text-[#1A1A1A]">
              {header.map((col, cIdx) => (
                <th key={cIdx} className="px-3.5 py-2 font-semibold text-[11.5px] tracking-wide">
                  {formatInlineBold(col)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E5E1D8]">
            {dataRows.map((row, rIdx) => (
              <tr key={rIdx} className="hover:bg-[#FFFFFF]/70 transition-colors">
                {row.map((cell, cIdx) => (
                  <td key={cIdx} className="px-3.5 py-2.5 text-[#2C2C2C] text-[11.5px] leading-snug">
                    {formatInlineBold(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
    tableRows = [];
    inTable = false;
  };

  lines.forEach((line, index) => {
    const trimmed = line.trim();

    // Table rows
    if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
      if (/^\|(?:\s*:?-+:?\s*\|)+$/.test(trimmed)) {
        return; // divider
      }
      const cells = trimmed.split("|").slice(1, -1).map((c) => c.trim());
      if (cells.length > 0) {
        inTable = true;
        tableRows.push(cells);
        return;
      }
    } else if (inTable) {
      flushTable(index);
    }

    if (!trimmed) {
      renderedElements.push(<div key={index} className="h-2" />);
      return;
    }

    // Horizontal rule
    if (/^[-_=*]{3,}$/.test(trimmed)) {
      renderedElements.push(<hr key={index} className="border-t border-stone-200 my-3" />);
      return;
    }

    // Headings
    if (trimmed.startsWith("###")) {
      const headingText = trimmed.replace(/^###\s*/, "");
      renderedElements.push(
        <h4 key={index} className="text-xs font-bold text-stone-900 uppercase tracking-wider mt-3 mb-1.5">
          {formatInlineBold(headingText)}
        </h4>
      );
      return;
    }
    if (trimmed.startsWith("##")) {
      const headingText = trimmed.replace(/^##\s*/, "");
      renderedElements.push(
        <h3 key={index} className="text-sm font-bold text-stone-900 mt-3 mb-1.5">
          {formatInlineBold(headingText)}
        </h3>
      );
      return;
    }

    // Bullet list items
    if (trimmed.startsWith("- ") || trimmed.startsWith("* ") || trimmed.startsWith("• ")) {
      const bulletText = trimmed.replace(/^[-*•]\s*/, "");
      renderedElements.push(
        <div key={index} className="flex items-start gap-2 my-1 text-xs text-stone-700 leading-relaxed">
          <span className="text-[#1B4332] font-bold select-none">•</span>
          <span className="flex-1">{formatInlineBold(bulletText)}</span>
        </div>
      );
      return;
    }

    // Regular paragraphs
    renderedElements.push(
      <p key={index} className="text-xs text-stone-800 leading-relaxed my-1">
        {formatInlineBold(trimmed)}
      </p>
    );
  });

  if (inTable) {
    flushTable("end");
  }

  return <div className={`space-y-0.5 ${className}`}>{renderedElements}</div>;
}
