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
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const pan = react_1.default.useRef(new react_native_1.Animated.ValueXY({ x: 0, y: height })).current;
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const [offset, setOffset] = react_1.default.useState(props.starRating || 0);
    // eslint-disable-next-line react-hooks/rules-of-hooks
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
    // eslint-disable-next-line react-hooks/rules-of-hooks
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiUmF0aW5nTW9kYWwuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJSYXRpbmdNb2RhbC50c3giXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0FBQUEsK0NBQStDO0FBQy9DLCtDQUFrRDtBQUNsRCwrQ0FPcUI7QUFDckIsdUVBQThDO0FBQzlDLG1EQUFtRDtBQUNuRCxtRUFBMEM7QUFDMUMsaUVBQXdDO0FBV3hDLE1BQU0sRUFBRSxLQUFLLEVBQUUsTUFBTSxFQUFFLEdBQUcseUJBQVUsQ0FBQyxHQUFHLENBQUMsUUFBUSxDQUFDLENBQUE7QUFFbEQsTUFBTSxZQUFZLEdBQUcsTUFBTSxHQUFHLElBQUksQ0FBQTtBQUVsQyxNQUFNLGlCQUFpQixHQUFHLENBQUMsS0FBWSxFQUFFLEVBQUU7SUFDekMsSUFBSSxDQUFDLEtBQUssQ0FBQyxPQUFPLEVBQUUsQ0FBQztRQUNuQixPQUFPLElBQUksQ0FBQTtJQUNiLENBQUM7SUFFRCxzREFBc0Q7SUFDdEQsTUFBTSxHQUFHLEdBQUcsZUFBSyxDQUFDLE1BQU0sQ0FBQyxJQUFJLHVCQUFRLENBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQyxFQUFFLENBQUMsRUFBRSxDQUFDLEVBQUUsTUFBTSxFQUFFLENBQUMsQ0FBQyxDQUFDLE9BQU8sQ0FBQTtJQUMzRSxzREFBc0Q7SUFDdEQsTUFBTSxDQUFDLE1BQU0sRUFBRSxTQUFTLENBQUMsR0FBRyxlQUFLLENBQUMsUUFBUSxDQUFDLEtBQUssQ0FBQyxVQUFVLElBQUksQ0FBQyxDQUFDLENBQUE7SUFDakUsc0RBQXNEO0lBQ3RELE1BQU0sYUFBYSxHQUFHLGVBQUssQ0FBQyxNQUFNLENBQUMsQ0FBQyxDQUFDLENBQUE7SUFFckMsTUFBTSxRQUFRLEdBQUcsR0FBRyxFQUFFO1FBQ3BCLHVCQUFRLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUU7WUFDckIsT0FBTyxFQUFFLE1BQU0sR0FBRyxZ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QixDQUFBO0FBQ0gsQ0FBQyxDQUFBO0FBRUQsa0JBQWUsaUJBQWlCLENBQUEiLCJzb3VyY2VzQ29udGVudCI6WyIvKiBlc2xpbnQtZGlzYWJsZSByZWFjdC1ob29rcy9ydWxlcy1vZi1ob29rcyAqL1xuaW1wb3J0IFJlYWN0LCB7IHVzZUNhbGxiYWNrLCB1c2VSZWYgfSBmcm9tICdyZWFjdCdcbmltcG9ydCB7XG4gIEFuaW1hdGVkLFxuICBQYW5SZXNwb25kZXIsXG4gIERpbWVuc2lvbnMsXG4gIFN0eWxlU2hlZXQsXG4gIEdlc3R1cmVSZXNwb25kZXJFdmVudCxcbiAgUGFuUmVzcG9uZGVyR2VzdHVyZVN0YXRlLFxufSBmcm9tICdyZWFjdC1uYXRpdmUnXG5pbXBvcnQgU3RhciBmcm9tICdAcGFnZXMvQ2FsZW5kYXIvUmF0aW5nL1N0YXInXG4vLyBpbXBvcnQgU3RhcnMgZnJvbSAnQHBhZ2VzL0NhbGVuZGFyL1JhdGluZy9TdGFycydcbmltcG9ydCBUZXh0IGZyb20gJ0Bjb21wb25lbnRzL2NvbW1vbi9UZXh0J1xuaW1wb3J0IEJveCBmcm9tICdAY29tcG9uZW50cy9jb21tb24vQm94J1xuXG5pbnRlcmZhY2UgUHJvcHMge1xuICB2aXNpYmxlOiBib29sZWFuO1xuICBvbkNsb3NlOiAoKSA9PiB2b2lkO1xuICBvblJhdGluZ0NoYW5nZWQ6IChyYXRpbmc6IG51bWJlcikgPT4gdm9pZDtcbiAgc3RhclNpemU6IG51bWJlcjtcbiAgbWF4U3RhcnM/OiBudW1iZXI7XG4gIHN0YXJSYXRpbmc/OiBudW1iZXI7XG59XG5cbmNvbnN0IHsgd2lkdGgsIGhlaWdodCB9ID0gRGltZW5zaW9ucy5nZXQoJ3NjcmVlbicpXG5cbmNvbnN0IE1PREFMX0hFSUdIVCA9IGhlaWdodCAqIDAuMjVcblxuY29uc3QgUmF0aW5nQm90dG9tTW9kYWwgPSAocHJvcHM6IFByb3BzKSA9PiB7XG4gIGlmICghcHJvcHMudmlzaWJsZSkge1xuICAgIHJldHVybiBudWxsXG4gIH1cblxuICAvLyBlc2xpbnQtZGlzYWJsZS1uZXh0LWxpbmUgcmVhY3QtaG9va3MvcnVsZXMtb2YtaG9va3NcbiAgY29uc3QgcGFuID0gUmVhY3QudXNlUmVmKG5ldyBBbmltYXRlZC5WYWx1ZVhZKHsgeDogMCwgeTogaGVpZ2h0IH0pKS5jdXJyZW50XG4gIC8vIGVzbGludC1kaXNhYmxlLW5leHQtbGluZSByZWFjdC1ob29rcy9ydWxlcy1vZi1ob29rc1xuICBjb25zdCBbb2Zmc2V0LCBzZXRPZmZzZXRdID0gUmVhY3QudXNlU3RhdGUocHJvcHMuc3RhclJhdGluZyB8fCAwKVxuICAvLyBlc2xpbnQtZGlzYWJsZS1uZXh0LWxpbmUgcmVhY3QtaG9va3MvcnVsZXMtb2YtaG9va3NcbiAgY29uc3QgYW5pbWF0ZWRXaWR0aCA9IFJlYWN0LnVzZVJlZigwKVxuXG4gIGNvbnN0IG9wZW5BbmltID0gKCkgPT4ge1xuICAgIEFuaW1hdGVkLnNwcmluZyhwYW4ueSwge1xuICAgICAgdG9WYWx1ZTogaGVpZ2h0IC0gTU9EQUxfSEVJR0hULFxuICAgICAgYm91bmNpbmVzczogMCxcbiAgICAgIHVzZU5hdGl2ZURyaXZlcjogdHJ1ZSxcbiAgICB9KS5zdGFydCgpXG4gIH1cblxuICBjb25zdCBjbG9zZUFuaW0gPSAoKSA9PiB7XG4gICAgQW5pbWF0ZWQuc3ByaW5nKHBhbi55LCB7XG4gICAgICB0b1ZhbHVlOiBoZWlnaHQsXG4gICAgICB1c2VOYXRpdmVEcml2ZXI6IHRydWUsXG4gICAgfSkuc3RhcnQoKVxuXG4gICAgLy8geW91IG1heSBpbnZva2UgaXQgaW4gdGhlIGFuaW1hdGlvbiBlbmQgY2FsbGJhY2ssIGJ1dFxuICAgIC8vIHRoYXQgbWF5IGZlZWwgc2xvd2VyXG4gICAgcHJvcHMub25DbG9zZSgpXG4gIH1cblxuICAvLyBlc2xpbnQtZGlzYWJsZS1uZXh0LWxpbmUgcmVhY3QtaG9va3MvcnVsZXMtb2YtaG9va3NcbiAgUmVhY3QudXNlRWZmZWN0KCgpID0+IHtcbiAgICBwcm9wcy5vblJhdGluZ0NoYW5nZWQob2Zmc2V0KTtcbiAgfSwgW29mZnNldCwgcHJvcHNdKTtcblxuICBSZWFjdC51c2VFZmZlY3QoKCkgPT4ge1xuICAgIGNvbnN0IG9wZW5BbmltMSA9ICgpID0+IHtcbiAgICAgIEFuaW1hdGVkLnNwcmluZyhwYW4ueSwge1xuICAgICAgICB0b1ZhbHVlOiBoZWlnaHQgLSBNT0RBTF9IRUlHSFQsXG4gICAgICAgIGJvdW5jaW5lc3M6IDAsXG4gICAgICAgIHVzZU5hdGl2ZURyaXZlcjogdHJ1ZSxcbiAgICAgIH0pLnN0YXJ0KClcbiAgICB9XG4gICAgaWYgKCFwcm9wcy52aXNpYmxlKSB7XG4gICAgICByZXR1cm5cbiAgICB9XG5cbiAgICBvcGVuQW5pbTEoKVxuICB9LCBbcGFuLnksIHByb3BzLnZpc2libGVdKVxuXG4gIGNvbnN0IGNoYW5nZU9mZnNldCA9IHVzZUNhbGxiYWNrKChlOiBHZXN0dXJlUmVzcG9uZGVyRXZlbnQpID0+IHtcbiAgICBjb25zdCB7IG5hdGl2ZUV2ZW50IH0gPSBlO1xuXG4gICAgY29uc3QgZGlzdGFuY2UgPSAod2lkdGggLSBhbmltYXRlZFdpZHRoLmN1cnJlbnQpIC8gMjtcbiAgICBjb25zdCBzdGFyU2l6ZSA9IGFuaW1hdGVkV2lkdGguY3VycmVudCAvIChwcm9wcy5tYXhTdGFycyB8fCA1KTtcblxuICAgIGxldCB2ID0gTnVtYmVyKChuYXRpdmVFdmVudC5wYWdlWCAtIGRpc3RhbmNlKSAvIHN0YXJTaXplKTtcblxuICAgIGNvbnN0IHJlc3QgPSB2IC0gTWF0aC50cnVuYyh2KTtcblxuICAgIGlmIChyZXN0IDw9IDAuNSkge1xuICAgICAgdiA9IE1hdGgudHJ1bmModik7XG4gICAgfSBlbHNlIHtcbiAgICAgIHYgPSBNYXRoLnRydW5jKHYpICsgMC41O1xuICAgIH1cblxuICAgIHNldE9mZnNldCh2KTtcbiAgfSwgW3Byb3BzLm1heFN0YXJzXSlcblxuICBjb25zdCBjaGFuZ2VNb2RhbFBvc2l0aW9uID0gUmVhY3QudXNlQ2FsbGJhY2soXG4gICAgKGdzOiBQYW5SZXNwb25kZXJHZXN0dXJlU3RhdGUpID0+IHtcbiAgICAgIGNvbnN0IHZhbHVlID0gaGVpZ2h0IC0gTU9EQUxfSEVJR0hUICsgZ3MuZHlcblxuICAgICAgLy8gcHJldmVudCBkcmFnZ2luZyB0b28gaGlnaCBvciB0b28gbG93XG4gICAgICBpZiAodmFsdWUgPj0gaGVpZ2h0IHx8IHZhbHVlIDwgaGVpZ2h0IC0gTU9EQUxfSEVJR0hUKSB7XG4gICAgICAgIHJldHVyblxuICAgICAgfVxuXG4gICAgICBwYW4ueS5zZXRWYWx1ZSh2YWx1ZSlcbiAgICB9LFxuICAgIFtwYW4ueV0sXG4gIClcblxuICBjb25zdCBtb2RhbFJlc3BvbmRlciA9IFJlYWN0LnVzZVJlZihcbiAgICBQYW5SZXNwb25kZXIuY3JlYXRlKHtcbiAgICAgIG9uU3RhcnRTaG91bGRTZXRQYW5SZXNwb25kZXI6IChlKSA9PiB7XG4gICAgICAgIC8vIGNoZWNrIGlmIHRvdWNoIGlzIGluIHRoZSBtb2RhbCBhcmVhXG4gICAgICAgIGlmIChlLm5hdGl2ZUV2ZW50LnBhZ2VZID4gaGVpZ2h0IC0gTU9EQUxfSEVJR0hUKSB7XG4gICAgICAgICAgcmV0dXJuIHRydWU7XG4gICAgICAgIH1cblxuICAgICAgICBjbG9zZUFuaW0oKTtcblxuICAgICAgICByZXR1cm4gZmFsc2U7XG4gICAgICB9LFxuICAgICAgb25QYW5SZXNwb25kZXJHcmFudDogKCkgPT4ge1xuICAgICAgICAvLyBUT0RPOiBzaG93IHNvbWUgdmlzdWFsIGZlZWRiYWNrIGhlcmVcbiAgICAgIH0sXG4gICAgICBvblBhblJlc3BvbmRlck1vdmU6IChfLCBncykgPT4ge1xuICAgICAgICBjaGFuZ2VNb2RhbFBvc2l0aW9uKGdzKTtcbiAgICAgIH0sXG4gICAgICBvblBhblJlc3BvbmRlclJlbGVhc2U6IChfLCB7IGR5IH0pID0+IHtcbiAgICAgICAgaWYgKGR5IDwgTU9EQUxfSEVJR0hUIC8gMikge1xuICAgICAgICAgIG9wZW5BbmltKCk7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgY2xvc2VBbmltKCk7XG4gICAgICAgIH1cbiAgICAgIH0sXG4gICAgfSksXG4gICkuY3VycmVudFxuXG4gIGNvbnN0IHN0YXJQYW5SZXNwb25kZXIgPSB1c2VSZWYoXG4gICAgUGFuUmVzcG9uZGVyLmNyZWF0ZSh7XG4gICAgICBvblN0YXJ0U2hvdWxkU2V0UGFuUmVzcG9uZGVyOiAoZSwgZ3MpID0+IHtcbiAgICAgICAgY2hhbmdlT2Zmc2V0KGUpXG4gICAgICAgIHJldHVybiB0cnVlXG4gICAgICB9LFxuICAgICAgb25QYW5SZXNwb25kZXJNb3ZlOiAoZSwgZ3MpID0+IHtcbiAgICAgICAgLy8gdXNlciBzd2lwZWQgZG93biBvbiBhIHN0YXJcbiAgICAgICAgaWYgKGdzLmR5ID4gNTApIHtcbiAgICAgICAgICBjaGFuZ2VNb2RhbFBvc2l0aW9uKGdzKTtcbiAgICAgICAgICByZXR1cm5cbiAgICAgICAgfVxuXG4gICAgICAgIGNoYW5nZU9mZnNldChlKVxuICAgICAgfSxcbiAgICAgIG9uUGFuUmVzcG9uZGVyUmVsZWFzZTogKF8sIHsgZHkgfSkgPT4ge1xuICAgICAgICBpZiAoZHkgPCBNT0RBTF9IRUlHSFQgLyAyKSB7XG4gICAgICAgICAgb3BlbkFuaW0oKVxuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgIGNsb3NlQW5pbSgpXG4gICAgICAgIH1cbiAgICAgIH0sXG4gICAgfSksXG4gICkuY3VycmVudFxuXG4gIHJldHVybiAoXG4gICAgPEFuaW1hdGVkLlZpZXdcbiAgICAgIHsuLi5tb2RhbFJlc3BvbmRlci5wYW5IYW5kbGVyc31cbiAgICAgIHN0eWxlPXtbXG4gICAgICAgIHtcbiAgICAgICAgICBwb3NpdGlvbjogJ2Fic29sdXRlJyxcbiAgICAgICAgICB0b3A6IDAsXG4gICAgICAgICAgbGVmdDogMCxcbiAgICAgICAgICB3aWR0aCxcbiAgICAgICAgICBoZWlnaHQsXG4gICAgICAgICAgYmFja2dyb3VuZENvbG9yOiAncmdiYSgwLDAsMCwuMSknLFxuICAgICAgICB9LFxuICAgICAgXX0+XG4gICAgICA8QW5pbWF0ZWQuVmlld1xuICAgICAgICBzdHlsZT17e1xuICAgICAgICAgIG9wYWNpdHk6IHBhbi55LmludGVycG9sYXRlKHtcbiAgICAgICAgICAgIGlucHV0UmFuZ2U6IFtoZWlnaHQgLSBNT0RBTF9IRUlHSFQsIGhlaWdodF0sXG4gICAgICAgICAgICBvdXRwdXRSYW5nZTogWzEsIDAuNV0sXG4gICAgICAgICAgfSksXG4gICAgICAgICAgdHJhbnNmb3JtOiBbXG4gICAgICAgICAgICB7XG4gICAgICAgICAgICAgIHRyYW5zbGF0ZVk6IHBhbi55LFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICBdLFxuICAgICAgICB9fT5cbiAgICAgICAgICA8Qm94XG4gICAgICAgICAgICBiYWNrZ3JvdW5kQ29sb3I9XCJtYWluQmFja2dyb3VuZFwiXG4gICAgICAgICAgICBzdHlsZT17e1xuICAgICAgICAgICAgd2lkdGg6ICcxMDAlJyxcbiAgICAgICAgICAgIGhlaWdodDogTU9EQUxfSEVJR0hULFxuICAgICAgICAgICAgLy8gICBiYWNrZ3JvdW5kQ29sb3I6ICcjZmZmJyxcbiAgICAgICAgICAgIHNoYWRvd0NvbG9yOiAnI2NjYycsXG4gICAgICAgICAgICBzaGFkb3dPZmZzZXQ6IHsgaGVpZ2h0OiAtMSwgd2lkdGg6IDAgfSxcbiAgICAgICAgICAgIHNoYWRvd1JhZGl1czogMTUsXG4gICAgICAgICAgICBzaGFkb3dPcGFjaXR5OiAwLjEsXG4gICAgICAgICAgICB9fVxuICAgICAgICAgID5cbiAgICAgICAgICAgICAgPEJveFxuICAgICAgICAgICAgICAgIHN0eWxlPXt7XG4gICAgICAgICAgICAgICAgICAgIGZsZXg6IDEsXG4gICAgICAgICAgICAgICAgICAgIHBhZGRpbmdUb3A6IDI0LFxuICAgICAgICAgICAgICAgICAgICBhbGlnbkl0ZW1zOiAnY2VudGVyJyxcbiAgICAgICAgICAgICAgICAgICAganVzdGlmeUNvbnRlbnQ6ICdmbGV4LXN0YXJ0J1xuICAgICAgICAgICAgICB9fT5cbiAgICAgICAgICAgICAgICAgIDxUZXh0IHZhcmlhbnQ9XCJyYXRpbmdcIj5cbiAgICAgICAgICAgICAgICAgICAgICByYXRlIHlvdXIgcHJvZHVjdGl2aXR5IGxldmVsIGZvciB0aGlzIGV2ZW50XG4gICAgICAgICAgICAgICAgICA8L1RleHQ+XG5cbiAgICAgICAgICAgICAgICAgIDxCb3hcbiAgICAgICAgICAgICAgICAgICAgICBzdHlsZT17e1xuICAgICAgICAgICAgICAgICAgICAgIG1hcmdpblRvcDogMTYsXG4gICAgICAgICAgICAgICAgICAgICAgZmxleERpcmVjdGlvbjogJ3JvdycsXG4gICAgICAgICAgICAgICAgICAgIH19PlxuICAgICAgICAgICAgICAgICAgICAgIDxBbmltYXRlZC5WaWV3XG4gICAgICAgICAgICAgICAgICAgICAgb25MYXlvdXQ9eyhlKSA9PiB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgIGFuaW1hdGVkV2lkdGguY3VycmVudCA9IGUubmF0aXZlRXZlbnQubGF5b3V0LndpZHRoO1xuICAgICAgICAgICAgICAgICAgICAgIH19XG4gICAgICAgICAgICAgICAgICAgICAgc3R5bGU9e3sgZmxleERpcmVjdGlvbjogJ3JvdycgfX1cbiAgICAgICAgICAgICAgICAgICAgICB7Li4uc3RhclBhblJlc3BvbmRlci5wYW5IYW5kbGVyc30+XG4gICAgICAgICAgICAgICAgICAgICAge0FycmF5LmZyb20oeyBsZW5ndGg6IHByb3BzLm1heFN0YXJzIHx8IDUgfSkubWFwKChfLCBpKSA9PiB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICAgICAgICAgICAgICAgIDxTdGFyXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICBrZXk9e2l9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICBzaXplPXtwcm9wcy5zdGFyU2l6ZX1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGRpc3RhbmNlPXs4fVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgb2Zmc2V0PXtvZmZzZXQgLSBpfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAvPlxuICAgICAgICAgICAgICAgICAgICAgICAgICApO1xuICAgICAgICAgICAgICAgICAgICAgIH0pfVxuICAgICAgICAgICAgICAgICAgICAgIDwvQW5pbWF0ZWQuVmlldz5cbiAgICAgICAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICA8L0JveD5cbiAgICAgIDwvQW5pbWF0ZWQuVmlldz5cbiAgICA8L0FuaW1hdGVkLlZpZXc+XG4gIClcbn1cblxuZXhwb3J0IGRlZmF1bHQgUmF0aW5nQm90dG9tTW9kYWwiXX0=