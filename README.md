# AitoEarn Auto — 自动接单

当前自动定时接单已暂停；仓库仅保留 GitHub Actions 手动触发入口。需要临时运行时，可到 Actions 页面手动触发 `workflow_dispatch`。

## 工作原理

```
GitHub Actions
    │
    ├─ 自动定时触发：已暂停
    ├─ 手动触发 workflow_dispatch 时扫描任务市场
    ├─ 按粉丝门槛自动接取
    └─ 推广类任务 → 邮件通知
```

## 接单规则

| 平台 | 粉丝 | 账号 |
|------|------|------|
| 抖音 | 153 | Crazy |
| 小红书 | 0 | 🐮 |
| B站 | 20 | 库牛 |
| 快手 | 4 | 快手用户... |

只接 `interaction`（互动）和 `fixed`（一口价）任务，CPE/CPM 跳过。

## 首次部署

### 1. 获取 QQ 邮箱授权码

打开 QQ 邮箱 → 设置 → 账户 → POP3/SMTP 服务 → 开启 → 生成授权码（16 位）

### 2. 设置 GitHub Secrets

仓库 Settings → Secrets and variables → Actions → New repository secret：

| Secret 名称 | 值 |
|-------------|-----|
| `AITOEARN_API_KEY` | 你的 aitoearn API Key（以 `ak_` 开头的那一串） |
| `QQ_EMAIL` | `1525764737@qq.com` |
| `QQ_SMTP_AUTH_CODE` | QQ 邮箱 SMTP 授权码（16 位） |

### 3. 推送代码到 GitHub

```bash
cd AitoEarn_auto
git init
git add .
git commit -m "feat: auto accept tasks + email notify"
git branch -M main
git remote add origin https://github.com/nzy0510/AitoEarn_auto.git
git push -u origin main
```

### 4. 验证

推送后到 GitHub Actions 标签页 → 手动触发 `workflow_dispatch` 跑一次，确认邮件能收到。

## 注意事项

- 自动定时触发已暂停，不会按固定间隔自动抓取或接取任务。
- 接取推广任务后，仍需登录 https://aitoearn.cn 完成发布。
- 互动类任务接取后，MCP 可能支持直接提交，后续可扩展。
