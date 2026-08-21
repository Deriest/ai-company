/** @license MIT License (c) AI Company 2024 */

import { cn } from '../lib/utils';

interface TagBadgeProps {
  tag: string;
  onDelete?: () => void;
  variant?: 'default' | 'outline' | 'destructive';
}

export function TagBadge({ tag, onDelete, variant = 'default' }: TagBadgeProps) {
  const variants = {
    default: 'bg-primary text-primary-foreground hover:bg-primary/80',
    outline: 'border border-input bg-transparent hover:bg-accent hover:text-accent-foreground',
    destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/80',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
        variants[variant],
      )}
    >
      {tag}
      {onDelete && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          className="ml-1 inline-flex h-3 w-3 items-center justify-center rounded-full text-current hover:text-red-900 opacity-60 hover:opacity-100"
          aria-label={`Remove ${tag} tag`}
        >
          ×
        </button>
      )}
    </span>
  );
}

interface TagsListProps {
  tags: string[];
  onRemoveTag?: (tag: string) => void;
  maxDisplay?: number;
}

export function TagsList({ tags, onRemoveTag, maxDisplay = 5 }: TagsListProps) {
  if (!tags || tags.length === 0) {
    return null;
  }

  const displayTags = maxDisplay ? tags.slice(0, maxDisplay) : tags;
  const remainingCount = maxDisplay && tags.length > maxDisplay ? tags.length - maxDisplay : 0;

  return (
    <div className="flex flex-wrap gap-1">
      {displayTags.map((tag) => (
        <TagBadge key={tag} tag={tag} onDelete={onRemoveTag ? () => onRemoveTag(tag) : undefined} />
      ))}
      {remainingCount > 0 && (
        <span className="text-xs text-muted-foreground">
          +{remainingCount} more
        </span>
      )}
    </div>
  );
}
