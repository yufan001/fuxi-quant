import test from 'node:test';
import assert from 'node:assert/strict';

import { buildFactorRunPayload, isFactorStrategy, parsePoolCodes } from './factor-utils.js';

test('isFactorStrategy detects factor templates', () => {
  assert.equal(isFactorStrategy({ type: 'factor', params: {} }), true);
  assert.equal(isFactorStrategy({ type: 'tech', params: {} }), false);
  assert.equal(isFactorStrategy({ type: 'custom', params: { factor_configs: [{ key: 'pb', weight: 1 }] } }), true);
});

test('parsePoolCodes splits textarea input into trimmed codes', () => {
  assert.deepEqual(parsePoolCodes(' sh.600000, sz.000001\n\nsh.600519 '), ['sh.600000', 'sz.000001', 'sh.600519']);
  assert.deepEqual(parsePoolCodes('   '), []);
});

test('buildFactorRunPayload merges template params with form overrides', () => {
  const strategy = {
    id: 'factor_low_pb_momentum',
    type: 'factor',
    params: {
      factor_configs: [
        { key: 'pb', weight: 0.5 },
        { key: 'momentum_20', weight: 0.5 },
      ],
      top_n: 10,
      rebalance: 'monthly',
    },
  };

  const payload = buildFactorRunPayload(strategy, {
    start_date: '2024-01-01',
    end_date: '2024-03-31',
    capital: '200000',
    top_n: '15',
    rebalance: 'weekly',
    pool_codes: 'sh.600000, sz.000001',
  });

  assert.deepEqual(payload.factor_configs, strategy.params.factor_configs);
  assert.equal(payload.capital, 200000);
  assert.equal(payload.top_n, 15);
  assert.equal(payload.rebalance, 'weekly');
  assert.deepEqual(payload.pool_codes, ['sh.600000', 'sz.000001']);
});

test('buildFactorRunPayload includes inline script editing state for custom factor strategies', () => {
  const strategy = {
    id: 'custom_factor_script',
    type: 'factor',
    code: 'def score_stocks(histories, context):\n    return {}',
    params: {
      top_n: 5,
      rebalance: 'monthly',
    },
  };

  const payload = buildFactorRunPayload(strategy, {
    start_date: '2024-01-01',
    end_date: '2024-03-31',
    capital: '100000',
    top_n: '6',
    rebalance: 'weekly',
    pool_codes: '',
    script: 'def select_portfolio(histories, context):\n    return [{"code": "sh.600000", "weight": 1.0}]',
  });

  assert.equal(payload.strategy_id, 'custom_factor_script');
  assert.match(payload.script, /select_portfolio/);
  assert.equal(payload.top_n, 6);
});
