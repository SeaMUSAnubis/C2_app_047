/**
 * Simple markdown → HTML formatter for AI chat messages.
 * Handles: **bold**, *italic*, `code`, ```code blocks```,
 * ## headings, - / * unordered lists, 1. ordered lists,
 * paragraph breaks (double newline).
 */
export function formatMarkdown(text: string): string {
  if (!text) return '';

  // Escape HTML first
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Code blocks (fenced) — capture before other rules
  html = html.replace(/```(?:\w*)\n([\s\S]*?)```/g, (_m, code) => {
    const escaped = code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return `<pre class="md-code-block"><code>${escaped.trim()}</code></pre>`;
  });

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code class="md-inline-code">$1</code>');

  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

  // Italic
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

  // Headings (## through ####)
  html = html.replace(/^#### (.+)$/gm, '<h4 class="md-heading">$1</h4>');
  html = html.replace(/^### (.+)$/gm, '<h3 class="md-heading">$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2 class="md-heading">$1</h2>');

  // Horizontal rules
  html = html.replace(/^---$/gm, '<hr class="md-hr">');

  // Unordered lists — handle lines starting with - or *
  // Split into blocks, process list groups
  const blocks = html.split('\n\n');
  const processed = blocks.map((block) => {
    const lines = block.split('\n');

    // Check if this block is an unordered list
    if (lines.every((l) => /^[-*]\s/.test(l) || l === '')) {
      const items = lines
        .filter((l) => l.trim())
        .map((l) => `<li>${l.replace(/^[-*]\s+/, '')}</li>`);
      return `<ul class="md-list">${items.join('')}</ul>`;
    }

    // Check if this block is an ordered list
    if (lines.every((l) => /^\d+\.\s/.test(l) || l === '')) {
      const items = lines
        .filter((l) => l.trim())
        .map((l) => `<li>${l.replace(/^\d+\.\s+/, '')}</li>`);
      return `<ol class="md-list md-list-ordered">${items.join('')}</ol>`;
    }

    // Regular paragraph
    return `<p class="md-paragraph">${lines.join('<br>')}</p>`;
  });

  return processed.join('');
}
