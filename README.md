# 多渠道法币买币报价脚本

`moonpay_usdt_quote.py` 现已支持多渠道聚合查询，核心覆盖你提的四点：

1. 多渠道：`moonpay`、`banxa`、`transit`（也支持 `demo` 本地演示数据）
2. 多金额：可同时查小额/大额（如 `50,100,200,1000`）
3. 支付方式：可指定 `visa`、`apple_pay` 等（按渠道可用性）
4. 币种与链：可指定 `--asset`（USDT/ETH/BTC）和 `--network`（ethereum/tron/bsc...）

输出为统一 Markdown 表格，也可追加写入 CSV。

## 快速开始

```bash
python moonpay_usdt_quote.py \
  --fiat USD \
  --asset USDT \
  --network ethereum \
  --providers moonpay,banxa,transit \
  --payment-methods visa,apple_pay \
  --amounts 50,100,200,1000 \
  --allow-failures
```

> `--allow-failures`：某个渠道失败时不中断，输出 `status=error` 的行，方便批量比较。

## 常用示例

### 1) 按你的场景：多渠道 + 多金额 + 支付方式 + 指定网络

```bash
python moonpay_usdt_quote.py \
  --fiat USD \
  --asset USDT \
  --network ethereum \
  --providers moonpay,banxa,transit \
  --payment-methods visa,apple_pay \
  --amounts 50,100,200 \
  --allow-failures
```

### 2) 只跑某一个渠道（例如 Banxa）

```bash
python moonpay_usdt_quote.py --providers banxa --fiat USD --asset BTC --amounts 100,500 --payment-methods visa
```

### 3) watch 模式持续抓取

```bash
python moonpay_usdt_quote.py --providers moonpay,banxa --amounts 100,200 --watch --iterations 5 --interval-sec 15 --allow-failures
```

### 4) 输出 CSV

```bash
python moonpay_usdt_quote.py --providers moonpay,banxa,transit --amounts 50,100,200 --csv quotes.csv --allow-failures
```

### 5) 本地演示（无网络时验证表格流程）

```bash
python moonpay_usdt_quote.py --providers demo --amounts 50,100,200
```

## 字段说明

- `Provider`: 渠道商
- `Amount`: 法币输入金额
- `Asset/Network`: 币种与链
- `Payment`: 支付方式（如 `visa`, `apple_pay`）
- `Quote`: 预估获得数量
- `Status`: `ok` 或 `error`
- `Note`: 错误详情或补充说明

## 注意

- 不同渠道 API 有地区限制、风控、参数校验差异，部分请求可能返回错误。
- `transit` 为聚合场景，公开 API 可能变更；脚本已做通用解析，但需按实际接口调整。
- 请遵守各网站服务条款与法律法规。
