# AitoEarn Auto — 自动接单

每 30 分钟扫描 aitoearn 任务市场，自动接取符合条件的任务，推广类任务邮件通知。

## 工作原理

```
GitHub Actions (云端，24/7)
    │
    ├─ 每30分钟触发一次
    ├─ 扫描全部46个任务
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

- GitHub Actions 免费额度：公开仓库无限，私有仓库 2000 分钟/月（30 分钟/次 × 2 次/时 × 720 小时 ≈ 1440 分钟/月）
- 接取推广任务后，仍需登录 https://aitoearn.cn 完成发布
- 互动类任务接取后，MCP 可能支持直接提交，后续可扩展
