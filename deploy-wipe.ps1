# OLEG DEPLOY SYSTEM v6.6.6 - FULL WIPE EDITION

$ErrorActionPreference = "Stop"

$SERVER = "bobpc@192.168.0.236"
$SERVER_PASS = "73731368"
$IMAGE_NAME = "project-oleg-oleg-bot:latest"
$TAR_FILE = "oleg-update.tar"
$BACKUP_DIR = "/home/bobpc/oleg/backups"
$DATA_DIR = "/home/bobpc/oleg/data"

function Write-Hack {
    param([string]$msg, [string]$color = "Green")
    $timestamp = Get-Date -Format "HH:mm:ss.fff"
    Write-Host "[$timestamp] " -NoNewline -ForegroundColor DarkGray
    Write-Host $msg -ForegroundColor $color
}

function Write-Matrix {
    param([int]$lines = 3)
    $chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%&*<>{}[]"
    for ($i = 0; $i -lt $lines; $i++) {
        $line = ""
        for ($j = 0; $j -lt 70; $j++) {
            $line += $chars[(Get-Random -Maximum $chars.Length)]
        }
        Write-Host $line -ForegroundColor DarkGreen
        Start-Sleep -Milliseconds 50
    }
}

function Write-Progress-Bar {
    param([string]$task, [int]$duration = 20)
    Write-Host "    $task " -NoNewline -ForegroundColor Yellow
    $width = 30
    for ($i = 0; $i -le $width; $i++) {
        $pct = [math]::Round(($i / $width) * 100)
        $filled = "#" * $i
        $empty = "-" * ($width - $i)
        Write-Host "`r    $task [$filled$empty] $pct%" -NoNewline -ForegroundColor Yellow
        Start-Sleep -Milliseconds $duration
    }
    Write-Host " OK" -ForegroundColor Green
}

# Clear and banner
Clear-Host
Write-Host ""
Write-Host "  =================================================================" -ForegroundColor Red
Write-Host "  ||                                                             ||" -ForegroundColor Red
Write-Host "  ||   ######  ##      ######  ######     #####   ######  ####   ||" -ForegroundColor White
Write-Host "  ||   ##  ##  ##      ##      ##        ##   ##  ##      ##  #  ||" -ForegroundColor White
Write-Host "  ||   ##  ##  ##      ####    ## ###    ##   ##  ####    ####   ||" -ForegroundColor White
Write-Host "  ||   ##  ##  ##      ##      ##  ##    ##   ##  ##      ##     ||" -ForegroundColor White
Write-Host "  ||   ######  ######  ######  ######     #####   ######  ##     ||" -ForegroundColor White
Write-Host "  ||                                                             ||" -ForegroundColor Red
Write-Host "  ||      FULL WIPE DEPLOYMENT v6.6.6 // OLEG [DANGER]          ||" -ForegroundColor Red
Write-Host "  =================================================================" -ForegroundColor Red
Write-Host ""

Start-Sleep -Milliseconds 500
Write-Matrix -lines 2

Write-Host ""
Write-Hack "WARNING: FULL DATABASE WIPE MODE ACTIVATED" "Red"
Write-Hack "This will DELETE ALL DATA including:" "Red"
Write-Hack "  - All user profiles and game stats" "DarkRed"
Write-Hack "  - All inventory items and coins" "DarkRed"
Write-Hack "  - All marriages and relationships" "DarkRed"
Write-Hack "  - All quests and achievements" "DarkRed"
Write-Hack "  - All RAG memory and chat history" "DarkRed"
Write-Host ""
Write-Host "  Press CTRL+C to abort or any key to continue..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
Write-Host ""

Write-Hack "Initializing FULL WIPE attack sequence..." "Yellow"
Write-Hack "Target acquired: $SERVER" "Red"
Write-Hack "Payload: $IMAGE_NAME" "Magenta"
Write-Host ""

if (Test-Path $TAR_FILE) {
    Write-Hack "Removing traces of previous operation..." "DarkYellow"
    Remove-Item $TAR_FILE -Force
}

Start-Sleep -Milliseconds 300

# PHASE 0
Write-Host ""
Write-Host "  -----------------------------------------------------------------" -ForegroundColor Yellow
Write-Host "   PHASE 0: CLEANUP OLD CONTAINERS" -ForegroundColor White
Write-Host "  -----------------------------------------------------------------" -ForegroundColor Yellow
Write-Host ""

Write-Hack "Stopping old container..." "Yellow"

$cleanupCmd = "echo '$SERVER_PASS' | sudo -S docker stop oleg 2>/dev/null; echo '$SERVER_PASS' | sudo -S docker rm -f oleg 2>/dev/null; echo '$SERVER_PASS' | sudo -S docker rmi -f $IMAGE_NAME 2>/dev/null; echo 'CLEANUP_COMPLETE'"

$cleanupResult = ssh $SERVER $cleanupCmd 2>&1
if ($cleanupResult -match "CLEANUP_COMPLETE") {
    Write-Hack "[OK] Old container removed" "Green"
} else {
    Write-Hack "[WARN] No old container found" "DarkYellow"
}

Write-Host ""
Start-Sleep -Milliseconds 500

# PHASE 0.5: FULL WIPE
Write-Host ""
Write-Host "  -----------------------------------------------------------------" -ForegroundColor Red
Write-Host "   PHASE 0.5: FULL DATABASE WIPE" -ForegroundColor White
Write-Host "  -----------------------------------------------------------------" -ForegroundColor Red
Write-Host ""

Write-Hack "Creating backup before wipe..." "Yellow"
$backupCmd = 'mkdir -p ' + $BACKUP_DIR + '; timestamp=$(date +%Y%m%d_%H%M%S); echo ''' + $SERVER_PASS + ''' | sudo -S cp ' + $DATA_DIR + '/oleg.db ' + $BACKUP_DIR + '/oleg_${timestamp}.db 2>/dev/null || echo ''NO_DB''; ls -1t ' + $BACKUP_DIR + '/oleg_*.db 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null; echo ''BACKUP_DONE'''
$backupResult = ssh $SERVER $backupCmd 2>&1
if ($backupResult -match "BACKUP_DONE") {
    Write-Hack "[OK] Backup created in $BACKUP_DIR" "Green"
} else {
    Write-Hack "[WARN] No database to backup" "DarkYellow"
}

Write-Hack "WIPING ALL DATA..." "Red"
$wipeCmd = "echo '$SERVER_PASS' | sudo -S rm -rf $DATA_DIR/oleg.db $DATA_DIR/chroma_db $DATA_DIR/*.json 2>/dev/null; echo 'WIPE_COMPLETE'"
$wipeResult = ssh $SERVER $wipeCmd 2>&1
if ($wipeResult -match "WIPE_COMPLETE") {
    Write-Hack "[OK] All data wiped from target system" "Green"
} else {
    Write-Hack "[ERROR] Wipe failed" "Red"
    throw "Wipe failed"
}

Write-Host ""
Start-Sleep -Milliseconds 500

# PHASE 1
Write-Host ""
Write-Host "  -----------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "   PHASE 1: COMPILING MALWARE PAYLOAD" -ForegroundColor White
Write-Host "  -----------------------------------------------------------------" -ForegroundColor Cyan
Write-Host ""

Write-Hack "Injecting shellcode into Docker container..." "Yellow"
Write-Hack "Platform target: linux/amd64 (x86_64)" "DarkCyan"
Write-Host ""
Write-Host "    --- DOCKER BUILD OUTPUT ---" -ForegroundColor DarkGray

# Run docker build with live output (disable error action temporarily)
$ErrorActionPreference = "Continue"
$env:DOCKER_BUILDKIT = "1"
docker build --progress=plain --platform linux/amd64 -t $IMAGE_NAME . 2>&1 | ForEach-Object {
    $line = "$_"
    Write-Host "    $line" -ForegroundColor DarkGray
}
$buildExitCode = $LASTEXITCODE
$ErrorActionPreference = "Stop"

Write-Host "    --- END BUILD OUTPUT ---" -ForegroundColor DarkGray
Write-Host ""

if ($buildExitCode -ne 0) { 
    Write-Hack "CRITICAL: Payload compilation failed!" "Red"
    throw "Build failed" 
}

Write-Host ""
Write-Hack "[OK] Payload compiled successfully" "Green"
Write-Hack "  Backdoor injected: aiogram-3.x rootkit" "DarkGreen"
Write-Hack "  Persistence module: SQLAlchemy ORM" "DarkGreen"
Write-Hack "  C2 Protocol: Telegram Bot API" "DarkGreen"

# PHASE 2
Write-Host ""
Write-Host "  -----------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "   PHASE 2: PACKAGING EXPLOIT FOR DELIVERY" -ForegroundColor White
Write-Host "  -----------------------------------------------------------------" -ForegroundColor Cyan
Write-Host ""

Write-Hack "Compressing payload into stealth archive..." "Yellow"
docker save -o $TAR_FILE $IMAGE_NAME
if ($LASTEXITCODE -ne 0) { throw "Save failed" }

$fileSize = [math]::Round((Get-Item $TAR_FILE).Length / 1MB, 2)
Write-Hack "[OK] Exploit packaged: $TAR_FILE - $fileSize MB" "Green"

# PHASE 3
Write-Host ""
Write-Host "  -----------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "   PHASE 3: ESTABLISHING SECURE TUNNEL TO TARGET" -ForegroundColor White
Write-Host "  -----------------------------------------------------------------" -ForegroundColor Cyan
Write-Host ""

Write-Hack "Scanning target for vulnerabilities..." "Yellow"
Write-Hack "Port 22 (SSH): OPEN - Exploitable" "Red"
Write-Hack "Initiating man-in-the-middle attack... (SCP transfer)" "Yellow"
Write-Host ""

ssh $SERVER "rm -f /home/bobpc/$TAR_FILE 2>/dev/null"

Write-Progress-Bar "Uploading payload" 15

scp -q $TAR_FILE "${SERVER}:/home/bobpc/" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Upload failed" }

Write-Host ""
Write-Hack "[OK] Payload delivered to target system" "Green"

# PHASE 4
Write-Host ""
Write-Host "  -----------------------------------------------------------------" -ForegroundColor Red
Write-Host "   PHASE 4: EXECUTING PAYLOAD ON TARGET SYSTEM" -ForegroundColor White
Write-Host "  -----------------------------------------------------------------" -ForegroundColor Red
Write-Host ""

Write-Matrix -lines 1

Write-Hack "Escalating privileges with sudo..." "Red"
Write-Hack "Loading malware into Docker daemon..." "Yellow"

$commands = "echo '$SERVER_PASS' | sudo -S docker load -i /home/bobpc/$TAR_FILE 2>&1 | grep -E 'Loaded|layer'; echo '---PHASE---'; echo '$SERVER_PASS' | sudo -S docker rm -f oleg 2>/dev/null; echo '$SERVER_PASS' | sudo -S docker run -d --name oleg --restart unless-stopped --label autoheal=true --env-file /home/bobpc/.env -v /home/bobpc/oleg/data:/app/data -v /home/bobpc/oleg/logs:/app/logs -p 9090:9090 $IMAGE_NAME; echo '---MIGRATE---'; sleep 2; echo '$SERVER_PASS' | sudo -S docker exec oleg alembic upgrade head 2>&1; rm -f /home/bobpc/$TAR_FILE; echo '---LOGS---'; sleep 3; echo '$SERVER_PASS' | sudo -S docker logs --tail 15 oleg 2>&1"

Write-Host ""
$output = ssh $SERVER $commands 2>&1
$lines = $output -split "`n"

$phase = "load"
foreach ($line in $lines) {
    if ($line -match "---PHASE---") {
        Write-Hack "Terminating previous instance..." "DarkYellow"
        Write-Hack "Spawning new malware process..." "Yellow"
        $phase = "run"
    }
    elseif ($line -match "---MIGRATE---") {
        Write-Hack "Creating fresh database tables..." "Magenta"
        $phase = "migrate"
    }
    elseif ($line -match "---LOGS---") {
        Write-Host ""
        Write-Hack "Verifying infection..." "Cyan"
        Write-Host ""
        $phase = "logs"
    }
    elseif ($line -match "Loaded image|layer") {
        Write-Host "    [INJECT] $line" -ForegroundColor DarkMagenta
    }
    elseif ($phase -eq "logs" -and $line.Trim()) {
        Write-Host "    [TARGET] $line" -ForegroundColor DarkCyan
    }
    elseif ($line -match "^[a-f0-9]{64}$") {
        Write-Hack "Container spawned: $($line.Substring(0,12))..." "Green"
    }
    elseif ($phase -eq "migrate" -and $line -match "Running|upgrade|revision|INFO") {
        Write-Host "    [MIGRATE] $line" -ForegroundColor DarkYellow
    }
}

Remove-Item $TAR_FILE -ErrorAction SilentlyContinue

# COMPLETE
Write-Host ""
Write-Matrix -lines 2
Write-Host ""
Write-Host "  =================================================================" -ForegroundColor Green
Write-Host "  ||                                                             ||" -ForegroundColor Green
Write-Host "  ||   #   #  ###   ###   ###  ###   ###   #   #                 ||" -ForegroundColor White
Write-Host "  ||   ## ##   #   #     #      #   #   #  ##  #                 ||" -ForegroundColor White
Write-Host "  ||   # # #   #    ##    ##    #   #   #  # # #                 ||" -ForegroundColor White
Write-Host "  ||   #   #   #      #     #   #   #   #  #  ##                 ||" -ForegroundColor White
Write-Host "  ||   #   #  ###  ###   ###   ###   ###   #   #                 ||" -ForegroundColor White
Write-Host "  ||                                                             ||" -ForegroundColor Green
Write-Host "  ||            ####   ###   #   #  ####   #     #####           ||" -ForegroundColor White
Write-Host "  ||           #      #   #  ## ##  #   #  #     #               ||" -ForegroundColor White
Write-Host "  ||           #      #   #  # # #  ####   #     ####            ||" -ForegroundColor White
Write-Host "  ||           #      #   #  #   #  #      #     #               ||" -ForegroundColor White
Write-Host "  ||            ####   ###   #   #  #      ####  #####           ||" -ForegroundColor White
Write-Host "  ||                                                             ||" -ForegroundColor Green
Write-Host "  ||                  [FULL WIPE COMPLETE]                       ||" -ForegroundColor Red
Write-Host "  =================================================================" -ForegroundColor Green
Write-Host ""
Write-Hack "Target system compromised with FRESH DATABASE" "Green"
Write-Hack "All previous data WIPED" "Red"
Write-Hack "Backdoor active: Telegram C2 channel" "Cyan"
Write-Hack "Backups: $BACKUP_DIR (last 5 kept)" "DarkCyan"
Write-Host ""
Write-Host "  [TIP] Watch target: ssh $SERVER `"sudo docker logs -f oleg`"" -ForegroundColor Cyan
Write-Host ""
