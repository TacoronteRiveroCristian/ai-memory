import { useState, useRef, useCallback } from "react";
import styles from "./KeywordFilter.module.css";

interface KeywordFilterProps {
  keywords: string[];
  onChange: (keywords: string[]) => void;
}

export default function KeywordFilter({ keywords, onChange }: KeywordFilterProps) {
  const [draft, setDraft] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const addChip = useCallback(
    (text: string) => {
      const trimmed = text.trim().toLowerCase();
      if (!trimmed || keywords.includes(trimmed)) return;
      onChange([...keywords, trimmed]);
    },
    [keywords, onChange]
  );

  const removeChip = useCallback(
    (index: number) => {
      onChange(keywords.filter((_, i) => i !== index));
    },
    [keywords, onChange]
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.key === "Enter" || e.key === ",") && draft.trim()) {
      e.preventDefault();
      addChip(draft);
      setDraft("");
    } else if (e.key === "Backspace" && !draft && keywords.length > 0) {
      removeChip(keywords.length - 1);
    }
  };

  const handleChange = (text: string) => {
    // If user pastes or types a comma, split and add chips
    if (text.includes(",")) {
      const parts = text.split(",");
      for (const part of parts.slice(0, -1)) {
        addChip(part);
      }
      setDraft(parts[parts.length - 1]);
      return;
    }
    setDraft(text);
  };

  const clearAll = () => {
    setDraft("");
    onChange([]);
    inputRef.current?.focus();
  };

  const hasContent = keywords.length > 0 || draft.length > 0;

  return (
    <div
      className={styles.wrapper}
      onClick={() => inputRef.current?.focus()}
    >
      {keywords.map((kw, i) => (
        <span key={`${kw}-${i}`} className={styles.chip}>
          {kw}
          <button
            className={styles.chipRemove}
            onClick={(e) => {
              e.stopPropagation();
              removeChip(i);
            }}
          >
            ×
          </button>
        </span>
      ))}
      <input
        ref={inputRef}
        className={styles.input}
        type="text"
        placeholder={keywords.length === 0 ? "Filter by keyword or tag..." : ""}
        value={draft}
        onChange={(e) => handleChange(e.target.value)}
        onKeyDown={handleKeyDown}
      />
      {hasContent && (
        <button className={styles.clear} onClick={clearAll}>
          ✕
        </button>
      )}
    </div>
  );
}
