import ReactMarkdown from "react-markdown";
import { useNavigate } from "react-router-dom";
import remarkGfm from "remark-gfm";

const PROSE =
  "prose prose-stone max-w-none " +
  "prose-headings:font-display prose-headings:font-semibold prose-headings:tracking-tight prose-headings:text-ink " +
  "prose-p:text-ink/90 prose-li:text-ink/90 " +
  "prose-a:font-medium prose-a:text-accent prose-a:no-underline hover:prose-a:underline " +
  "prose-code:rounded prose-code:bg-paper prose-code:px-1.5 prose-code:py-0.5 prose-code:font-mono prose-code:text-[.85em] prose-code:before:content-none prose-code:after:content-none " +
  "prose-pre:rounded-xl prose-pre:border prose-pre:border-line " +
  "prose-blockquote:border-l-accent prose-blockquote:text-ink-muted prose-hr:border-line";

export default function Markdown({ content }: { content: string }) {
  const navigate = useNavigate();
  return (
    <div className={PROSE}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a({ href, children }) {
            const to = href ?? "#";
            if (to.startsWith("/")) {
              return (
                <a
                  href={to}
                  onClick={(e) => {
                    e.preventDefault();
                    navigate(to);
                  }}
                >
                  {children}
                </a>
              );
            }
            return <a href={to}>{children}</a>;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
