declare const palette: {
    offBlack: string;
    purpleLight: string;
    purple: string;
    purplePrimary: string;
    pinkPrimary: string;
    transparentPurple: string;
    purpleDark: string;
    red: string;
    lightGreen: string;
    greenPrimary: string;
    darkGreen: string;
    textBlack: string;
    black: string;
    white: string;
    darkGray: string;
    lightGray: string;
    FACEBOOK: string;
    TWITTER: string;
    PRIMARY: string;
    INFO: string;
    ERROR: string;
    WARNING: string;
    SUCCESS: string;
    INPUT: string;
    PLACEHOLDER: string;
    NAVBAR: string;
    BLOCK: string;
    shadowColor: string;
    ICON: string;
    grey: string;
    MUTED: string;
    WARN: string;
    regularCardBackground: string;
    transparent: string;
    black60: string;
    carbs: string;
    protein: string;
    fat: string;
    link: string;
    backgroundLink: string;
    disabled: string;
};
declare const theme: {
    colors: {
        mainBackground: string;
        mainForeground: string;
        regularCardBackground: string;
        regularCardText: string;
        lightRegularCardBackground: string;
        lightRegularCardText: string;
        lightRegularCardIcon: string;
        darkCardBackground: string;
        darkCardText: string;
        secondaryCardBackground: string;
        secondaryCardText: string;
        toastBreakBackground: string;
        primaryCardBackground: string;
        primaryCardText: string;
        buttonIconBackground: string;
        iconColor: string;
        link: string;
        backgroundLink: string;
        greyLink: string;
        buttonLink: string;
        redLink: string;
        buttonText: string;
        primaryButtonText: string;
        followingButtonText: string;
        body: string;
        commentPost: string;
        shadowColor: string;
        transparent: string;
    };
    borderRadii: {
        cardRadius: any;
    };
    spacing: {
        none: number;
        xxs: number;
        xs: number;
        s: number;
        m: number;
        l: number;
        xl: number;
        xxl: number;
    };
    breakpoints: {
        phone: number;
        tablet: number;
    };
    textVariants: {
        backgroundText: {
            fontWeight: string;
            fontSize: number;
            textAlign: string;
        };
        header: {
            fontWeight: string;
            fontSize: number;
            lineHeight: number;
            textAlign: string;
        };
        subheader: {
            fontWeight: string;
            fontSize: number;
            lineHeight: number;
        };
        subheaderNormal: {
            fontWeight: string;
            fontSize: number;
            lineHeight: number;
        };
        rating: {
            textTransform: string;
            fontWeight: string;
            fontSize: number;
        };
        subheaderBold: {
            fontWeight: string;
            fontSize: number;
            lineHeight: number;
        };
        subTitle: {
            fontWeight: string;
            fontSize: number;
            lineHeight: number;
            textTransform: string;
        };
        primaryHeader: {
            fontWeight: string;
            fontSize: number;
            lineHeight: number;
            textAlign: string;
        };
        primarySecondaryHeader: {
            fontWeight: string;
            fontSize: number;
            lineHeight: number;
        };
        secondaryHeaderLink: {
            fontWeight: string;
            fontSize: number;
            lineHeight: number;
            color: string;
        };
        lightRegularHeader: {
            fontWeight: string;
            fontSize: number;
            lineHeight: number;
            textAlign: string;
        };
        lightRegularSubheader: {
            fontWeight: string;
            fontSize: number;
            lineHeight: number;
        };
        body: {
            fontSize: number;
            lineHeight: number;
        };
        bodyBold: {
            fontWeight: string;
            fontSize: number;
        };
        google: {
            fontSize: number;
            lineHeight: number;
            fontWeight: string;
        };
        apple: {
            fontSize: number;
            lineHeight: number;
            fontWeight: string;
        };
        comment: {
            fontSize: number;
            lineHeight: number;
        };
        username: {
            fontSize: number;
            lineHeight: number;
            fontWeight: string;
        };
        caption: {
            fontSize: number;
            lineHeight: number;
        };
        toDoButton: {
            fontSize: number;
            lineHeight: number;
        };
        cardCaption: {
            fontSize: number;
            lineHeight: number;
        };
        cardTitle: {
            fontSize: number;
            lineHeight: number;
        };
        cardLink: {
            fontSize: number;
            lineHeight: number;
            color: string;
        };
        greyComment: {
            fontSize: number;
            lineHeight: number;
        };
        optionHeader: {
            fontSize: number;
            lineHeight: number;
            padding: string;
        };
        primaryOptionHeader: {
            fontSize: number;
            lineHeight: number;
        };
        menuHeader: {
            fontSize: number;
        };
        buttonLink: {
            fontSize: number;
            color: string;
        };
        greyLink: {
            fontSize: number;
            lineHeight: number;
        };
        redLink: {
            fontSize: number;
            lineHeight: number;
        };
        buttonText: {
            fontSize: number;
            lineHeight: number;
        };
        primaryButtonText: {
            fontSize: number;
            lineHeight: number;
        };
        followingButtonText: {
            fontSize: number;
            lineHeight: number;
        };
        commentPost: {
            fontSize: number;
            lineHeight: number;
        };
    };
    cardVariants: {
        defaults: {
            marginVertical: {
                phone: string;
                tablet: string;
            };
            padding: {
                phone: string;
                tablet: string;
            };
            borderRadius: {
                phone: string;
                tablet: string;
            };
            borderWidth: any;
            borderColor: string;
            justifyContent: string;
            alignItems: string;
        };
        regular: {
            backgroundColor: string;
        };
        elevated: {
            borderWidth: number;
            shadowColor: string;
            shadowOpacity: any;
            shadowOffset: {
                width: number;
                height: number;
            };
            shadowRadius: any;
            elevation: any;
        };
        primaryElevated: {
            borderWidth: number;
            backgroundColor: string;
            shadowColor: string;
            shadowOpacity: any;
            shadowOffset: {
                width: number;
                height: number;
            };
            shadowRadius: any;
            elevation: any;
        };
        miniElevated: {
            borderWidth: number;
            shadowColor: string;
            shadowOpacity: any;
            shadowOffset: {
                width: number;
                height: number;
            };
            shadowRadius: any;
            elevation: any;
        };
    };
};
export type Theme = typeof theme;
declare const darkTheme: Theme;
export { darkTheme, theme, palette };
