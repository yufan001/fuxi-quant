export function isFactorStrategy(strategy) {
  return strategy?.type === 'factor' || Array.isArray(strategy?.params?.factor_configs);
}

export function parsePoolCodes(value = '') {
  return value
    .split(/[\s,]+/)
    .map(item => item.trim())
    .filter(Boolean);
}

export function buildFactorRunPayload(strategy, formState) {
  const params = strategy?.params || {};
  return {
    strategy_id: strategy?.id || null,
    script: formState.script || strategy?.code || '',
    factor_configs: params.factor_configs || [],
    start_date: formState.start_date,
    end_date: formState.end_date,
    capital: parseFloat(formState.capital || '100000'),
    top_n: parseInt(formState.top_n || params.top_n || '10', 10),
    rebalance: formState.rebalance || params.rebalance || 'monthly',
    pool_codes: parsePoolCodes(formState.pool_codes || ''),
  };
}
