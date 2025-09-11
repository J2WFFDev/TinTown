# Extract BT50 sensor data and create CSV
$pattern = 'BT50 RAW: \[(\d+),(\d+),(\d+)\]'
$timePattern = '(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})'
$matches = Select-String -Path debug_latest.log -Pattern "$timePattern.*$pattern"

Write-Host "Found $($matches.Count) BT50 data points"

# Create CSV content
$csvContent = @()
$csvContent += "Timestamp_Seconds,X_Raw,Y_Raw,Z_Raw,X_Corrected,Y_Corrected,Z_Corrected,Magnitude"

$BASELINE_X = 2089
$BASELINE_Y = 0
$BASELINE_Z = 0
$startTime = $null

foreach ($match in $matches) {
    if ($match.Line -match "$timePattern.*BT50 RAW: \[(\d+),(\d+),(\d+)\]") {
        $timeStr = $matches.Matches[0].Groups[1].Value
        $xRaw = [int]$matches.Matches[0].Groups[2].Value
        $yRaw = [int]$matches.Matches[0].Groups[3].Value
        $zRaw = [int]$matches.Matches[0].Groups[4].Value
        
        # Parse timestamp
        $timestamp = [DateTime]::ParseExact($timeStr, "yyyy-MM-dd HH:mm:ss,fff", $null)
        
        if ($startTime -eq $null) {
            $startTime = $timestamp
        }
        
        $relativeSeconds = ($timestamp - $startTime).TotalSeconds
        
        # Calculate corrected values
        $xCorrected = $xRaw - $BASELINE_X
        $yCorrected = $yRaw - $BASELINE_Y
        $zCorrected = $zRaw - $BASELINE_Z
        
        # Calculate magnitude
        $magnitude = [Math]::Round([Math]::Sqrt($xCorrected*$xCorrected + $yCorrected*$yCorrected + $zCorrected*$zCorrected), 1)
        
        $csvContent += "$relativeSeconds,$xRaw,$yRaw,$zRaw,$xCorrected,$yCorrected,$zCorrected,$magnitude"
    }
}

# Write to CSV file
$csvContent | Out-File -FilePath "bt50_sensor_data.csv" -Encoding UTF8
Write-Host "Created bt50_sensor_data.csv with $($csvContent.Count - 1) data points"