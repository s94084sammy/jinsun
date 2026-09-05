# 第三方與既有程式揭露

## Hermes Agent

- 來源：Nous Research，<https://github.com/nousresearch/hermes-agent>
- 授權：MIT（見 LICENSE.hermes-agent）
- 這份打包使用：v0.21.0（2026-08-31），上游提交 63279301bcbdc185c1b07b98a9312eb0c862f26d
- Docker 映像：`nousresearch/hermes-agent:latest`
- 映像摘要：`sha256:76d5d17a201bb623268c02d43e397925e8f0127eb29b2e00fc48632d74945b05`
- 使用方式：官方 Docker 映像，外加金孫的減法設定、長輩技能、自製報名表、LINE 一次一則與排程腳本。
- 這個倉庫只放金孫這份家用改裝，不是把其它工作環境改名交出去。

## OpenAI 的 GPT

- 模型可走 ChatGPT 或 Codex 訂閱。OpenAI 是 BUILDMODE GEN-AI HACKATHON 2026 的贊助商之一。
- 授權走 ChatGPT 或 Codex 訂閱的瀏覽器／裝置碼登入，對應 Hermes 的 ChatGPT or Codex Subscription。
- 不使用 OpenAI API 金鑰，不使用 Gemini。

## xAI 的 Grok

- 預設走 xAI 裝置碼登入（`xai-oauth`）。也可以改走 ChatGPT 或 Codex 訂閱。
- 不使用 xAI API 金鑰。

## LINE Messaging API

- 官方 Messaging API。頻道由使用者自己申請。
- 本倉庫不附頻道密鑰。沒有 LINE 也能在容器內測技能與排程。

## 台灣開放資料

- 中央氣象署開放資料、交通部 TDX、環境部環境資料開放平臺、台北市中山區公所公開活動表。
- 金鑰由使用者自己申請。沒填就白話說明查不了，不要編造。

## 自製報名表

- Demo 寫入的是家裡這台電腦上的 SQLite 表。
- 不是公所、學校、醫院或 Google 表單的正式後端。
