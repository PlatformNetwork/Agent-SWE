jest.mock('n8n-workflow', () => ({
	FROM_AI_AUTO_GENERATED_MARKER: '/*mock-marker*/',
}), { virtual: true });

import * as expressionModule from './expression';
import { expr, parseExpression, createFromAIExpression } from './expression';

describe('Workflow SDK expression public surface', () => {
	it('keeps expression utilities focused on string-based helpers', () => {
		const exported = expressionModule as Record<string, unknown>;

		expect(Object.prototype.hasOwnProperty.call(exported, 'serializeExpression')).toBe(false);
		expect(Object.prototype.hasOwnProperty.call(exported, 'parseExpression')).toBe(true);
		expect(Object.prototype.hasOwnProperty.call(exported, 'expr')).toBe(true);
	});

	it('keeps string-based expression utilities available', () => {
		const result = expr('{{ $json.userId }}');
		expect(result).toBe('={{ $json.userId }}');

		const parsed = parseExpression('={{ $json.userId }}');
		expect(parsed).toBe('$json.userId');
	});

	it('creates fromAI expressions with sanitized keys', () => {
		const expression = createFromAIExpression('user id');
		expect(expression).toContain("$fromAI('user_id')");
		const complex = createFromAIExpression('**weird##key', 'desc', 'string');
		expect(complex).toContain("$fromAI('weird_key'");
	});
});
