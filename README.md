# BDO Patch PT-BR

Bot de Discord que acompanha o Black Desert e posta, em português:

| Canal | O que sai |
|---|---|
| `#bdo-patch` | 🧪 **Global Lab** (servidor de testes, traduzido do coreano), 👀 **Preview** do update SA (via SEA, ~4h antes), 🟢 **Update SA** (só as diferenças em relação ao preview, ou "igual ao preview") e 🔧 hotfixes |
| `#eventos` | 🎉 eventos novos do SA (o que fazer, recompensas, contagem "acaba em…") e ⏳ lembrete 24h antes de acabar |
| `#loja-de-perolas` | 💎 novidades da Loja de Pérolas do SA |
| `#bot-logs` | ⚠️ problemas, 📚 termos novos para aprovar, testes |

Patches e eventos vêm com um **áudio** curto, para quem prefere ouvir.

## Como funciona

- Roda de graça no **GitHub Actions**, sem PC ligado: de hora em hora, e a cada 30 min nos horários em que cada
  fonte costuma publicar (`bdo_bot/fontes.py`).
- Resumo e tradução pelo **Gemini** (plano gratuito). Áudio pelo **edge-tts** (reserva: TTS do Gemini).
- **Glossário** `data/glossario.json`: nomes oficiais KR / EN / PT-BR usados em toda tradução. Nomes de itens
  vêm da base do [arsha.io](https://api.arsha.io). Quando o update SA sai, o bot compara com o SEA e o KR e
  abre um **pull request** com termos novos; nada entra no glossário sem você aprovar (Merge).
- `data/estado.json`: o que já foi postado (o bot atualiza sozinho).

## Comandos manuais

Em **Actions → bot → Run workflow**:

- `testar-fonte` + fonte: reposta o post mais recente daquela fonte no `#bot-logs` (bom para ver a qualidade).
- `testar-vozes`: manda um áudio de cada voz no `#bot-logs`. Para escolher, crie em
  **Settings → Secrets and variables → Actions → Variables** a variável `TTS_VOZ`
  (`pt-BR-FranciscaNeural` ou `pt-BR-AntonioNeural`).
- `glossario-inicial`: compara os últimos 4 patches SA/SEA/KR e abre um PR com os termos encontrados.

## Configuração

`scripts/configurar-segredos.ps1` pede, sem mostrar na tela, a chave do Gemini e as URLs dos webhooks.
Para postar também em outro servidor (ex.: o da guild), coloque **mais de uma URL** no mesmo segredo, uma por linha.

Opcional: `DISCORD_BOT_TOKEN` (de um bot do Discord no servidor) faz as mensagens dos canais de anúncio serem
publicadas automaticamente para quem **segue** o canal. Sem ele, quem segue não recebe as mensagens de webhook.

## Desenvolvimento

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m pytest
```
