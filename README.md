# 多渠道法币买币报价脚本

`moonpay_usdt_quote.py` 现已支持多渠道聚合查询，核心覆盖你提的四点：

1. 多渠道：`moonpay`、`banxa`、`transit`（也支持 `demo` 本地演示数据）
2. 多金额：可同时查小额/大额（如 `50,100,200,1000`）
3. 支付方式：可指定 `visa`、`apple_pay` 等（按渠道可用性）
4. 币种与链：可指定 `--asset`（USDT/ETH/BTC）和 `--network`（ethereum/tron/bsc...）

输出为统一 Markdown 表格，也可追加写入 CSV。

## 前端网页版（可视化比较）

你可以直接启动网页，在页面里输入金额、支付方式、渠道来比较报价：

```bash
python web_quote_server.py
```

打开浏览器访问：

```text
http://127.0.0.1:8000
```

网页功能：

- 表单输入：法币 / 币种 / 网络 / 金额 / 支付方式 / 渠道
- 一键查询后按“金额 + 支付方式”分组展示
- 自动高亮每组中的最佳报价（绿色）
- 渠道失败不会中断（会显示 `status=error`）

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

## PR 冲突一键处理（新增）

如果你在 GitHub 上看到 "This branch has conflicts"，先尝试 PR 页面上的 **Update branch**。

如果 Update branch 不可用，再在本地/云端执行：

```bash
scripts/resolve_pr_conflicts.sh main work
# 或自动偏向目标分支版本（减少手工冲突）
scripts/resolve_pr_conflicts.sh main work --prefer theirs
```

脚本会自动：

1. `fetch` 远端分支
2. 切到你的功能分支
3. `pull --rebase` 最新功能分支
4. `rebase` 到目标分支（如 `main`）
5. 若冲突则列出冲突文件和冲突标记，提示下一步命令
6. 无冲突时提示 `push --force-with-lease`

> 你也可以省略第二个参数，默认使用当前分支：
>
> ```bash
> scripts/resolve_pr_conflicts.sh main
> ```

## 没有本地仓库怎么解决 PR 冲突？

如果你没有本地环境，也可以直接在 GitHub 网页端处理：

1. 打开你的 PR 页面，点击 **Resolve conflicts**。
2. 在网页编辑器里保留需要的代码（删除 `<<<<<<<`, `=======`, `>>>>>>>` 标记）。
3. 点击 **Mark as resolved**，并对所有冲突文件重复。
4. 点击 **Commit merge** 完成冲突修复提交。
5. 回到 PR 页面确认冲突已消失并可正常 Merge。

如果按钮不可用（例如冲突太复杂），有两个无本地替代方案：

- 用 **GitHub Codespaces** 临时开一个云端开发环境，再运行：
  ```bash
  scripts/resolve_pr_conflicts.sh main <你的分支名>
  ```
- 或让有仓库权限的协作者在本地/CI代为执行 rebase 并 push。
