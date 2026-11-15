# BUILD_NOTES — bushilian 免费节点仓库复刻说明

## 文件清单

| 文件 | 说明 |
| --- | --- |
| `README.md` | 仓库首页：订阅地址、节点列表快照、使用说明 |
| `sub` | 生成的订阅文件：可用节点的 Base64 编码（无换行） |
| `fetch_nodes.py` | 抓取、改名、去重、测速、生成 `sub` 的脚本（Python 3，只用标准库） |
| `.github/workflows/update.yml` | GitHub Actions：每 6 小时自动跑脚本并更新 `sub` |

## 上游来源

- `https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub`（目前唯一的源）

## 改名规则（fetch_nodes.py 里的 clean_name）

- 保留节点显示名里的地区/国家部分（例如 香港、美国、日本东京、新西兰、英国）。
- 去掉原分享者的品牌词（V2CROSS.COM、mibei77.com、米贝节点分享、数据中心等）。
- 新名字 = `地区 bushilian`，例如 `香港 bushilian`；没有地区信息的就保留原名再加 ` bushilian`。
- 服务器、端口、密码、SNI 一律不动（那是原节点主人的，改了就连不上）。

## 去重规则

按（协议、服务器、端口、密码/UUID）去重，相同节点只保留第一次出现的。

## 测速规则

- 每个去重后的节点只测一次端点（host:port），5 秒超时，TCP 能连上算活。
- 在 GitHub Actions（无代理）上是直接 TCP 连接；在有 HTTP(S)_PROXY 的环境里改走 HTTP CONNECT 隧道（否则拦截式出口代理会让所有直连都“成功”，测速失去意义）。
- 主机名用 DNS-over-HTTPS（Cloudflare）解析，解析不到再回退到系统 DNS。
- 存活节点按延迟从低到高排序后写进 `sub`。

## 增加更多上游来源

编辑 `fetch_nodes.py` 顶部的 `SOURCES` 列表，把新的订阅地址加进去就行：

```python
SOURCES = [
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
    "https://example.com/另一个免费订阅",
]
```

每个来源可以是纯文本节点列表，也可以是 Base64 编码的订阅，脚本都会处理。

## 自动更新怎么跑

`.github/workflows/update.yml` 每 6 小时（cron `0 */6 * * *`）跑一次，也支持手动触发（workflow_dispatch）：
checkout → Python 3.12 → `python3 fetch_nodes.py` → 只有 `sub` 变了才 commit + push。

## 本次生成结果（2026-11-15）

- 上游抓到 11 个节点，去重后 10 个，TCP 存活 9 个，死亡 1 个（`bl1.nexfile.net:4444`）。
- 生成的 `sub` 共 9 个节点：美国、英国、香港 ×2、日本东京、新西兰 ×4。

## 注意事项

- 不要把任何 Token、密码写进仓库文件；Actions 靠仓库自带的 `GITHUB_TOKEN` 推送，不需要额外配置。
- 订阅地址（推上去之后）：`https://raw.githubusercontent.com/bushilian/bushilian/main/sub`
