"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const jsx_runtime_1 = require("react/jsx-runtime");
/* eslint-disable react-hooks/rules-of-hooks */
const react_1 = __importStar(require("react"));
const react_native_1 = require("react-native");
const Star_1 = __importDefault(require("@pages/Calendar/Rating/Star"));
// import Stars from '@pages/Calendar/Rating/Stars'
const Text_1 = __importDefault(require("@components/common/Text"));
const Box_1 = __importDefault(require("@components/common/Box"));
const { width, height } = react_native_1.Dimensions.get('screen');
const MODAL_HEIGHT = height * 0.25;
const RatingBottomModal = (props) => {
    if (!props.visible) {
        return null;
    }
    const pan = react_1.default.useRef(new react_native_1.Animated.ValueXY({ x: 0, y: height })).current;
    const [offset, setOffset] = react_1.default.useState(props.starRating || 0);
    const animatedWidth = react_1.default.useRef(0);
    const openAnim = () => {
        react_native_1.Animated.spring(pan.y, {
            toValue: height - MODAL_HEIGHT,
            bounciness: 0,
            useNativeDriver: true,
        }).start();
    };
    const closeAnim = () => {
        react_native_1.Animated.spring(pan.y, {
            toValue: height,
            useNativeDriver: true,
        }).start();
        // you may invoke it in the animation end callback, but
        // that may feel slower
        props.onClose();
    };
    react_1.default.useEffect(() => {
        props.onRatingChanged(offset);
    }, [offset, props]);
    react_1.default.useEffect(() => {
        const openAnim1 = () => {
            react_native_1.Animated.spring(pan.y, {
                toValue: height - MODAL_HEIGHT,
                bounciness: 0,
                useNativeDriver: true,
            }).start();
        };
        if (!props.visible) {
            return;
        }
        openAnim1();
    }, [pan.y, props.visible]);
    const changeOffset = (0, react_1.useCallback)((e) => {
        const { nativeEvent } = e;
        const distance = (width - animatedWidth.current) / 2;
        const starSize = animatedWidth.current / (props.maxStars || 5);
        let v = Number((nativeEvent.pageX - distance) / starSize);
        const rest = v - Math.trunc(v);
        if (rest <= 0.5) {
            v = Math.trunc(v);
        }
        else {
            v = Math.trunc(v) + 0.5;
        }
        setOffset(v);
    }, [props.maxStars]);
    const changeModalPosition = react_1.default.useCallback((gs) => {
        const value = height - MODAL_HEIGHT + gs.dy;
        // prevent dragging too high or too low
        if (value >= height || value < height - MODAL_HEIGHT) {
            return;
        }
        pan.y.setValue(value);
    }, [pan.y]);
    const modalResponder = react_1.default.useRef(react_native_1.PanResponder.create({
        onStartShouldSetPanResponder: (e) => {
            // check if touch is in the modal area
            if (e.nativeEvent.pageY > height - MODAL_HEIGHT) {
                return true;
            }
            closeAnim();
            return false;
        },
        onPanResponderGrant: () => {
            // TODO: show some visual feedback here
        },
        onPanResponderMove: (_, gs) => {
            changeModalPosition(gs);
        },
        onPanResponderRelease: (_, { dy }) => {
            if (dy < MODAL_HEIGHT / 2) {
                openAnim();
            }
            else {
                closeAnim();
            }
        },
    })).current;
    const starPanResponder = (0, react_1.useRef)(react_native_1.PanResponder.create({
        onStartShouldSetPanResponder: (e, gs) => {
            changeOffset(e);
            return true;
        },
        onPanResponderMove: (e, gs) => {
            // user swiped down on a star
            if (gs.dy > 50) {
                changeModalPosition(gs);
                return;
            }
            changeOffset(e);
        },
        onPanResponderRelease: (_, { dy }) => {
            if (dy < MODAL_HEIGHT / 2) {
                openAnim();
            }
            else {
                closeAnim();
            }
        },
    })).current;
    return ((0, jsx_runtime_1.jsx)(react_native_1.Animated.View, { ...modalResponder.panHandlers, style: [
            {
                position: 'absolute',
                top: 0,
                left: 0,
                width,
                height,
                backgroundColor: 'rgba(0,0,0,.1)',
            },
        ], children: (0, jsx_runtime_1.jsx)(react_native_1.Animated.View, { style: {
                opacity: pan.y.interpolate({
                    inputRange: [height - MODAL_HEIGHT, height],
                    outputRange: [1, 0.5],
                }),
                transform: [
                    {
                        translateY: pan.y,
                    },
                ],
            }, children: (0, jsx_runtime_1.jsx)(Box_1.default, { backgroundColor: "mainBackground", style: {
                    width: '100%',
                    height: MODAL_HEIGHT,
                    //   backgroundColor: '#fff',
                    shadowColor: '#ccc',
                    shadowOffset: { height: -1, width: 0 },
                    shadowRadius: 15,
                    shadowOpacity: 0.1,
                }, children: (0, jsx_runtime_1.jsxs)(Box_1.default, { style: {
                        flex: 1,
                        paddingTop: 24,
                        alignItems: 'center',
                        justifyContent: 'flex-start'
                    }, children: [(0, jsx_runtime_1.jsx)(Text_1.default, { variant: "rating", children: "rate your productivity level for this event" }), (0, jsx_runtime_1.jsx)(Box_1.default, { style: {
                                marginTop: 16,
                                flexDirection: 'row',
                            }, children: (0, jsx_runtime_1.jsx)(react_native_1.Animated.View, { onLayout: (e) => {
                                    animatedWidth.current = e.nativeEvent.layout.width;
                                }, style: { flexDirection: 'row' }, ...starPanResponder.panHandlers, children: Array.from({ length: props.maxStars || 5 }).map((_, i) => {
                                    return ((0, jsx_runtime_1.jsx)(Star_1.default, { size: props.starSize, distance: 8, offset: offset - i }, i));
                                }) }) })] }) }) }) }));
};
exports.default = RatingBottomModal;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiUmF0aW5nTW9kYWxCYXNpYy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIlJhdGluZ01vZGFsQmFzaWMudHN4Il0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztBQUFBLCtDQUErQztBQUMvQywrQ0FBa0Q7QUFFbEQsK0NBT3FCO0FBQ3JCLHVFQUE4QztBQUM5QyxtREFBbUQ7QUFDbkQsbUVBQTBDO0FBQzFDLGlFQUF3QztBQVd4QyxNQUFNLEVBQUUsS0FBSyxFQUFFLE1BQU0sRUFBRSxHQUFHLHlCQUFVLENBQUMsR0FBRyxDQUFDLFFBQVEsQ0FBQyxDQUFBO0FBRWxELE1BQU0sWUFBWSxHQUFHLE1BQU0sR0FBRyxJQUFJLENBQUE7QUFFbEMsTUFBTSxpQkFBaUIsR0FBRyxDQUFDLEtBQVksRUFBRSxFQUFFO0lBQ3pDLElBQUksQ0FBQyxLQUFLLENBQUMsT0FBTyxFQUFFLENBQUM7UUFDbkIsT0FBTyxJQUFJLENBQUE7SUFDYixDQUFDO0lBRUQsTUFBTSxHQUFHLEdBQUcsZUFBSyxDQUFDLE1BQU0sQ0FBQyxJQUFJLHVCQUFRLENBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQyxFQUFFLENBQUMsRUFBRSxDQUFDLEVBQUUsTUFBTSxFQUFFLENBQUMsQ0FBQyxDQUFDLE9BQU8sQ0FBQTtJQUMzRSxNQUFNLENBQUMsTUFBTSxFQUFFLFNBQVMsQ0FBQyxHQUFHLGVBQUssQ0FBQyxRQUFRLENBQUMsS0FBSyxDQUFDLFVBQVUsSUFBSSxDQUFDLENBQUMsQ0FBQTtJQUNqRSxNQUFNLGFBQWEsR0FBRyxlQUFLLENBQUMsTUFBTSxDQUFDLENBQUMsQ0FBQyxDQUFBO0lBRXJDLE1BQU0sUUFBUSxHQUFHLEdBQUcsRUFBRTtRQUNwQix1QkFBUSxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFO1lBQ3JCLE9BQU8sRUFBRSxNQUFNLEdBQUcsWUFBWTtZQUM5QixVQUFVLEVBQUUsQ0FBQztZQUNi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QUEiLCJzb3VyY2VzQ29udGVudCI6WyIvKiBlc2xpbnQtZGlzYWJsZSByZWFjdC1ob29rcy9ydWxlcy1vZi1ob29rcyAqL1xuaW1wb3J0IFJlYWN0LCB7IHVzZUNhbGxiYWNrLCB1c2VSZWYgfSBmcm9tICdyZWFjdCdcblxuaW1wb3J0IHtcbiAgQW5pbWF0ZWQsXG4gIFBhblJlc3BvbmRlcixcbiAgRGltZW5zaW9ucyxcbiAgU3R5bGVTaGVldCxcbiAgR2VzdHVyZVJlc3BvbmRlckV2ZW50LFxuICBQYW5SZXNwb25kZXJHZXN0dXJlU3RhdGUsXG59IGZyb20gJ3JlYWN0LW5hdGl2ZSdcbmltcG9ydCBTdGFyIGZyb20gJ0BwYWdlcy9DYWxlbmRhci9SYXRpbmcvU3Rhcidcbi8vIGltcG9ydCBTdGFycyBmcm9tICdAcGFnZXMvQ2FsZW5kYXIvUmF0aW5nL1N0YXJzJ1xuaW1wb3J0IFRleHQgZnJvbSAnQGNvbXBvbmVudHMvY29tbW9uL1RleHQnXG5pbXBvcnQgQm94IGZyb20gJ0Bjb21wb25lbnRzL2NvbW1vbi9Cb3gnXG5cbmludGVyZmFjZSBQcm9wcyB7XG4gIHZpc2libGU6IGJvb2xlYW47XG4gIG9uQ2xvc2U6ICgpID0+IHZvaWQ7XG4gIG9uUmF0aW5nQ2hhbmdlZDogKHJhdGluZzogbnVtYmVyKSA9PiB2b2lkO1xuICBzdGFyU2l6ZTogbnVtYmVyO1xuICBtYXhTdGFycz86IG51bWJlcjtcbiAgc3RhclJhdGluZz86IG51bWJlcjtcbn1cblxuY29uc3QgeyB3aWR0aCwgaGVpZ2h0IH0gPSBEaW1lbnNpb25zLmdldCgnc2NyZWVuJylcblxuY29uc3QgTU9EQUxfSEVJR0hUID0gaGVpZ2h0ICogMC4yNVxuXG5jb25zdCBSYXRpbmdCb3R0b21Nb2RhbCA9IChwcm9wczogUHJvcHMpID0+IHtcbiAgaWYgKCFwcm9wcy52aXNpYmxlKSB7XG4gICAgcmV0dXJuIG51bGxcbiAgfVxuXG4gIGNvbnN0IHBhbiA9IFJlYWN0LnVzZVJlZihuZXcgQW5pbWF0ZWQuVmFsdWVYWSh7IHg6IDAsIHk6IGhlaWdodCB9KSkuY3VycmVudFxuICBjb25zdCBbb2Zmc2V0LCBzZXRPZmZzZXRdID0gUmVhY3QudXNlU3RhdGUocHJvcHMuc3RhclJhdGluZyB8fCAwKVxuICBjb25zdCBhbmltYXRlZFdpZHRoID0gUmVhY3QudXNlUmVmKDApXG5cbiAgY29uc3Qgb3BlbkFuaW0gPSAoKSA9PiB7XG4gICAgQW5pbWF0ZWQuc3ByaW5nKHBhbi55LCB7XG4gICAgICB0b1ZhbHVlOiBoZWlnaHQgLSBNT0RBTF9IRUlHSFQsXG4gICAgICBib3VuY2luZXNzOiAwLFxuICAgICAgdXNlTmF0aXZlRHJpdmVyOiB0cnVlLFxuICAgIH0pLnN0YXJ0KClcbiAgfVxuXG4gIGNvbnN0IGNsb3NlQW5pbSA9ICgpID0+IHtcbiAgICBBbmltYXRlZC5zcHJpbmcocGFuLnksIHtcbiAgICAgIHRvVmFsdWU6IGhlaWdodCxcbiAgICAgIHVzZU5hdGl2ZURyaXZlcjogdHJ1ZSxcbiAgICB9KS5zdGFydCgpXG5cbiAgICAvLyB5b3UgbWF5IGludm9rZSBpdCBpbiB0aGUgYW5pbWF0aW9uIGVuZCBjYWxsYmFjaywgYnV0XG4gICAgLy8gdGhhdCBtYXkgZmVlbCBzbG93ZXJcbiAgICBwcm9wcy5vbkNsb3NlKClcbiAgfVxuXG4gIFJlYWN0LnVzZUVmZmVjdCgoKSA9PiB7XG4gICAgcHJvcHMub25SYXRpbmdDaGFuZ2VkKG9mZnNldCk7XG4gIH0sIFtvZmZzZXQsIHByb3BzXSk7XG5cbiAgUmVhY3QudXNlRWZmZWN0KCgpID0+IHtcbiAgICBjb25zdCBvcGVuQW5pbTEgPSAoKSA9PiB7XG4gICAgQW5pbWF0ZWQuc3ByaW5nKHBhbi55LCB7XG4gICAgICB0b1ZhbHVlOiBoZWlnaHQgLSBNT0RBTF9IRUlHSFQsXG4gICAgICBib3VuY2luZXNzOiAwLFxuICAgICAgdXNlTmF0aXZlRHJpdmVyOiB0cnVlLFxuICAgIH0pLnN0YXJ0KClcbiAgfVxuICAgIGlmICghcHJvcHMudmlzaWJsZSkge1xuICAgICAgcmV0dXJuXG4gICAgfVxuXG4gICAgb3BlbkFuaW0xKClcbiAgfSwgW3Bhbi55LCBwcm9wcy52aXNpYmxlXSlcblxuICBjb25zdCBjaGFuZ2VPZmZzZXQgPSB1c2VDYWxsYmFjaygoZTogR2VzdHVyZVJlc3BvbmRlckV2ZW50KSA9PiB7XG4gICAgY29uc3QgeyBuYXRpdmVFdmVudCB9ID0gZTtcblxuICAgIGNvbnN0IGRpc3RhbmNlID0gKHdpZHRoIC0gYW5pbWF0ZWRXaWR0aC5jdXJyZW50KSAvIDI7XG4gICAgY29uc3Qgc3RhclNpemUgPSBhbmltYXRlZFdpZHRoLmN1cnJlbnQgLyAocHJvcHMubWF4U3RhcnMgfHwgNSk7XG5cbiAgICBsZXQgdiA9IE51bWJlcigobmF0aXZlRXZlbnQucGFnZVggLSBkaXN0YW5jZSkgLyBzdGFyU2l6ZSk7XG5cbiAgICBjb25zdCByZXN0ID0gdiAtIE1hdGgudHJ1bmModik7XG5cbiAgICBpZiAocmVzdCA8PSAwLjUpIHtcbiAgICAgIHYgPSBNYXRoLnRydW5jKHYpO1xuICAgIH0gZWxzZSB7XG4gICAgICB2ID0gTWF0aC50cnVuYyh2KSArIDAuNTtcbiAgICB9XG5cbiAgICBzZXRPZmZzZXQodik7XG4gIH0sIFtwcm9wcy5tYXhTdGFyc10pXG5cbiAgY29uc3QgY2hhbmdlTW9kYWxQb3NpdGlvbiA9IFJlYWN0LnVzZUNhbGxiYWNrKFxuICAgIChnczogUGFuUmVzcG9uZGVyR2VzdHVyZVN0YXRlKSA9PiB7XG4gICAgICBjb25zdCB2YWx1ZSA9IGhlaWdodCAtIE1PREFMX0hFSUdIVCArIGdzLmR5XG5cbiAgICAgIC8vIHByZXZlbnQgZHJhZ2dpbmcgdG9vIGhpZ2ggb3IgdG9vIGxvd1xuICAgICAgaWYgKHZhbHVlID49IGhlaWdodCB8fCB2YWx1ZSA8IGhlaWdodCAtIE1PREFMX0hFSUdIVCkge1xuICAgICAgICByZXR1cm5cbiAgICAgIH1cblxuICAgICAgcGFuLnkuc2V0VmFsdWUodmFsdWUpXG4gICAgfSxcbiAgICBbcGFuLnldLFxuICApXG5cbiAgY29uc3QgbW9kYWxSZXNwb25kZXIgPSBSZWFjdC51c2VSZWYoXG4gICAgUGFuUmVzcG9uZGVyLmNyZWF0ZSh7XG4gICAgICBvblN0YXJ0U2hvdWxkU2V0UGFuUmVzcG9uZGVyOiAoZSkgPT4ge1xuICAgICAgICAvLyBjaGVjayBpZiB0b3VjaCBpcyBpbiB0aGUgbW9kYWwgYXJlYVxuICAgICAgICBpZiAoZS5uYXRpdmVFdmVudC5wYWdlWSA+IGhlaWdodCAtIE1PREFMX0hFSUdIVCkge1xuICAgICAgICAgIHJldHVybiB0cnVlO1xuICAgICAgICB9XG5cbiAgICAgICAgY2xvc2VBbmltKCk7XG5cbiAgICAgICAgcmV0dXJuIGZhbHNlO1xuICAgICAgfSxcbiAgICAgIG9uUGFuUmVzcG9uZGVyR3JhbnQ6ICgpID0+IHtcbiAgICAgICAgLy8gVE9ETzogc2hvdyBzb21lIHZpc3VhbCBmZWVkYmFjayBoZXJlXG4gICAgICB9LFxuICAgICAgb25QYW5SZXNwb25kZXJNb3ZlOiAoXywgZ3MpID0+IHtcbiAgICAgICAgY2hhbmdlTW9kYWxQb3NpdGlvbihncyk7XG4gICAgICB9LFxuICAgICAgb25QYW5SZXNwb25kZXJSZWxlYXNlOiAoXywgeyBkeSB9KSA9PiB7XG4gICAgICAgIGlmIChkeSA8IE1PREFMX0hFSUdIVCAvIDIpIHtcbiAgICAgICAgICBvcGVuQW5pbSgpO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgIGNsb3NlQW5pbSgpO1xuICAgICAgICB9XG4gICAgICB9LFxuICAgIH0pLFxuICApLmN1cnJlbnRcblxuICBjb25zdCBzdGFyUGFuUmVzcG9uZGVyID0gdXNlUmVmKFxuICAgIFBhblJlc3BvbmRlci5jcmVhdGUoe1xuICAgICAgb25TdGFydFNob3VsZFNldFBhblJlc3BvbmRlcjogKGUsIGdzKSA9PiB7XG4gICAgICAgIGNoYW5nZU9mZnNldChlKVxuICAgICAgICByZXR1cm4gdHJ1ZVxuICAgICAgfSxcbiAgICAgIG9uUGFuUmVzcG9uZGVyTW92ZTogKGUsIGdzKSA9PiB7XG4gICAgICAgIC8vIHVzZXIgc3dpcGVkIGRvd24gb24gYSBzdGFyXG4gICAgICAgIGlmIChncy5keSA+IDUwKSB7XG4gICAgICAgICAgY2hhbmdlTW9kYWxQb3NpdGlvbihncyk7XG4gICAgICAgICAgcmV0dXJuXG4gICAgICAgIH1cblxuICAgICAgICBjaGFuZ2VPZmZzZXQoZSlcbiAgICAgIH0sXG4gICAgICBvblBhblJlc3BvbmRlclJlbGVhc2U6IChfLCB7IGR5IH0pID0+IHtcbiAgICAgICAgaWYgKGR5IDwgTU9EQUxfSEVJR0hUIC8gMikge1xuICAgICAgICAgIG9wZW5BbmltKClcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICBjbG9zZUFuaW0oKVxuICAgICAgICB9XG4gICAgICB9LFxuICAgIH0pLFxuICApLmN1cnJlbnRcblxuICByZXR1cm4gKFxuICAgIDxBbmltYXRlZC5WaWV3XG4gICAgICB7Li4ubW9kYWxSZXNwb25kZXIucGFuSGFuZGxlcnN9XG4gICAgICBzdHlsZT17W1xuICAgICAgICB7XG4gICAgICAgICAgcG9zaXRpb246ICdhYnNvbHV0ZScsXG4gICAgICAgICAgdG9wOiAwLFxuICAgICAgICAgIGxlZnQ6IDAsXG4gICAgICAgICAgd2lkdGgsXG4gICAgICAgICAgaGVpZ2h0LFxuICAgICAgICAgIGJhY2tncm91bmRDb2xvcjogJ3JnYmEoMCwwLDAsLjEpJyxcbiAgICAgICAgfSxcbiAgICAgIF19PlxuICAgICAgPEFuaW1hdGVkLlZpZXdcbiAgICAgICAgc3R5bGU9e3tcbiAgICAgICAgICBvcGFjaXR5OiBwYW4ueS5pbnRlcnBvbGF0ZSh7XG4gICAgICAgICAgICBpbnB1dFJhbmdlOiBbaGVpZ2h0IC0gTU9EQUxfSEVJR0hULCBoZWlnaHRdLFxuICAgICAgICAgICAgb3V0cHV0UmFuZ2U6IFsxLCAwLjVdLFxuICAgICAgICAgIH0pLFxuICAgICAgICAgIHRyYW5zZm9ybTogW1xuICAgICAgICAgICAge1xuICAgICAgICAgICAgICB0cmFuc2xhdGVZOiBwYW4ueSxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgXSxcbiAgICAgICAgfX0+XG4gICAgICAgICAgPEJveFxuICAgICAgICAgICAgYmFja2dyb3VuZENvbG9yPVwibWFpbkJhY2tncm91bmRcIlxuICAgICAgICAgICAgc3R5bGU9e3tcbiAgICAgICAgICAgIHdpZHRoOiAnMTAwJScsXG4gICAgICAgICAgICBoZWlnaHQ6IE1PREFMX0hFSUdIVCxcbiAgICAgICAgICAgIC8vICAgYmFja2dyb3VuZENvbG9yOiAnI2ZmZicsXG4gICAgICAgICAgICBzaGFkb3dDb2xvcjogJyNjY2MnLFxuICAgICAgICAgICAgc2hhZG93T2Zmc2V0OiB7IGhlaWdodDogLTEsIHdpZHRoOiAwIH0sXG4gICAgICAgICAgICBzaGFkb3dSYWRpdXM6IDE1LFxuICAgICAgICAgICAgc2hhZG93T3BhY2l0eTogMC4xLFxuICAgICAgICAgICAgfX1cbiAgICAgICAgICA+XG4gICAgICAgICAgICAgIDxCb3hcbiAgICAgICAgICAgICAgICBzdHlsZT17e1xuICAgICAgICAgICAgICAgICAgICBmbGV4OiAxLFxuICAgICAgICAgICAgICAgICAgICBwYWRkaW5nVG9wOiAyNCxcbiAgICAgICAgICAgICAgICAgICAgYWxpZ25JdGVtczogJ2NlbnRlcicsXG4gICAgICAgICAgICAgICAgICAgIGp1c3RpZnlDb250ZW50OiAnZmxleC1zdGFydCdcbiAgICAgICAgICAgICAgfX0+XG4gICAgICAgICAgICAgICAgICA8VGV4dCB2YXJpYW50PVwicmF0aW5nXCI+XG4gICAgICAgICAgICAgICAgICAgICAgcmF0ZSB5b3VyIHByb2R1Y3Rpdml0eSBsZXZlbCBmb3IgdGhpcyBldmVudFxuICAgICAgICAgICAgICAgICAgPC9UZXh0PlxuXG4gICAgICAgICAgICAgICAgICA8Qm94XG4gICAgICAgICAgICAgICAgICAgICAgc3R5bGU9e3tcbiAgICAgICAgICAgICAgICAgICAgICBtYXJnaW5Ub3A6IDE2LFxuICAgICAgICAgICAgICAgICAgICAgIGZsZXhEaXJlY3Rpb246ICdyb3cnLFxuICAgICAgICAgICAgICAgICAgICB9fT5cbiAgICAgICAgICAgICAgICAgICAgICA8QW5pbWF0ZWQuVmlld1xuICAgICAgICAgICAgICAgICAgICAgIG9uTGF5b3V0PXsoZSkgPT4ge1xuICAgICAgICAgICAgICAgICAgICAgICAgICBhbmltYXRlZFdpZHRoLmN1cnJlbnQgPSBlLm5hdGl2ZUV2ZW50LmxheW91dC53aWR0aDtcbiAgICAgICAgICAgICAgICAgICAgICB9fVxuICAgICAgICAgICAgICAgICAgICAgIHN0eWxlPXt7IGZsZXhEaXJlY3Rpb246ICdyb3cnIH19XG4gICAgICAgICAgICAgICAgICAgICAgey4uLnN0YXJQYW5SZXNwb25kZXIucGFuSGFuZGxlcnN9PlxuICAgICAgICAgICAgICAgICAgICAgIHtBcnJheS5mcm9tKHsgbGVuZ3RoOiBwcm9wcy5tYXhTdGFycyB8fCA1IH0pLm1hcCgoXywgaSkgPT4ge1xuICAgICAgICAgICAgICAgICAgICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgICAgICAgICAgICAgICA8U3RhclxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAga2V5PXtpfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgc2l6ZT17cHJvcHMuc3RhclNpemV9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICBkaXN0YW5jZT17OH1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIG9mZnNldD17b2Zmc2V0IC0gaX1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgLz5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgICAgICAgICAgICB9KX1cbiAgICAgICAgICAgICAgICAgICAgICA8L0FuaW1hdGVkLlZpZXc+XG4gICAgICAgICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgPC9Cb3g+XG4gICAgICA8L0FuaW1hdGVkLlZpZXc+XG4gICAgPC9BbmltYXRlZC5WaWV3PlxuICApXG59XG5cbmV4cG9ydCBkZWZhdWx0IFJhdGluZ0JvdHRvbU1vZGFsIl19