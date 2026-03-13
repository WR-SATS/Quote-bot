# MoonPay USDT 自动报价脚本

脚本 `moonpay_usdt_quote.py` 会自动打开 MoonPay 买币页面，输入一个或多个法币金额，并把报价以 **Markdown 表格** 输出到终端；也可选写入 CSV。

## 安装

```bash
pip install playwright
playwright install chromium
```

## 用法

### 1) 查询单个金额

```bash
python moonpay_usdt_quote.py --fiat HKD --crypto USDT --amount 1000
```

### 2) 一次查询多个金额（自动输出表格）

```bash
python moonpay_usdt_quote.py --fiat HKD --crypto USDT --amounts 500,1000,2000
```

### 3) 持续自动获取（每 20 秒一次，共 3 轮）

```bash
python moonpay_usdt_quote.py --fiat HKD --crypto USDT --amounts 1000,2000 --watch --iterations 3 --interval-sec 20
```

### 4) 同时保存为 CSV

```bash
python moonpay_usdt_quote.py --fiat HKD --crypto USDT --amounts 500,1000 --csv quotes.csv
```

## 输出示例

```markdown
| Timestamp (UTC) | Fiat | Fiat Amount | Crypto | Quote |
|---|---|---:|---|---|
| 2026-01-01T00:00:00+00:00 | HKD | 1000 | USDT | 116 USDT |
```

## 注意

- 这是前端自动化方案，页面结构变化会导致选择器失效，需要维护。
- MoonPay 可能有地区限制、风控、验证码等机制，自动化可能失败。
- 请遵守目标网站服务条款和当地法律法规。
