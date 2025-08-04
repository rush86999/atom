export declare class TemplateEngine {
    private template;
    constructor(template: string);
    render(variables: Record<string, string>): string;
    renderMany(variables: Array<string>): string;
}
