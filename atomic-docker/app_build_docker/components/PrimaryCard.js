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
const variant = (0, restyle_1.createVariant)({ themeKey: 'cardVariants', defaults: {
        margin: {
            phone: 's',
            tablet: 'm',
        },
        backgroundColor: 'primaryCardBackground',
    } });
const Box = (0, restyle_1.createBox)();
const Card = (0, restyle_1.createRestyleComponent)([variant], Box);
function PrimaryCard(props) {
    const { image, imageText } = props;
    function renderImage() {
        if (!image) {
            return null;
        }
        return ((0, jsx_runtime_1.jsxs)(Box, { style: {
                width: 'auto',
                height: sizes_1.default.CARD_IMAGE_HEIGHT,
                borderWidth: 0,
                overflow: 'hidden',
            }, children: [(0, jsx_runtime_1.jsx)(image_1.default, { src: image, height: sizes_1.default.CARD_IMAGE_HEIGHT, alt: imageText }), (0, jsx_runtime_1.jsx)(Box, { position: "absolute", bottom: 15, left: 10, children: (0, jsx_runtime_1.jsx)(Text_1.default, { variant: "primaryHeader", children: imageText ? imageText : null }) })] }));
    }
    return ((0, jsx_runtime_1.jsxs)(Card, { ...props, variant: "primaryElevated", children: [renderImage(), props.children ? props.children : null] }));
}
// const styles = (theme: any) =>
//   StyleSheet.create({
//     card: {
//       borderWidth: 0,
//       backgroundColor: theme.COLORS.WHITE,
//       width: theme.SIZES.CARD_WIDTH,
//       marginVertical: theme.SIZES.CARD_MARGIN_VERTICAL,
//     },
//     footer: {
//       justifyContent: 'flex-start',
//       alignItems: 'center',
//       paddingHorizontal: theme.SIZES.CARD_FOOTER_HORIZONTAL,
//       paddingVertical: theme.SIZES.CARD_FOOTER_VERTICAL,
//       backgroundColor: theme.COLORS.TRANSPARENT,
//       zIndex: 1,
//     },
//     avatar: {
//       width: theme.SIZES.CARD_AVATAR_WIDTH,
//       height: theme.SIZES.CARD_AVATAR_HEIGHT,
//       borderRadius: theme.SIZES.CARD_AVATAR_RADIUS,
//     },
//     title: {
//       justifyContent: 'center',
//     },
//     round: {
//       borderRadius: theme.SIZES.CARD_ROUND,
//     },
//     rounded: {
//       borderRadius: theme.SIZES.CARD_ROUNDED,
//     },
//   });
exports.default = PrimaryCard;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiUHJpbWFyeUNhcmQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJQcmltYXJ5Q2FyZC50c3giXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7O0FBRUEsdURBQThCO0FBQzlCLDhDQUd5QjtBQUV6Qiw2REFBb0M7QUFFcEMsbUVBQTBDO0FBRzFDLE1BQU0sT0FBTyxHQUFHLElBQUEsdUJBQWEsRUFBUSxFQUFDLFFBQVEsRUFBRSxjQUFjLEVBQUUsUUFBUSxFQUFFO1FBQ3hFLE1BQU0sRUFBRTtZQUNOLEtBQUssRUFBRSxHQUFHO1lBQ1YsTUFBTSxFQUFFLEdBQUc7U0FDWjtRQUNELGVBQWUsRUFBRSx1QkFBdUI7S0FDekMsRUFBQyxDQUFDLENBQUE7QUFFSCxNQUFNLEdBQUcsR0FBRyxJQUFBLG1CQUFTLEdBQVMsQ0FBQztBQUkvQixNQUFNLElBQUksR0FBRyxJQUFBLGdDQUFzQixFQUFlLENBQUMsT0FBTyxDQUFDLEVBQUUsR0FBRyxDQUFDLENBQUE7QUFFakUsU0FBUyxXQUFXLENBQUMsS0FBVTtJQUM3QixNQUFNLEVBQUUsS0FBSyxFQUFFLFNBQVMsRUFBRSxHQUFHLEtBQUssQ0FBQztJQUVuQyxTQUFTLFdBQVc7UUFDbEIsSUFBSSxDQUFDLEtBQUssRUFBRSxDQUFDO1lBQ1gsT0FBTyxJQUFJLENBQUM7UUFDZCxDQUFDO1FBRUQsT0FBTyxDQUNMLHdCQUFDLEdBQUcsSUFBQyxLQUFLLEVBQUU7Z0JBQ1YsS0FBSyxFQUFFLE1BQU07Z0JBQ2IsTUFBTSxFQUFFLGVBQUssQ0FBQyxpQkFBaUI7Z0JBQy9CLFdBQVcsRUFBRSxDQUFDO2dCQUNkLFFBQVEsRUFBRSxRQUFRO2FBQ25CLGFBRUcsdUJBQUMsZUFBSyxJQUFDLEdBQUcsRUFBRSxLQUFLLEVBQUUsTUFBTSxFQUFFLGVBQUssQ0FBQyxpQkFBaUIsRUFBRSxHQUFHLEVBQUUsU0FBUyxHQUFJLEVBQ3RFLHVCQUFDLEdBQUcsSUFBQyxRQUFRLEVBQUMsVUFBVSxFQUFDLE1BQU0sRUFBRSxFQUFFLEVBQUUsSUFBSSxFQUFFLEVBQUUsWUFDM0MsdUJBQUMsY0FBSSxJQUFDLE9BQU8sRUFBQyxlQUFlLFlBQzFCLFNBQVMsQ0FBQyxDQUFDLENBQUMsU0FBUyxDQUFDLENBQUMsQ0FBQyxJQUFJLEdBQ3hCLEdBQ0gsSUFDSixDQUNQLENBQUE7SUFDSCxDQUFDO0lBRUQsT0FBTyxDQUNMLHdCQUFDLElBQUksT0FDQyxLQUFLLEVBQ1QsT0FBTyxFQUFDLGlCQUFpQixhQUV0QixXQUFXLEVBQUUsRUFDYixLQUFLLENBQUMsUUFBUSxDQUFDLENBQUMsQ0FBQyxLQUFLLENBQUMsUUFBUSxDQUFDLENBQUMsQ0FBQyxJQUFJLElBQ3BDLENBQ1IsQ0FBQTtBQUNILENBQUM7QUFFRCxpQ0FBaUM7QUFDakMsd0JBQXdCO0FBQ3hCLGNBQWM7QUFDZCx3QkFBd0I7QUFDeEIsNkNBQTZDO0FBQzdDLHVDQUF1QztBQUN2QywwREFBMEQ7QUFDMUQsU0FBUztBQUNULGdCQUFnQjtBQUNoQixzQ0FBc0M7QUFDdEMsOEJBQThCO0FBQzlCLCtEQUErRDtBQUMvRCwyREFBMkQ7QUFDM0QsbURBQW1EO0FBQ25ELG1CQUFtQjtBQUNuQixTQUFTO0FBQ1QsZ0JBQWdCO0FBQ2hCLDhDQUE4QztBQUM5QyxnREFBZ0Q7QUFDaEQsc0RBQXNEO0FBQ3RELFNBQVM7QUFDVCxlQUFlO0FBQ2Ysa0NBQWtDO0FBQ2xDLFNBQVM7QUFDVCxlQUFlO0FBQ2YsOENBQThDO0FBQzlDLFNBQVM7QUFDVCxpQkFBaUI7QUFDakIsZ0RBQWdEO0FBQ2hELFNBQVM7QUFDVCxRQUFRO0FBRVIsa0JBQWUsV0FBVyxDQUFBIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IFJlYWN0IGZyb20gJ3JlYWN0J1xuaW1wb3J0IHsgU3R5bGVTaGVldCB9IGZyb20gJ3JlYWN0LW5hdGl2ZSdcbmltcG9ydCBJbWFnZSBmcm9tICduZXh0L2ltYWdlJ1xuaW1wb3J0IHtcbiAgY3JlYXRlVmFyaWFudCwgY3JlYXRlUmVzdHlsZUNvbXBvbmVudCwgVmFyaWFudFByb3BzLFxuICBjcmVhdGVCb3gsXG59IGZyb20gJ0BzaG9waWZ5L3Jlc3R5bGUnXG5pbXBvcnQge1RoZW1lfSBmcm9tICdAbGliL3RoZW1lL3RoZW1lJ1xuaW1wb3J0IFNJWkVTIGZyb20gJ0BsaWIvdGhlbWUvc2l6ZXMnXG5cbmltcG9ydCBUZXh0IGZyb20gJ0Bjb21wb25lbnRzL2NvbW1vbi9UZXh0J1xuXG5cbmNvbnN0IHZhcmlhbnQgPSBjcmVhdGVWYXJpYW50PFRoZW1lPih7dGhlbWVLZXk6ICdjYXJkVmFyaWFudHMnLCBkZWZhdWx0czoge1xuICBtYXJnaW46IHtcbiAgICBwaG9uZTogJ3MnLFxuICAgIHRhYmxldDogJ20nLFxuICB9LFxuICBiYWNrZ3JvdW5kQ29sb3I6ICdwcmltYXJ5Q2FyZEJhY2tncm91bmQnLFxufX0pXG5cbmNvbnN0IEJveCA9IGNyZWF0ZUJveDxUaGVtZT4oKTtcblxudHlwZSBQcm9wcyA9IFZhcmlhbnRQcm9wczxUaGVtZSwgJ2NhcmRWYXJpYW50cycgJiBSZWFjdC5Db21wb25lbnRQcm9wczx0eXBlb2YgQm94Pj5cblxuY29uc3QgQ2FyZCA9IGNyZWF0ZVJlc3R5bGVDb21wb25lbnQ8UHJvcHMsIFRoZW1lPihbdmFyaWFudF0sIEJveClcblxuZnVuY3Rpb24gUHJpbWFyeUNhcmQocHJvcHM6IGFueSkge1xuICBjb25zdCB7IGltYWdlLCBpbWFnZVRleHQgfSA9IHByb3BzO1xuXG4gIGZ1bmN0aW9uIHJlbmRlckltYWdlKCkge1xuICAgIGlmICghaW1hZ2UpIHtcbiAgICAgIHJldHVybiBudWxsO1xuICAgIH1cblxuICAgIHJldHVybiAoXG4gICAgICA8Qm94IHN0eWxlPXt7XG4gICAgICAgIHdpZHRoOiAnYXV0bycsXG4gICAgICAgIGhlaWdodDogU0laRVMuQ0FSRF9JTUFHRV9IRUlHSFQsXG4gICAgICAgIGJvcmRlcldpZHRoOiAwLFxuICAgICAgICBvdmVyZmxvdzogJ2hpZGRlbicsXG4gICAgICB9fT5cbiAgICAgICAgICB7LyogZXNsaW50LWRpc2FibGUtbmV4dC1saW5lIGpzeC1hMTF5L2FsdC10ZXh0Ki99XG4gICAgICAgICAgPEltYWdlIHNyYz17aW1hZ2V9IGhlaWdodD17U0laRVMuQ0FSRF9JTUFHRV9IRUlHSFR9IGFsdD17aW1hZ2VUZXh0fSAvPlxuICAgICAgICAgIDxCb3ggcG9zaXRpb249XCJhYnNvbHV0ZVwiIGJvdHRvbT17MTV9IGxlZnQ9ezEwfT5cbiAgICAgICAgICAgIDxUZXh0IHZhcmlhbnQ9XCJwcmltYXJ5SGVhZGVyXCI+XG4gICAgICAgICAgICAgIHtpbWFnZVRleHQgPyBpbWFnZVRleHQgOiBudWxsfVxuICAgICAgICAgICAgPC9UZXh0PlxuICAgICAgICAgIDwvQm94PlxuICAgICAgPC9Cb3g+XG4gICAgKVxuICB9XG5cbiAgcmV0dXJuIChcbiAgICA8Q2FyZFxuICAgICAgey4uLnByb3BzfVxuICAgICAgdmFyaWFudD1cInByaW1hcnlFbGV2YXRlZFwiXG4gICAgPlxuICAgICAgICB7cmVuZGVySW1hZ2UoKX1cbiAgICAgICAge3Byb3BzLmNoaWxkcmVuID8gcHJvcHMuY2hpbGRyZW4gOiBudWxsfVxuICAgIDwvQ2FyZD5cbiAgKVxufVxuXG4vLyBjb25zdCBzdHlsZXMgPSAodGhlbWU6IGFueSkgPT5cbi8vICAgU3R5bGVTaGVldC5jcmVhdGUoe1xuLy8gICAgIGNhcmQ6IHtcbi8vICAgICAgIGJvcmRlcldpZHRoOiAwLFxuLy8gICAgICAgYmFja2dyb3VuZENvbG9yOiB0aGVtZS5DT0xPUlMuV0hJVEUsXG4vLyAgICAgICB3aWR0aDogdGhlbWUuU0laRVMuQ0FSRF9XSURUSCxcbi8vICAgICAgIG1hcmdpblZlcnRpY2FsOiB0aGVtZS5TSVpFUy5DQVJEX01BUkdJTl9WRVJUSUNBTCxcbi8vICAgICB9LFxuLy8gICAgIGZvb3Rlcjoge1xuLy8gICAgICAganVzdGlmeUNvbnRlbnQ6ICdmbGV4LXN0YXJ0Jyxcbi8vICAgICAgIGFsaWduSXRlbXM6ICdjZW50ZXInLFxuLy8gICAgICAgcGFkZGluZ0hvcml6b250YWw6IHRoZW1lLlNJWkVTLkNBUkRfRk9PVEVSX0hPUklaT05UQUwsXG4vLyAgICAgICBwYWRkaW5nVmVydGljYWw6IHRoZW1lLlNJWkVTLkNBUkRfRk9PVEVSX1ZFUlRJQ0FMLFxuLy8gICAgICAgYmFja2dyb3VuZENvbG9yOiB0aGVtZS5DT0xPUlMuVFJBTlNQQVJFTlQsXG4vLyAgICAgICB6SW5kZXg6IDEsXG4vLyAgICAgfSxcbi8vICAgICBhdmF0YXI6IHtcbi8vICAgICAgIHdpZHRoOiB0aGVtZS5TSVpFUy5DQVJEX0FWQVRBUl9XSURUSCxcbi8vICAgICAgIGhlaWdodDogdGhlbWUuU0laRVMuQ0FSRF9BVkFUQVJfSEVJR0hULFxuLy8gICAgICAgYm9yZGVyUmFkaXVzOiB0aGVtZS5TSVpFUy5DQVJEX0FWQVRBUl9SQURJVVMsXG4vLyAgICAgfSxcbi8vICAgICB0aXRsZToge1xuLy8gICAgICAganVzdGlmeUNvbnRlbnQ6ICdjZW50ZXInLFxuLy8gICAgIH0sXG4vLyAgICAgcm91bmQ6IHtcbi8vICAgICAgIGJvcmRlclJhZGl1czogdGhlbWUuU0laRVMuQ0FSRF9ST1VORCxcbi8vICAgICB9LFxuLy8gICAgIHJvdW5kZWQ6IHtcbi8vICAgICAgIGJvcmRlclJhZGl1czogdGhlbWUuU0laRVMuQ0FSRF9ST1VOREVELFxuLy8gICAgIH0sXG4vLyAgIH0pO1xuXG5leHBvcnQgZGVmYXVsdCBQcmltYXJ5Q2FyZFxuIl19