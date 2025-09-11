# Enhanced BT50 data extraction with timestamps and analysis columns
$matches = Select-String -Path debug_latest.log -Pattern "(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}).*BT50 RAW: \[(\d+),(\d+),(\d+)\]"
Write-Host "Processing $($matches.Count) BT50 data points..."

$csvLines = @()
$csvLines += "Sample,Timestamp_Seconds,X_Raw,Y_Raw,Z_Raw,X_Corrected,Y_Corrected,Z_Corrected,Magnitude,Above_Threshold"

$BASELINE_X = 2089
$BASELINE_Y = 0  
$BASELINE_Z = 0
$THRESHOLD = 150
$startTime = $null

for ($i = 0; $i -lt $matches.Count; $i++) {
    $match = $matches[$i]
    if ($match.Line -match "(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}).*BT50 RAW: \[(\d+),(\d+),(\d+)\]") {
        $timeStr = $matches2.Groups[1].Value
        $xRaw = [int]$matches2.Groups[2].Value
        $yRaw = [int]$matches2.Groups[3].Value
        $zRaw = [int]$matches2.Groups[4].Value
        
        # Calculate relative timestamp in seconds
        try {
            $timestamp = [DateTime]::ParseExact($timeStr, "yyyy-MM-dd HH:mm:ss,fff", $null)
            if ($startTime -eq $null) { $startTime = $timestamp }
            $relativeSeconds = [Math]::Round(($timestamp - $startTime).TotalSeconds, 3)
        } catch {
            $relativeSeconds = $i * 0.02  # Estimate ~50Hz sampling
        }
        
        # Calculate corrected values
        $xCorrected = $xRaw - $BASELINE_X
        $yCorrected = $yRaw - $BASELINE_Y
        $zCorrected = $zRaw - $BASELINE_Z
        
        # Calculate magnitude
        $magnitude = [Math]::Round([Math]::Sqrt($xCorrected*$xCorrected + $yCorrected*$yCorrected + $zCorrected*$zCorrected), 1)
        
        # Check if above threshold
        $aboveThreshold = if ($magnitude -gt $THRESHOLD) { 1 } else { 0 }
        
        $csvLines += "$($i+1),$relativeSeconds,$xRaw,$yRaw,$zRaw,$xCorrected,$yCorrected,$zCorrected,$magnitude,$aboveThreshold"
    }
}

# Write enhanced CSV
$csvLines | Out-File -FilePath "bt50_enhanced_data.csv" -Encoding UTF8
Write-Host "Created bt50_enhanced_data.csv with $($csvLines.Count - 1) data points"
Write-Host "Columns: Sample, Timestamp_Seconds, X_Raw, Y_Raw, Z_Raw, X_Corrected, Y_Corrected, Z_Corrected, Magnitude, Above_Threshold"