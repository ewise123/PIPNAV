Add-Type -AssemblyName presentationCore
while ($true) {
    $file = Read-Host
    if ($file -eq "quit") { break }
    $p = New-Object System.Windows.Media.MediaPlayer
    $p.Open([Uri]$file)
    $p.Play()
}
