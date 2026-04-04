import styles from "./TabSwitcher.module.css";

export type TabId = "graph" | "health" | "guide";

interface TabSwitcherProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
}

const TABS: { id: TabId; label: string }[] = [
  { id: "graph", label: "\u{1f9e0} Graph" },
  { id: "health", label: "\u2764 Health" },
  { id: "guide", label: "\u{1f4d6} Guide" },
];

export default function TabSwitcher({ activeTab, onTabChange }: TabSwitcherProps) {
  return (
    <div className={styles.tabs}>
      {TABS.map((tab) => (
        <button
          key={tab.id}
          className={`${styles.tab} ${activeTab === tab.id ? styles.active : ""}`}
          onClick={() => onTabChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
