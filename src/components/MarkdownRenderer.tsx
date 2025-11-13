
import React from 'react';
import ReactMarkdown from 'react-markdown';

export const MarkdownRenderer: React.FC<{ content: string }> = ({ content }) => {
    return (
        <ReactMarkdown
            components={{
                h1: ({ children }: any) => <h1 className="md-h1">{children}</h1>,
                h2: ({ children }: any) => <h2 className="md-h2">{children}</h2>,
                h3: ({ children }: any) => <h3 className="md-h3">{children}</h3>,
                p: ({ children }: any) => <p className="md-p">{children}</p>,
                ul: ({ children }: any) => <ul className="md-ul">{children}</ul>,
                ol: ({ children }: any) => <ol className="md-ol">{children}</ol>,
                li: ({ children }: any) => <li className="md-li">{children}</li>,
                code: ({ inline, children }: any) => inline ? <code className="md-inline-code">{children}</code> : <code className="md-code">{children}</code>,
                pre: ({ children }: any) => <pre className="md-code-block">{children}</pre>,
                blockquote: ({ children }: any) => <blockquote className="md-blockquote">{children}</blockquote>,
                table: ({ children }: any) => <table className="md-table">{children}</table>,
                thead: ({ children }: any) => <thead className="md-thead">{children}</thead>,
                tbody: ({ children }: any) => <tbody className="md-tbody">{children}</tbody>,
                tr: ({ children }: any) => <tr className="md-tr">{children}</tr>,
                th: ({ children }: any) => <th className="md-th">{children}</th>,
                td: ({ children }: any) => <td className="md-td">{children}</td>,
                a: ({ href, children }: any) => <a href={href} className="md-link" target="_blank" rel="noopener noreferrer">{children}</a>,
                strong: ({ children }: any) => <strong className="md-strong">{children}</strong>,
                em: ({ children }: any) => <em className="md-em">{children}</em>,
            }}
        >
            {content}
        </ReactMarkdown>
    );
};
