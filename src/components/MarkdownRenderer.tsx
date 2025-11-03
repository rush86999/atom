
import React from 'react';

export const MarkdownRenderer: React.FC<{ content: string }> = ({ content }) => {
    // A simple markdown to JSX renderer. Note: This is a basic implementation.
    // For a production app, a library like 'react-markdown' would be better.
    const renderTokens = () => {
        const tokens: React.ReactElement[] = [];
        let inCodeBlock = false;
        let codeBlockContent: string[] = [];
        let codeBlockLang = '';

        content.split('\n').forEach((line, index) => {
            if (line.startsWith('```')) {
                if (inCodeBlock) {
                    tokens.push(<pre key={`cb-${index}`} className="md-code-block"><code>{codeBlockContent.join('\n')}</code></pre>);
                    codeBlockContent = [];
                    inCodeBlock = false;
                } else {
                    inCodeBlock = true;
                    codeBlockLang = line.substring(3);
                }
                return;
            }

            if (inCodeBlock) {
                codeBlockContent.push(line);
                return;
            }

            if (line.startsWith('# ')) {
                tokens.push(<h1 key={index} className="md-h1">{line.substring(2)}</h1>);
            } else if (line.startsWith('## ')) {
                tokens.push(<h2 key={index} className="md-h2">{line.substring(3)}</h2>);
            } else if (line.startsWith('### ')) {
                tokens.push(<h3 key={index} className="md-h3">{line.substring(4)}</h3>);
            } else if (line.match(/^\s*-\s/)) {
                 tokens.push(<li key={index} className="md-li">{line.replace(/^\s*-\s/, '')}</li>); // Should be wrapped in ul
            } else if (line.match(/^\|.*\|$/)) {
                 // Basic table support
                const cells = line.split('|').filter(c => c.trim() !== '');
                if(tokens.length > 0 && tokens[tokens.length-1].type === 'tr') {
                     // This is a header separator line, skip for now
                } else {
                     // This is a very basic table row implementation
                    tokens.push(<tr key={index}>{cells.map((c, i) => <td key={i} style={{border: '1px solid #333', padding: '0.5rem'}}>{c.trim()}</td>)}</tr>);
                }
            } else if (line.trim() === '') {
                // To create paragraph breaks
            } else {
                tokens.push(<p key={index} className="md-p">{line}</p>);
            }
        });
        return tokens;
    };
    
    return <>{renderTokens()}</>;
};
