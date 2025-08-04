export declare const getListPage: (filePath: string) => Promise<{
    frontmatter: any;
    content: any;
    mdxContent: any;
}>;
export declare const getSinglePage: (folder: string) => {
    frontmatter: any;
    slug: any;
    content: string;
}[];
export declare const getRegularPage: (slug: any) => Promise<{
    frontmatter: any;
    content: any;
    mdxContent: any;
}>;
