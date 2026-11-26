# Guarda as chaves do bot nos segredos do GitHub, sem que elas aparecam na tela.
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\configurar-segredos.ps1
# Pode rodar de novo quando quiser trocar alguma chave.

$ErrorActionPreference = 'Stop'
$Repo = 'artor410/bdo-patch-bot-ptbr'

$Segredos = @(
    @{ Nome = 'GEMINI_API_KEY'; Como = @(
        'Abra https://aistudio.google.com/apikey (ja deixei aberto no Chrome).',
        'Clique em "Create API key" (Criar chave de API) e copie a chave.') },
    @{ Nome = 'DISCORD_WEBHOOK_PATCH'; Como = @(
        'Discord > servidor BDO Patch PT-BR > Configuracoes do servidor > Integracoes > Webhooks.',
        'Abra o webhook "Patch" e clique em "Copiar URL do webhook".') },
    @{ Nome = 'DISCORD_WEBHOOK_EVENTOS'; Como = @(
        'Mesmo lugar: abra o webhook "Eventos" e clique em "Copiar URL do webhook".') },
    @{ Nome = 'DISCORD_WEBHOOK_LOJA'; Como = @(
        'Mesmo lugar: abra o webhook "Loja de Perolas" e clique em "Copiar URL do webhook".') },
    @{ Nome = 'DISCORD_WEBHOOK_LOGS'; Como = @(
        'Mesmo lugar: abra o webhook "Bot Logs" e clique em "Copiar URL do webhook".') }
)

Write-Host ''
Write-Host '=== Configurar segredos do bdo-patch-bot-ptbr ===' -ForegroundColor Cyan
Write-Host 'Para cada item: copie o valor, volte aqui, clique com o botao direito para colar e aperte Enter.'
Write-Host 'O valor nao aparece na tela. Deixe vazio e aperte Enter para pular um item.'

$jaExistem = (gh secret list --repo $Repo 2>$null) -join "`n"

$i = 0
foreach ($s in $Segredos) {
    $i++
    Write-Host ''
    $status = if ($jaExistem -match "(?m)^$($s.Nome)\s") { ' (ja configurado; Enter para manter)' } else { '' }
    Write-Host "[$i/$($Segredos.Count)] $($s.Nome)$status" -ForegroundColor Yellow
    foreach ($linha in $s.Como) { Write-Host "   $linha" }
    $seguro = Read-Host -AsSecureString '   Cole aqui'
    $valor = [System.Net.NetworkCredential]::new('', $seguro).Password.Trim()
    if (-not $valor) { Write-Host '   Pulado.' -ForegroundColor DarkGray; continue }
    if ($s.Nome -like 'DISCORD_*' -and $valor -notmatch '^https://(discord\.com|discordapp\.com)/api/webhooks/') {
        Write-Host '   Isso nao parece uma URL de webhook do Discord. Pulei; rode o script de novo para este item.' -ForegroundColor Red
        continue
    }
    $valor | gh secret set $s.Nome --repo $Repo
    Write-Host '   Guardado.' -ForegroundColor Green
}

Write-Host ''
Write-Host 'Pronto. Segredos atuais do repositorio:' -ForegroundColor Cyan
gh secret list --repo $Repo
