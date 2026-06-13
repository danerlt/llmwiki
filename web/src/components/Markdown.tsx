import ReactMarkdown from "react-markdown";
import { useNavigate } from "react-router-dom";
import remarkGfm from "remark-gfm";

export default function Markdown({ content }: { content: string }) {
  const navigate = useNavigate();
  return (
    <div className="prose max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a({ href, children }) {
            const to = href ?? "#";
            if (to.startsWith("/")) {
              return (
                <a
                  href={to}
                  className="text-blue-600 underline"
                  onClick={(e) => {
                    e.preventDefault();
                    navigate(to);
                  }}
                >
                  {children}
                </a>
              );
            }
            return (
              <a href={to} className="text-blue-600 underline">
                {children}
              </a>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
