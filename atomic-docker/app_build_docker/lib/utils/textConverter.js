"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.plainify = exports.humanize = exports.markdownify = exports.slugify = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const github_slugger_1 = require("github-slugger");
const marked_1 = require("marked");
// slugify
const slugify = (content) => {
    if (!content)
        return null;
    return (0, github_slugger_1.slug)(content);
};
exports.slugify = slugify;
// markdownify
const markdownify = (content, tag, className) => {
    if (!content)
        return null;
    const Tag = tag;
    return tag ? ((0, jsx_runtime_1.jsx)(Tag, { className: className, dangerouslySetInnerHTML: {
            __html: tag === "div" ? marked_1.marked.parse(content) : marked_1.marked.parseInline(content),
        } })) : ((0, jsx_runtime_1.jsx)("span", { className: className, dangerouslySetInnerHTML: {
            __html: marked_1.marked.parseInline(content),
        } }));
};
exports.markdownify = markdownify;
// humanize
const humanize = (content) => {
    if (!content)
        return null;
    return content
        .replace(/^[\s_]+|[\s_]+$/g, "")
        .replace(/[_\s]+/g, " ")
        .replace(/^[a-z]/, function (m) {
        return m.toUpperCase();
    });
};
exports.humanize = humanize;
// plainify
const plainify = (content) => {
    if (!content)
        return undefined;
    const mdParsed = marked_1.marked.parseInline(String(content));
    const filterBrackets = mdParsed.replace(/<\/?[^>]+(>|$)/gm, "");
    const filterSpaces = filterBrackets.replace(/[\r\n]\s*[\r\n]/gm, "");
    const stripHTML = htmlEntityDecoder(filterSpaces);
    return stripHTML;
};
exports.plainify = plainify;
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidGV4dENvbnZlcnRlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInRleHRDb252ZXJ0ZXIudHN4Il0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7QUFBQSxtREFBc0M7QUFDdEMsbUNBQWdDO0FBRWhDLFVBQVU7QUFDSCxNQUFNLE9BQU8sR0FBRyxDQUFDLE9BQWUsRUFBRSxFQUFFO0lBQ3pDLElBQUksQ0FBQyxPQUFPO1FBQUUsT0FBTyxJQUFJLENBQUM7SUFFMUIsT0FBTyxJQUFBLHFCQUFJLEVBQUMsT0FBTyxDQUFDLENBQUM7QUFDdkIsQ0FBQyxDQUFDO0FBSlcsUUFBQSxPQUFPLFdBSWxCO0FBRUYsY0FBYztBQUNQLE1BQU0sV0FBVyxHQUFHLENBQUMsT0FBZSxFQUFFLEdBQVksRUFBRSxTQUFrQixFQUFFLEVBQUU7SUFDL0UsSUFBSSxDQUFDLE9BQU87UUFBRSxPQUFPLElBQUksQ0FBQztJQUUxQixNQUFNLEdBQUcsR0FBRyxHQUFVLENBQUM7SUFDdkIsT0FBTyxHQUFHLENBQUMsQ0FBQyxDQUFDLENBQ1gsdUJBQUMsR0FBRyxJQUNGLFNBQVMsRUFBRSxTQUFTLEVBQ3BCLHVCQUF1QixFQUFFO1lBQ3ZCLE1BQU0sRUFDSixHQUFHLEtBQUssS0FBSyxDQUFDLENBQUMsQ0FBQyxlQUFNLENBQUMsS0FBSyxDQUFDLE9BQU8sQ0FBQyxDQUFDLENBQUMsQ0FBQyxlQUFNLENBQUMsV0FBVyxDQUFDLE9BQU8sQ0FBQztTQUN0RSxHQUNELENBQ0gsQ0FBQyxDQUFDLENBQUMsQ0FDRixpQ0FDRSxTQUFTLEVBQUUsU0FBUyxFQUNwQix1QkFBdUIsRUFBRTtZQUN2QixNQUFNLEVBQUUsZUFBTSxDQUFDLFdBQVcsQ0FBQyxPQUFPLENBQUM7U0FDcEMsR0FDRCxDQUNILENBQUM7QUFDSixDQUFDLENBQUM7QUFwQlcsUUFBQSxXQUFXLGVBb0J0QjtBQUVGLFdBQVc7QUFDSixNQUFNLFFBQVEsR0FBRyxDQUFDLE9BQWUsRUFBRSxFQUFFO0lBQzFDLElBQUksQ0FBQyxPQUFPO1FBQUUsT0FBTyxJQUFJLENBQUM7SUFFMUIsT0FBTyxPQUFPO1NBQ1gsT0FBTyxDQUFDLGtCQUFrQixFQUFFLEVBQUUsQ0FBQztTQUMvQixPQUFPLENBQUMsU0FBUyxFQUFFLEdBQUcsQ0FBQztTQUN2QixPQUFPLENBQUMsUUFBUSxFQUFFLFVBQVUsQ0FBUztRQUNwQyxPQUFPLENBQUMsQ0FBQyxXQUFXLEVBQUUsQ0FBQztJQUN6QixDQUFDLENBQUMsQ0FBQztBQUNQLENBQUMsQ0FBQztBQVRXLFFBQUEsUUFBUSxZQVNuQjtBQUVGLFdBQVc7QUFDSixNQUFNLFFBQVEsR0FBRyxDQUFDLE9BQVksRUFBRSxFQUFFO0lBQ3ZDLElBQUksQ0FBQyxPQUFPO1FBQUUsT0FBTyxTQUFTLENBQUM7SUFFL0IsTUFBTSxRQUFRLEdBQUcsZUFBTSxDQUFDLFdBQVcsQ0FBQyxNQUFNLENBQUMsT0FBTyxDQUFDLENBQUMsQ0FBQztJQUNyRCxNQUFNLGNBQWMsR0FBRyxRQUFRLENBQUMsT0FBTyxDQUFDLGtCQUFrQixFQUFFLEVBQUUsQ0FBQyxDQUFDO0lBQ2hFLE1BQU0sWUFBWSxHQUFHLGNBQWMsQ0FBQyxPQUFPLENBQUMsbUJBQW1CLEVBQUUsRUFBRSxDQUFDLENBQUM7SUFDckUsTUFBTSxTQUFTLEdBQUcsaUJBQWlCLENBQUMsWUFBWSxDQUFDLENBQUM7SUFDbEQsT0FBTyxTQUFTLENBQUM7QUFDbkIsQ0FBQyxDQUFDO0FBUlcsUUFBQSxRQUFRLFlBUW5CO0FBRUYsOEJBQThCO0FBQzlCLE1BQU0saUJBQWlCLEdBQUcsQ0FBQyxnQkFBd0IsRUFBRSxFQUFFO0lBQ3JELElBQUksVUFBVSxHQUFRO1FBQ3BCLFFBQVEsRUFBRSxHQUFHO1FBQ2IsTUFBTSxFQUFFLEdBQUc7UUFDWCxNQUFNLEVBQUUsR0FBRztRQUNYLE9BQU8sRUFBRSxHQUFHO1FBQ1osUUFBUSxFQUFFLEdBQUc7UUFDYixPQUFPLEVBQUUsR0FBRztLQUNiLENBQUM7SUFDRixJQUFJLG1CQUFtQixHQUFHLGdCQUFnQixDQUFDLE9BQU8sQ0FDaEQsaUNBQWlDLEVBQ2pDLENBQUMsTUFBTSxFQUFFLEVBQUUsQ0FBQyxVQUFVLENBQUMsTUFBTSxDQUFDLENBQy9CLENBQUM7SUFDRixPQUFPLG1CQUFtQixDQUFDO0FBQzdCLENBQUMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IHNsdWcgfSBmcm9tIFwiZ2l0aHViLXNsdWdnZXJcIjtcbmltcG9ydCB7IG1hcmtlZCB9IGZyb20gXCJtYXJrZWRcIjtcbmltcG9ydCBSZWFjdCBmcm9tICdyZWFjdCdcbi8vIHNsdWdpZnlcbmV4cG9ydCBjb25zdCBzbHVnaWZ5ID0gKGNvbnRlbnQ6IHN0cmluZykgPT4ge1xuICBpZiAoIWNvbnRlbnQpIHJldHVybiBudWxsO1xuXG4gIHJldHVybiBzbHVnKGNvbnRlbnQpO1xufTtcblxuLy8gbWFya2Rvd25pZnlcbmV4cG9ydCBjb25zdCBtYXJrZG93bmlmeSA9IChjb250ZW50OiBzdHJpbmcsIHRhZz86IHN0cmluZywgY2xhc3NOYW1lPzogc3RyaW5nKSA9PiB7XG4gIGlmICghY29udGVudCkgcmV0dXJuIG51bGw7XG5cbiAgY29uc3QgVGFnID0gdGFnIGFzIGFueTtcbiAgcmV0dXJuIHRhZyA/IChcbiAgICA8VGFnXG4gICAgICBjbGFzc05hbWU9e2NsYXNzTmFtZX1cbiAgICAgIGRhbmdlcm91c2x5U2V0SW5uZXJIVE1MPXt7XG4gICAgICAgIF9faHRtbDpcbiAgICAgICAgICB0YWcgPT09IFwiZGl2XCIgPyBtYXJrZWQucGFyc2UoY29udGVudCkgOiBtYXJrZWQucGFyc2VJbmxpbmUoY29udGVudCksXG4gICAgICB9fVxuICAgIC8+XG4gICkgOiAoXG4gICAgPHNwYW5cbiAgICAgIGNsYXNzTmFtZT17Y2xhc3NOYW1lfVxuICAgICAgZGFuZ2Vyb3VzbHlTZXRJbm5lckhUTUw9e3tcbiAgICAgICAgX19odG1sOiBtYXJrZWQucGFyc2VJbmxpbmUoY29udGVudCksXG4gICAgICB9fVxuICAgIC8+XG4gICk7XG59O1xuXG4vLyBodW1hbml6ZVxuZXhwb3J0IGNvbnN0IGh1bWFuaXplID0gKGNvbnRlbnQ6IHN0cmluZykgPT4ge1xuICBpZiAoIWNvbnRlbnQpIHJldHVybiBudWxsO1xuXG4gIHJldHVybiBjb250ZW50XG4gICAgLnJlcGxhY2UoL15bXFxzX10rfFtcXHNfXSskL2csIFwiXCIpXG4gICAgLnJlcGxhY2UoL1tfXFxzXSsvZywgXCIgXCIpXG4gICAgLnJlcGxhY2UoL15bYS16XS8sIGZ1bmN0aW9uIChtOiBzdHJpbmcpIHtcbiAgICAgIHJldHVybiBtLnRvVXBwZXJDYXNlKCk7XG4gICAgfSk7XG59O1xuXG4vLyBwbGFpbmlmeVxuZXhwb3J0IGNvbnN0IHBsYWluaWZ5ID0gKGNvbnRlbnQ6IGFueSkgPT4ge1xuICBpZiAoIWNvbnRlbnQpIHJldHVybiB1bmRlZmluZWQ7XG5cbiAgY29uc3QgbWRQYXJzZWQgPSBtYXJrZWQucGFyc2VJbmxpbmUoU3RyaW5nKGNvbnRlbnQpKTtcbiAgY29uc3QgZmlsdGVyQnJhY2tldHMgPSBtZFBhcnNlZC5yZXBsYWNlKC88XFwvP1tePl0rKD58JCkvZ20sIFwiXCIpO1xuICBjb25zdCBmaWx0ZXJTcGFjZXMgPSBmaWx0ZXJCcmFja2V0cy5yZXBsYWNlKC9bXFxyXFxuXVxccypbXFxyXFxuXS9nbSwgXCJcIik7XG4gIGNvbnN0IHN0cmlwSFRNTCA9IGh0bWxFbnRpdHlEZWNvZGVyKGZpbHRlclNwYWNlcyk7XG4gIHJldHVybiBzdHJpcEhUTUw7XG59O1xuXG4vLyBzdHJpcCBlbnRpdGllcyBmb3IgcGxhaW5pZnlcbmNvbnN0IGh0bWxFbnRpdHlEZWNvZGVyID0gKGh0bWxXaXRoRW50aXRpZXM6IHN0cmluZykgPT4ge1xuICBsZXQgZW50aXR5TGlzdDogYW55ID0ge1xuICAgIFwiJm5ic3A7XCI6IFwiIFwiLFxuICAgIFwiJmx0O1wiOiBcIjxcIixcbiAgICBcIiZndDtcIjogXCI+XCIsXG4gICAgXCImYW1wO1wiOiBcIiZcIixcbiAgICBcIiZxdW90O1wiOiAnXCInLFxuICAgIFwiJiMzOTtcIjogXCInXCIsXG4gIH07XG4gIGxldCBodG1sV2l0aG91dEVudGl0aWVzID0gaHRtbFdpdGhFbnRpdGllcy5yZXBsYWNlKFxuICAgIC8oJmFtcDt8Jmx0O3wmZ3Q7fCZxdW90O3wmIzM5OykvZyxcbiAgICAoZW50aXR5KSA9PiBlbnRpdHlMaXN0W2VudGl0eV1cbiAgKTtcbiAgcmV0dXJuIGh0bWxXaXRob3V0RW50aXRpZXM7XG59O1xuIl19