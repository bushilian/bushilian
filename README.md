# Free-servers · 免费节点

免费节点订阅，节点来自公开的免费分享渠道，定时测速、每 6 小时更新一次。

## 订阅地址

把下面这个地址复制到客户端里添加订阅：

```
https://raw.githubusercontent.com/bushilian/bushilian/main/sub
```

## 节点列表

下面是本次更新后的可用节点（快照，最多展示 20 个；订阅里永远是最新的）：

```
vless://a88d4614-2134-404c-9479-6aba1ca9cdfd@162.35.38.156:443?&security=reality&flow=xtls-rprx-vision&pbk=UkUbCx7k5ykWTJTr1jqCOxns6TwvTAbfR0JvJzuALjM&sid=a62b22480f962a1d&fp=firefox&sni=2499dbt.us12.h1clayd.click&type=tcp&headerType=none&host=2499dbt.us12.h1clayd.click&path=%2F#%E7%BE%8E%E5%9B%BD%20bushilian
vless://c16e8cdb-65dd-4049-bc65-14c051b8a6c6@2.26.251.236:443?encryption=none&flow=xtls-rprx-vision&fp=chrome&headerType=none&pbk=1iVMMhJZgXHRY7tRlR-1kypF0YeaBcB7EjcfHRsYZX4&security=reality&sid=4ff31b18d1bd8227&sni=mental-deprivation.ru&type=tcp#%E8%8B%B1%E5%9B%BD%20bushilian
trojan://d7563108-615c-4338-a7bd-77f359869a4a@sclass-b1.catcat321.com:20027?security=tls&sni=hk.catxstar.com#%E9%A6%99%E6%B8%AF%20bushilian
ss://YWVzLTI1Ni1nY206WlJwZ2FCZUd4dEVOSVhndmhwa1pCS3o5R25XUlMyZFljeDlPK2EyaXdOND0=@202.50.253.18:19999#%E6%96%B0%E8%A5%BF%E5%85%B0%20bushilian
ss://YWVzLTI1Ni1nY206WlJwZ2FCZUd4dEVOSVhndmhwa1pCS3o5R25XUlMyZFljeDlPK2EyaXdOND0=@202.50.253.90:19999#%E6%96%B0%E8%A5%BF%E5%85%B0%20bushilian
trojan://d7563108-615c-4338-a7bd-77f359869a4a@sclass-b1.catcat321.com:20028?security=tls&sni=hk.catxstar.com#%E9%A6%99%E6%B8%AF%20bushilian
vless://57beeeb0-03fc-4fc9-94da-7604488a7134@zfapi.zalolink.com:54528?security=reality&type=raw&packetEncoding=xudp&sni=www.apple.com&fp=ios&flow=xtls-rprx-vision&sid=54cca3c1c1c7&pbk=7GvJVbR6BRhtrc8-rcZvB8qTFUF1LPeM_MmoZ04mBxo#%E6%97%A5%E6%9C%AC%E4%B8%9C%E4%BA%AC%20bushilian
ss://YWVzLTI1Ni1nY206WlJwZ2FCZUd4dEVOSVhndmhwa1pCS3o5R25XUlMyZFljeDlPK2EyaXdOND0=@202.50.253.45:19999#%E6%96%B0%E8%A5%BF%E5%85%B0%20bushilian
ss://YWVzLTI1Ni1nY206WlJwZ2FCZUd4dEVOSVhndmhwa1pCS3o5R25XUlMyZFljeDlPK2EyaXdOND0=@202.50.253.27:19999#%E6%96%B0%E8%A5%BF%E5%85%B0%20bushilian
```

## 怎么用

- **Shadowrocket（iOS）**：打开小火箭 → 添加订阅 → 粘贴上面的订阅地址 → 更新订阅，选一个延迟低的节点连接。
- **Clash / Mihomo（Windows / macOS / Android）**：订阅地址需要先转成 Clash 配置（可用订阅转换工具），或直接把上面节点列表里的链接逐个导入。
- **v2rayNG（Android）**：右上角 → 添加订阅 → 粘贴订阅地址 → 更新订阅。

连不上时先点“更新订阅”拉最新节点，再换个节点试试；免费共享节点随时可能失效。

## 说明

- 节点是从公开的免费分享渠道聚合来的，不是 bushilian 自己搭建的服务器；服务器、密码、SNI 都是原分享者的，只改了显示名字。
- 免费节点是成千上万人共用的，速度不稳、随时失效，节点运营方能看到你的流量，不要用它登录账号、付款。
- 本仓库每 6 小时自动拉取上游、测速、更新订阅（见 `.github/workflows/update.yml`）。
