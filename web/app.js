function splitCsv(value) {
  return value.split(',').map(v => v.trim()).filter(Boolean);
}

function parseQuoteNumber(text) {
  if (!text) return null;
  const m = text.match(/([0-9][0-9,.]*)/);
  if (!m) return null;
  return Number(m[1].replace(/,/g, ''));
}

function groupKey(row) {
  return `${row.fiat_amount}__${row.payment_method}`;
}

function render(rows) {
  const results = document.getElementById('results');
  const summary = document.getElementById('summary');
  if (!rows.length) {
    results.innerHTML = '<p>无结果</p>';
    summary.innerHTML = '';
    return;
  }

  const ok = rows.filter(r => r.status === 'ok').length;
  summary.innerHTML = `<p>总记录：${rows.length}，成功：${ok}，失败：${rows.length - ok}</p>`;

  const groups = new Map();
  for (const row of rows) {
    const key = groupKey(row);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(row);
  }

  let html = '';
  for (const [key, groupRows] of groups) {
    const [amount, payment] = key.split('__');
    const best = Math.max(...groupRows.map(r => parseQuoteNumber(r.quote_text) ?? -Infinity));

    html += `<div class="group"><h3>金额 ${amount} / 支付方式 ${payment}</h3>`;
    html += '<table><thead><tr><th>渠道</th><th>报价</th><th>状态</th><th>备注</th></tr></thead><tbody>';

    for (const r of groupRows) {
      const value = parseQuoteNumber(r.quote_text);
      const bestClass = value !== null && value === best ? 'best' : '';
      const errClass = r.status === 'error' ? 'error' : '';
      html += `<tr class="${bestClass}"><td>${r.provider}</td><td>${r.quote_text || '-'}</td><td class="${errClass}">${r.status}</td><td>${r.note || ''}</td></tr>`;
    }
    html += '</tbody></table></div>';
  }

  results.innerHTML = html;
}

async function onSubmit(e) {
  e.preventDefault();
  const status = document.getElementById('status');
  const btn = document.getElementById('submitBtn');
  const form = e.target;

  const payload = {
    fiat: form.fiat.value.trim(),
    asset: form.asset.value.trim(),
    network: form.network.value.trim(),
    amounts: splitCsv(form.amounts.value),
    providers: splitCsv(form.providers.value),
    payment_methods: splitCsv(form.paymentMethods.value),
    allow_failures: form.allowFailures.checked,
  };

  status.textContent = '查询中...';
  btn.disabled = true;
  try {
    const resp = await fetch('/api/quotes', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.error || '请求失败');
    }
    render(data.rows || []);
    status.textContent = '查询完成';
  } catch (err) {
    status.textContent = `查询失败: ${err.message}`;
  } finally {
    btn.disabled = false;
  }
}

document.getElementById('quoteForm').addEventListener('submit', onSubmit);
