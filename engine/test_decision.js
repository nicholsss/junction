/* Shared decision-contract tests for the browser validator.
 * Run: node --test engine/test_decision.js
 * Same cases as engine/test_decision.py. Nothing is signed or posted.
 */
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const contract = require('./decision.js');
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'decision-contract-cases.json'), 'utf8'));

function codes(errors) {
  return errors.map((error) => error.code).sort();
}

test('every shared case matches the expectation', () => {
  for (const item of cases.cases) {
    const input = item.input;
    const errors = contract.validateDecision(
      input.action, input.reason, input.refusalPositions,
      input.findingPositions, input.acknowledgedUnknowns, cases.contract);
    assert.deepStrictEqual(codes(errors), [...item.errors].sort(), item.name);
    assert.strictEqual(errors.length === 0, item.valid, item.name);
  }
});

test('every error carries a message', () => {
  for (const item of cases.cases) {
    const input = item.input;
    const errors = contract.validateDecision(
      input.action, input.reason, input.refusalPositions,
      input.findingPositions, input.acknowledgedUnknowns, cases.contract);
    for (const error of errors) assert.ok(error.message.trim(), item.name);
  }
});

test('legitimate domain brackets are not placeholders', () => {
  assert.strictEqual(contract.isPlaceholder('The [FromMetadata] scenario is separate.'), false);
  assert.strictEqual(contract.isPlaceholder('[your answer]'), true);
  assert.strictEqual(contract.isPlaceholder('[anything]'), true);
});
