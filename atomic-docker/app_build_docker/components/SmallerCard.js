"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const jsx_runtime_1 = require("react/jsx-runtime");
const image_1 = __importDefault(require("next/image"));
const restyle_1 = require("@shopify/restyle");
const sizes_1 = __importDefault(require("@lib/theme/sizes"));
const Text_1 = __importDefault(require("@components/common/Text"));
const theme_1 = require("@lib/theme/theme");
const variant = (0, restyle_1.createVariant)({ themeKey: 'cardVariants', defaults: {
        margin: {
            phone: 's',
            tablet: 'm',
        },
        backgroundColor: 'regularCardBackground',
    } });
const Box = (0, restyle_1.createBox)();
const Card = (0, restyle_1.createRestyleComponent)([variant], Box);
function SmallerCard(props) {
    const { image, caption, title, titleColor, captionColor, footerStyle } = props;
    // function renderAvatar() {
    //   if (!avatar) return null;
    //   return <Image source={{ uri: avatar }} style={styles.avatar} />;
    // }
    function renderImage() {
        if (!image) {
            return null;
        }
        return ((0, jsx_runtime_1.jsx)(Box, { style: {
                width: 'auto',
                height: sizes_1.default.CARD_IMAGE_HEIGHT,
                borderWidth: 0,
                overflow: 'hidden',
            }, children: (0, jsx_runtime_1.jsx)(image_1.default, { src: image, height: sizes_1.default.CARD_IMAGE_HEIGHT, alt: title }) }));
    }
    function renderAuthor() {
        if (!title)
            return null;
        return ((0, jsx_runtime_1.jsx)(Box, { flex: 1, flexDirection: "row", style: [styles.footer, footerStyle], justifyContent: "space-between", children: (0, jsx_runtime_1.jsxs)(Box, { children: [(0, jsx_runtime_1.jsx)(Box, { style: styles.title, children: (0, jsx_runtime_1.jsx)(Text_1.default, { variant: "cardTitle", color: titleColor, children: title }) }), (0, jsx_runtime_1.jsx)(Box, { flexDirection: "row", justifyContent: "flex-start", children: (0, jsx_runtime_1.jsx)(Box, { flexDirection: "row", alignItems: "flex-end", children: (0, jsx_runtime_1.jsx)(Text_1.default, { variant: "cardCaption", color: captionColor, children: caption }) }) })] }) }));
    }
    return ((0, jsx_runtime_1.jsxs)(Card, { ...props, variant: "miniElevated", children: [renderImage(), renderAuthor(), props.children ? props.children : null] }));
}
const styles = {
    card: {
        borderWidth: 0,
        backgroundColor: theme_1.palette.white,
        marginVertical: sizes_1.default.CARD_MARGIN_VERTICAL,
    },
    footer: {
        justifyContent: 'flex-start',
        alignItems: 'center',
        paddingHorizontal: sizes_1.default.CARD_FOOTER_HORIZONTAL,
        paddingVertical: sizes_1.default.CARD_FOOTER_VERTICAL,
        backgroundColor: theme_1.palette.transparent,
        zIndex: 1,
    },
    avatar: {
        width: sizes_1.default.CARD_AVATAR_WIDTH,
        height: sizes_1.default.CARD_AVATAR_HEIGHT,
        borderRadius: sizes_1.default.CARD_AVATAR_RADIUS,
    },
    title: {
        justifyContent: 'center',
    },
    round: {
        borderRadius: sizes_1.default.CARD_ROUND,
    },
    rounded: {
        borderRadius: sizes_1.default.CARD_ROUNDED,
    },
};
exports.default = SmallerCard;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiU21hbGxlckNhcmQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJTbWFsbGVyQ2FyZC50c3giXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7O0FBRUEsdURBQThCO0FBQzlCLDhDQUd5QjtBQUV6Qiw2REFBb0M7QUFFcEMsbUVBQTBDO0FBQzFDLDRDQUEwQztBQUUxQyxNQUFNLE9BQU8sR0FBRyxJQUFBLHVCQUFhLEVBQVEsRUFBQyxRQUFRLEVBQUUsY0FBYyxFQUFFLFFBQVEsRUFBRTtRQUN4RSxNQUFNLEVBQUU7WUFDTixLQUFLLEVBQUUsR0FBRztZQUNWLE1BQU0sRUFBRSxHQUFHO1NBQ1o7UUFDRCxlQUFlLEVBQUUsdUJBQXVCO0tBQ3pDLEVBQUMsQ0FBQyxDQUFBO0FBRUgsTUFBTSxHQUFHLEdBQUcsSUFBQSxtQkFBUyxHQUFTLENBQUM7QUFJL0IsTUFBTSxJQUFJLEdBQUcsSUFBQSxnQ0FBc0IsRUFBZSxDQUFDLE9BQU8sQ0FBQyxFQUFFLEdBQUcsQ0FBQyxDQUFBO0FBRWpFLFNBQVMsV0FBVyxDQUFDLEtBQVU7SUFDN0IsTUFBTSxFQUFFLEtBQUssRUFBRSxPQUFPLEVBQUUsS0FBSyxFQUM3QixVQUFVLEVBQUUsWUFBWSxFQUFFLFdBQVcsRUFBRSxHQUFHLEtBQUssQ0FBQztJQUVoRCw0QkFBNEI7SUFDNUIsOEJBQThCO0lBQzlCLHFFQUFxRTtJQUNyRSxJQUFJO0lBRUosU0FBUyxXQUFXO1FBQ2xCLElBQUksQ0FBQyxLQUFLLEVBQUUsQ0FBQztZQUNYLE9BQU8sSUFBSSxDQUFDO1FBQ2QsQ0FBQztRQUVELE9BQU8sQ0FDTCx1QkFBQyxHQUFHLElBQUMsS0FBSyxFQUFFO2dCQUNWLEtBQUssRUFBRSxNQUFNO2dCQUNiLE1BQU0sRUFBRSxlQUFLLENBQUMsaUJBQWlCO2dCQUMvQixXQUFXLEVBQUUsQ0FBQztnQkFDZCxRQUFRLEVBQUUsUUFBUTthQUNuQixZQUVHLHVCQUFDLGVBQUssSUFBQyxHQUFHLEVBQUUsS0FBSyxFQUFFLE1BQU0sRUFBRSxlQUFLLENBQUMsaUJBQWlCLEVBQUUsR0FBRyxFQUFFLEtBQUssR0FBSyxHQUNqRSxDQUNQLENBQUE7SUFDSCxDQUFDO0lBRUQsU0FBUyxZQUFZO1FBQ25CLElBQUksQ0FBQyxLQUFLO1lBQUUsT0FBTyxJQUFJLENBQUE7UUFFdkIsT0FBTyxDQUNMLHVCQUFDLEdBQUcsSUFBQyxJQUFJLEVBQUUsQ0FBQyxFQUFFLGFBQWEsRUFBQyxLQUFLLEVBQUMsS0FBSyxFQUFFLENBQUMsTUFBTSxDQUFDLE1BQU0sRUFBRSxXQUFXLENBQUMsRUFBRSxjQUFjLEVBQUMsZUFBZSxZQUNuRyx3QkFBQyxHQUFHLGVBQ0YsdUJBQUMsR0FBRyxJQUFDLEtBQUssRUFBRSxNQUFNLENBQUMsS0FBSyxZQUN0Qix1QkFBQyxjQUFJLElBQUMsT0FBTyxFQUFDLFdBQVcsRUFBQyxLQUFLLEVBQUUsVUFBVSxZQUN4QyxLQUFLLEdBQ0QsR0FDSCxFQUNOLHVCQUFDLEdBQUcsSUFBQyxhQUFhLEVBQUMsS0FBSyxFQUFDLGNBQWMsRUFBQyxZQUFZLFlBQ2xELHVCQUFDLEdBQUcsSUFBQyxhQUFhLEVBQUMsS0FBSyxFQUFDLFVBQVUsRUFBQyxVQUFVLFlBQzVDLHVCQUFDLGNBQUksSUFBQyxPQUFPLEVBQUMsYUFBYSxFQUFDLEtBQUssRUFBRSxZQUFZLFlBQzVDLE9BQU8sR0FDSCxHQUNILEdBQ0YsSUFDRixHQUNGLENBQ1AsQ0FBQztJQUNKLENBQUM7SUFFRCxPQUFPLENBQ0wsd0JBQUMsSUFBSSxPQUNDLEtBQUssRUFDVCxPQUFPLEVBQUMsY0FBYyxhQUVyQixXQUFXLEVBQUUsRUFDYixZQUFZLEVBQUUsRUFDZCxLQUFLLENBQUMsUUFBUSxDQUFDLENBQUMsQ0FBQyxLQUFLLENBQUMsUUFBUSxDQUFDLENBQUMsQ0FBQyxJQUFJLElBQ2xDLENBQ1IsQ0FBQTtBQUNILENBQUM7QUFFRCxNQUFNLE1BQU0sR0FBRztJQUNYLElBQUksRUFBRTtRQUNKLFdBQVcsRUFBRSxDQUFDO1FBQ2QsZUFBZSxFQUFFLGVBQU8sQ0FBQyxLQUFLO1FBRTlCLGNBQWMsRUFBRSxlQUFLLENBQUMsb0JBQW9CO0tBQzNDO0lBQ0QsTUFBTSxFQUFFO1FBQ04sY0FBYyxFQUFFLFlBQVk7UUFDNUIsVUFBVSxFQUFFLFFBQVE7UUFDcEIsaUJBQWlCLEVBQUUsZUFBSyxDQUFDLHNCQUFzQjtRQUMvQyxlQUFlLEVBQUUsZUFBSyxDQUFDLG9CQUFvQjtRQUMzQyxlQUFlLEVBQUUsZUFBTyxDQUFDLFdBQVc7UUFDcEMsTUFBTSxFQUFFLENBQUM7S0FDVjtJQUNELE1BQU0sRUFBRTtRQUNOLEtBQUssRUFBRSxlQUFLLENBQUMsaUJBQWlCO1FBQzlCLE1BQU0sRUFBRSxlQUFLLENBQUMsa0JBQWtCO1FBQ2hDLFlBQVksRUFBRSxlQUFLLENBQUMsa0JBQWtCO0tBQ3ZDO0lBQ0QsS0FBSyxFQUFFO1FBQ0wsY0FBYyxFQUFFLFFBQVE7S0FDbEI7SUFDUixLQUFLLEVBQUU7UUFDTCxZQUFZLEVBQUUsZUFBSyxDQUFDLFVBQVU7S0FDL0I7SUFDRCxPQUFPLEVBQUU7UUFDUCxZQUFZLEVBQUUsZUFBSyxDQUFDLFlBQVk7S0FDakM7Q0FDRixDQUFBO0FBRUgsa0JBQWUsV0FBVyxDQUFBIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IFJlYWN0IGZyb20gJ3JlYWN0J1xuaW1wb3J0IHsgU3R5bGVTaGVldCB9IGZyb20gJ3JlYWN0LW5hdGl2ZSdcbmltcG9ydCBJbWFnZSBmcm9tICduZXh0L2ltYWdlJ1xuaW1wb3J0IHtcbiAgY3JlYXRlVmFyaWFudCwgY3JlYXRlUmVzdHlsZUNvbXBvbmVudCwgVmFyaWFudFByb3BzLFxuICBjcmVhdGVCb3gsXG59IGZyb20gJ0BzaG9waWZ5L3Jlc3R5bGUnXG5pbXBvcnQge1RoZW1lfSBmcm9tICdAbGliL3RoZW1lL3RoZW1lJ1xuaW1wb3J0IFNJWkVTIGZyb20gJ0BsaWIvdGhlbWUvc2l6ZXMnXG5cbmltcG9ydCBUZXh0IGZyb20gJ0Bjb21wb25lbnRzL2NvbW1vbi9UZXh0J1xuaW1wb3J0IHsgcGFsZXR0ZSB9IGZyb20gJ0BsaWIvdGhlbWUvdGhlbWUnXG5cbmNvbnN0IHZhcmlhbnQgPSBjcmVhdGVWYXJpYW50PFRoZW1lPih7dGhlbWVLZXk6ICdjYXJkVmFyaWFudHMnLCBkZWZhdWx0czoge1xuICBtYXJnaW46IHtcbiAgICBwaG9uZTogJ3MnLFxuICAgIHRhYmxldDogJ20nLFxuICB9LFxuICBiYWNrZ3JvdW5kQ29sb3I6ICdyZWd1bGFyQ2FyZEJhY2tncm91bmQnLFxufX0pXG5cbmNvbnN0IEJveCA9IGNyZWF0ZUJveDxUaGVtZT4oKTtcblxudHlwZSBQcm9wcyA9IFZhcmlhbnRQcm9wczxUaGVtZSwgJ2NhcmRWYXJpYW50cycgJiBSZWFjdC5Db21wb25lbnRQcm9wczx0eXBlb2YgQm94Pj5cblxuY29uc3QgQ2FyZCA9IGNyZWF0ZVJlc3R5bGVDb21wb25lbnQ8UHJvcHMsIFRoZW1lPihbdmFyaWFudF0sIEJveClcblxuZnVuY3Rpb24gU21hbGxlckNhcmQocHJvcHM6IGFueSkge1xuICBjb25zdCB7IGltYWdlLCBjYXB0aW9uLCB0aXRsZSxcbiAgdGl0bGVDb2xvciwgY2FwdGlvbkNvbG9yLCBmb290ZXJTdHlsZSB9ID0gcHJvcHM7XG5cbiAgLy8gZnVuY3Rpb24gcmVuZGVyQXZhdGFyKCkge1xuICAvLyAgIGlmICghYXZhdGFyKSByZXR1cm4gbnVsbDtcbiAgLy8gICByZXR1cm4gPEltYWdlIHNvdXJjZT17eyB1cmk6IGF2YXRhciB9fSBzdHlsZT17c3R5bGVzLmF2YXRhcn0gLz47XG4gIC8vIH1cblxuICBmdW5jdGlvbiByZW5kZXJJbWFnZSgpIHtcbiAgICBpZiAoIWltYWdlKSB7XG4gICAgICByZXR1cm4gbnVsbDtcbiAgICB9XG5cbiAgICByZXR1cm4gKFxuICAgICAgPEJveCBzdHlsZT17e1xuICAgICAgICB3aWR0aDogJ2F1dG8nLFxuICAgICAgICBoZWlnaHQ6IFNJWkVTLkNBUkRfSU1BR0VfSEVJR0hULFxuICAgICAgICBib3JkZXJXaWR0aDogMCxcbiAgICAgICAgb3ZlcmZsb3c6ICdoaWRkZW4nLFxuICAgICAgfX0+XG4gICAgICAgICAgey8qIGVzbGludC1kaXNhYmxlLW5leHQtbGluZSBqc3gtYTExeS9hbHQtdGV4dCAqL31cbiAgICAgICAgICA8SW1hZ2Ugc3JjPXtpbWFnZX0gaGVpZ2h0PXtTSVpFUy5DQVJEX0lNQUdFX0hFSUdIVH0gYWx0PXt0aXRsZX0gIC8+XG4gICAgICA8L0JveD5cbiAgICApXG4gIH1cblxuICBmdW5jdGlvbiByZW5kZXJBdXRob3IoKSB7XG4gICAgaWYgKCF0aXRsZSkgcmV0dXJuIG51bGxcblxuICAgIHJldHVybiAoXG4gICAgICA8Qm94IGZsZXg9ezF9IGZsZXhEaXJlY3Rpb249XCJyb3dcIiBzdHlsZT17W3N0eWxlcy5mb290ZXIsIGZvb3RlclN0eWxlXX0ganVzdGlmeUNvbnRlbnQ9XCJzcGFjZS1iZXR3ZWVuXCI+XG4gICAgICAgIDxCb3g+XG4gICAgICAgICAgPEJveCBzdHlsZT17c3R5bGVzLnRpdGxlfT5cbiAgICAgICAgICAgIDxUZXh0IHZhcmlhbnQ9XCJjYXJkVGl0bGVcIiBjb2xvcj17dGl0bGVDb2xvcn0+XG4gICAgICAgICAgICAgIHt0aXRsZX1cbiAgICAgICAgICAgIDwvVGV4dD5cbiAgICAgICAgICA8L0JveD5cbiAgICAgICAgICA8Qm94IGZsZXhEaXJlY3Rpb249XCJyb3dcIiBqdXN0aWZ5Q29udGVudD1cImZsZXgtc3RhcnRcIj5cbiAgICAgICAgICAgIDxCb3ggZmxleERpcmVjdGlvbj1cInJvd1wiIGFsaWduSXRlbXM9XCJmbGV4LWVuZFwiPlxuICAgICAgICAgICAgICA8VGV4dCB2YXJpYW50PVwiY2FyZENhcHRpb25cIiBjb2xvcj17Y2FwdGlvbkNvbG9yfT5cbiAgICAgICAgICAgICAgICB7Y2FwdGlvbn1cbiAgICAgICAgICAgICAgPC9UZXh0PlxuICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgPC9Cb3g+XG4gICAgICAgIDwvQm94PlxuICAgICAgPC9Cb3g+XG4gICAgKTtcbiAgfVxuXG4gIHJldHVybiAoXG4gICAgPENhcmRcbiAgICAgIHsuLi5wcm9wc31cbiAgICAgIHZhcmlhbnQ9XCJtaW5pRWxldmF0ZWRcIlxuICAgID5cbiAgICAgIHtyZW5kZXJJbWFnZSgpfVxuICAgICAge3JlbmRlckF1dGhvcigpfVxuICAgICAge3Byb3BzLmNoaWxkcmVuID8gcHJvcHMuY2hpbGRyZW4gOiBudWxsfVxuICAgIDwvQ2FyZD5cbiAgKVxufVxuXG5jb25zdCBzdHlsZXMgPSB7XG4gICAgY2FyZDoge1xuICAgICAgYm9yZGVyV2lkdGg6IDAsXG4gICAgICBiYWNrZ3JvdW5kQ29sb3I6IHBhbGV0dGUud2hpdGUsXG4gICAgICBcbiAgICAgIG1hcmdpblZlcnRpY2FsOiBTSVpFUy5DQVJEX01BUkdJTl9WRVJUSUNBTCxcbiAgICB9LFxuICAgIGZvb3Rlcjoge1xuICAgICAganVzdGlmeUNvbnRlbnQ6ICdmbGV4LXN0YXJ0JyxcbiAgICAgIGFsaWduSXRlbXM6ICdjZW50ZXInLFxuICAgICAgcGFkZGluZ0hvcml6b250YWw6IFNJWkVTLkNBUkRfRk9PVEVSX0hPUklaT05UQUwsXG4gICAgICBwYWRkaW5nVmVydGljYWw6IFNJWkVTLkNBUkRfRk9PVEVSX1ZFUlRJQ0FMLFxuICAgICAgYmFja2dyb3VuZENvbG9yOiBwYWxldHRlLnRyYW5zcGFyZW50LFxuICAgICAgekluZGV4OiAxLFxuICAgIH0sXG4gICAgYXZhdGFyOiB7XG4gICAgICB3aWR0aDogU0laRVMuQ0FSRF9BVkFUQVJfV0lEVEgsXG4gICAgICBoZWlnaHQ6IFNJWkVTLkNBUkRfQVZBVEFSX0hFSUdIVCxcbiAgICAgIGJvcmRlclJhZGl1czogU0laRVMuQ0FSRF9BVkFUQVJfUkFESVVTLFxuICAgIH0sXG4gICAgdGl0bGU6IHtcbiAgICAgIGp1c3RpZnlDb250ZW50OiAnY2VudGVyJyxcbiAgICB9IGFzIGFueSxcbiAgICByb3VuZDoge1xuICAgICAgYm9yZGVyUmFkaXVzOiBTSVpFUy5DQVJEX1JPVU5ELFxuICAgIH0sXG4gICAgcm91bmRlZDoge1xuICAgICAgYm9yZGVyUmFkaXVzOiBTSVpFUy5DQVJEX1JPVU5ERUQsXG4gICAgfSxcbiAgfVxuXG5leHBvcnQgZGVmYXVsdCBTbWFsbGVyQ2FyZFxuIl19