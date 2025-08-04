export class TemplateEngine {
  private template: string;

  constructor(template: string) {
    this.template = template;
  }

  render(variables: Record<string, string>): string {
    let result = this.template;

    for (const key in variables) {
      const value = variables[key];
      const regex = new RegExp(`{{\\s*${key}\\s*}}`, 'g');
      result = result.replace(regex, value);
    }

    return result;
  }

  renderMany(variables: Array<string>): string {
    let result = this.template;

    // comma separate fields
    let missingFields = '';
    for (const variable of variables) {
      missingFields += `${variable}, `;
    }

    const regex = new RegExp(`{{\\s*missingFields\\s*}}`, 'g');
    result = result.replace(regex, missingFields);

    return result;
  }
}

// Usage example:
const template = 'Hello, {{name}}! Today is {{dayOfWeek}}.';
const engine = new TemplateEngine(template);
const rendered = engine.render({ name: 'John', dayOfWeek: 'Monday' });

console.log(rendered); // Output: Hello, John! Today is Monday.
