param(
    [string[]]$PreloadFiles = @()
)

Add-Type -AssemblyName presentationCore

$players = @{}
$currentPlayer = $null

function Get-Player {
    param(
        [Parameter(Mandatory = $true)]
        [string]$File
    )

    if (-not $players.ContainsKey($File)) {
        $player = New-Object System.Windows.Media.MediaPlayer
        $player.Open([Uri]$File)

        for ($i = 0; $i -lt 100 -and -not $player.NaturalDuration.HasTimeSpan; $i++) {
            Start-Sleep -Milliseconds 10
        }

        $players[$File] = $player
    }

    return $players[$File]
}

try {
    foreach ($file in $PreloadFiles) {
        if ([string]::IsNullOrWhiteSpace($file)) {
            continue
        }
        $null = Get-Player -File $file
    }

    while ($true) {
        $file = Read-Host
        if ($null -eq $file -or $file -eq "quit") {
            break
        }
        if ([string]::IsNullOrWhiteSpace($file)) {
            continue
        }

        if ($currentPlayer -ne $null) {
            $currentPlayer.Stop()
        }

        $player = Get-Player -File $file
        $player.Position = [TimeSpan]::Zero
        $player.Play()
        $currentPlayer = $player
    }
}
finally {
    foreach ($player in $players.Values) {
        $player.Stop()
        $player.Close()
    }
}
