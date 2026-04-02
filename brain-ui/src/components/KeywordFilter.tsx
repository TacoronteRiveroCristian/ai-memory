import { useState, useRef, useCallback, useEffect } from "react";
import styles from "./KeywordFilter.module.css";

interface KeywordFilterProps {
  value: string;
  onChange: (keyword: string) => void;
}

export default function KeywordFilter({ value, onChange }: KeywordFilterProps) {
  const [draft, setDraft] = useState(value);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setDraft(value);
  }, [value]);

  const flush = useCallback(
    (text: string) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      onChange(text.trim());
    },
    [onChange]
  );

  const handleChange = (text: string) => {
    setDraft(text);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => flush(text), 500);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      flush(draft);
    }
  };

  const clear = () => {
    setDraft("");
    flush("");
  };

  return (
    <div className={styles.wrapper}>
      <input
        className={styles.input}
        type="text"
        placeholder="Filter by keyword or tag..."
        value={draft}
        onChange={(e) => handleChange(e.target.value)}
        onKeyDown={handleKeyDown}
      />
      {draft && (
        <button className={styles.clear} onClick={clear}>
          ✕
        </button>
      )}
    </div>
  );
}
