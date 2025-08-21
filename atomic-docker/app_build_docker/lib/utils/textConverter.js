import { jsx } from "react/jsx-runtime";
import { slug } from "github-slugger";
import { marked } from "marked";

// slugify
export const slugify = (content) => {
    if (!content)
        return null;
    return slug(content);
};

// markdownify
export const markdownify = (content, tag, className) => {
    if (!content)
        return null;
    const Tag = tag;
    return tag ? (jsx(Tag, { className: className, dangerouslySetInnerHTML: {
            __html: tag === "div" ? marked.parse(content) : marked.parseInline(content),
        } })) : (jsx("span", { className: className, dangerouslySetInnerHTML: {
            __html: marked.parseInline(content),
        } }));
};

// humanize
export const humanize = (content) => {
    if (!content)
        return null;
    return content
        .replace(/^[\s_]+|[\s_]+$/g, "")
        .replace(/[_\s]+/g, " ")
        .replace(/^[a-z]/, function (m) {
        return m.toUpperCase();
    });
};

// plainify
export const plainify = (content) => {
    if (!content)
        return undefined;
    const mdParsed = marked.parseInline(String(content));
    const filterBrackets = mdParsed.replace(/<\/?[^>]+(>|$)/gm, "");
    const filterSpaces = filterBrackets.replace(/[\r\n]\s*[\r\n]/gm, "");
    const stripHTML = htmlEntityDecoder(filterSpaces);
    return stripHTML;
};

// strip entities for plainify
const htmlEntityDecoder = (htmlWithEntities) => {
    let entityList = {
        "&nbsp;": " ",
        "&lt;": "<",
        "&gt;": ">",
        "&amp;": "&",
        "&quot;": '"',
        "&#39;": "'",
    };
    let htmlWithoutEntities = htmlWithEntities.replace(/(&amp;|&lt;|&gt;|&quot;|&#39;)/g, (entity) => entityList[entity]);
    return htmlWithoutEntities;
};