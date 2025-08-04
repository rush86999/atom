import { DocumentProps, DocumentContext } from 'next/document';
interface MyDocumentProps extends DocumentProps {
    emotionStyleTags: JSX.Element[];
}
declare function MyDocument(props: MyDocumentProps): JSX.Element;
declare namespace MyDocument {
    var getInitialProps: (ctx: DocumentContext) => Promise<{
        emotionStyleTags: JSX.Element[];
        html: string;
        head?: Array<JSX.Element | null>;
        styles?: React.ReactElement[] | React.ReactFragment | JSX.Element;
    }>;
}
export default MyDocument;
