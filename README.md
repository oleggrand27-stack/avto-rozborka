# Авто під розбірку

Кожні 20 хвилин перевіряє нові оголошення на AUTO.RIA за моделями з `config.json`
і надсилає в Telegram ті, що схожі на авто під розбірку (запчастини, після ДТП, не на ходу).

Секрети (Settings → Secrets and variables → Actions → New repository secret):
- `RIA_API_KEY` — ключ з developers.ria.com
- `TELEGRAM_BOT_TOKEN` — токен від @BotFather
