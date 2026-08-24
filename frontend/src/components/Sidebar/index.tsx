import { Conversation } from "@/types";
import styles from "./index.module.scss";

interface Props {
  conversations: Conversation[];
  activeId: number | null;
  onNew: () => void;
  onSelect: (id: number) => void;
  onDelete: (id: number) => void;
}

const Sidebar = ({
  conversations,
  activeId,
  onNew,
  onSelect,
  onDelete,
}: Props) => {
  return (
    <aside className={styles.sidebar}>
      <div className={styles.header}>
        <span className={styles.logo}>Dochat</span>
        <button className={styles.newButton} onClick={onNew}>
          +
        </button>
      </div>

      <ul className={styles.list}>
        {conversations.length === 0 && (
          <li className={styles.empty}>No conversations yet</li>
        )}
        {conversations.map((conv) => (
          <li
            key={conv.id}
            className={`${styles.item} ${conv.id === activeId ? styles.active : ""}`}
            onClick={() => onSelect(conv.id)}
          >
            <span className={styles.itemTitle}>{conv.title}</span>
            <button
              className={styles.deleteButton}
              onClick={(e) => {
                e.stopPropagation();
                onDelete(conv.id);
              }}
              title="Delete"
            >
              ×
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
};

export default Sidebar;
