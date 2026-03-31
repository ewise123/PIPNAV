Add-Type -AssemblyName presentationCore
$player = New-Object System.Windows.Media.MediaPlayer
while ($true) {
    $file = Read-Host
    if ($file -eq "quit") { break }
    $player.Open([Uri]$file)
    $player.Play()
}
