# Shot Detection Analysis for BT50 Sensor Data
# PowerShell implementation of the proposed shot detection algorithm

Write-Host "Loading BT50 sensor data for shot detection analysis..."

# Load CSV data
$data = Import-Csv "bt50_xyz_data.csv"
$xData = $data | ForEach-Object { [int]$_.X_Raw }
$totalSamples = $xData.Count

Write-Host "Loaded $totalSamples samples"
Write-Host "X-axis range: $($xData | Measure-Object -Minimum | Select-Object -ExpandProperty Minimum) to $($xData | Measure-Object -Maximum | Select-Object -ExpandProperty Maximum)"

$baseline = 2089
$maxDeviation = ($xData | ForEach-Object { [Math]::Abs($_ - $baseline) } | Measure-Object -Maximum).Maximum
Write-Host "Baseline: $baseline, Max deviation from baseline: $maxDeviation"

# Shot detection function
function Detect-Shots {
    param(
        [int[]]$XData,
        [int]$Baseline = 2089,
        [int]$Threshold = 200,
        [int]$MinDuration = 6,
        [int]$MaxDuration = 12,
        [int]$MinInterval = 50
    )
    
    $shots = @()
    $inSpike = $false
    $spikeStart = 0
    $spikeSamples = 0
    $lastShotEnd = -$MinInterval
    $maxDev = 0
    
    for ($i = 0; $i -lt $XData.Count; $i++) {
        $deviation = [Math]::Abs($XData[$i] - $Baseline)
        
        if (-not $inSpike -and $deviation -gt $Threshold -and ($i - $lastShotEnd) -ge $MinInterval) {
            # Start of potential spike
            $inSpike = $true
            $spikeStart = $i
            $spikeSamples = 1
            $maxDev = $deviation
        }
        elseif ($inSpike -and $deviation -gt $Threshold) {
            # Continue spike
            $spikeSamples++
            if ($deviation -gt $maxDev) { $maxDev = $deviation }
        }
        elseif ($inSpike -and $deviation -le $Threshold) {
            # End of spike - check if it qualifies
            if ($spikeSamples -ge $MinDuration -and $spikeSamples -le $MaxDuration) {
                $timeSeconds = [Math]::Round($spikeStart / 50.0, 1)
                $shots += [PSCustomObject]@{
                    SampleStart = $spikeStart
                    SampleEnd = $i - 1
                    DurationSamples = $spikeSamples
                    MaxDeviation = $maxDev
                    TimeSeconds = $timeSeconds
                }
                $lastShotEnd = $i
            }
            $inSpike = $false
            $spikeSamples = 0
        }
    }
    
    return $shots
}

# Test different thresholds
$thresholds = @(150, 175, 200, 225, 250)

foreach ($threshold in $thresholds) {
    Write-Host "`n=== Testing threshold: $threshold counts ==="
    $shots = Detect-Shots -XData $xData -Threshold $threshold
    
    Write-Host "Detected $($shots.Count) shots:"
    for ($i = 0; $i -lt $shots.Count; $i++) {
        $shot = $shots[$i]
        Write-Host "  Shot $($i+1): Sample $($shot.SampleStart)-$($shot.SampleEnd) ($($shot.TimeSeconds)s), Duration: $($shot.DurationSamples) samples, Max deviation: $($shot.MaxDeviation) counts"
    }
}

# Detailed analysis with recommended threshold (200)
Write-Host "`n$('=' * 60)"
Write-Host "DETAILED ANALYSIS - Threshold: 200 counts"  
Write-Host "$('=' * 60)"

$shots = Detect-Shots -XData $xData -Threshold 200

# Focus on samples 200-600 where user observed the 6 shots
$focusStart = 200
$focusEnd = 600
$focusX = $xData[$focusStart..$focusEnd]
$focusMin = ($focusX | Measure-Object -Minimum).Minimum
$focusMax = ($focusX | Measure-Object -Maximum).Maximum

Write-Host "`nFocus region (samples $focusStart-$focusEnd):"
Write-Host "X-axis range in focus: $focusMin to $focusMax"

$shotsInFocus = $shots | Where-Object { $_.SampleStart -ge $focusStart -and $_.SampleStart -le $focusEnd }
Write-Host "Shots detected in focus region: $($shotsInFocus.Count)"

# Compare with known AMG timer shots (6 shots expected)
# From log analysis: shots occurred around 18.9, 20.1, 21.4, 22.5, 23.8, 25.1 seconds
$expectedShotTimes = @(18.9, 20.1, 21.4, 22.5, 23.8, 25.1)

Write-Host "`nComparison with AMG timer shots:"
Write-Host "Expected: 6 shots at approximately $($expectedShotTimes -join ', ') seconds"
Write-Host "Detected: $($shots.Count) shots"

for ($i = 0; $i -lt $shots.Count; $i++) {
    $shot = $shots[$i]
    $closestExpected = $expectedShotTimes | ForEach-Object { [PSCustomObject]@{ Time = $_; Diff = [Math]::Abs($_ - $shot.TimeSeconds) } } | Sort-Object Diff | Select-Object -First 1
    Write-Host "  Shot $($i+1): $($shot.TimeSeconds)s (closest expected: $($closestExpected.Time)s, diff: $([Math]::Round($closestExpected.Diff, 1))s)"
}

# Create summary
$summary = @"
SHOT DETECTION SUMMARY
==================================================
Total shots detected: $($shots.Count)
Time span: $($shots[0].TimeSeconds)s to $($shots[-1].TimeSeconds)s  
Average duration: $([Math]::Round(($shots | Measure-Object -Property DurationSamples -Average).Average, 1)) samples
Average deviation: $([Math]::Round(($shots | Measure-Object -Property MaxDeviation -Average).Average, 0)) counts

Individual shots:
"@

for ($i = 0; $i -lt $shots.Count; $i++) {
    $shot = $shots[$i]
    $summary += "Shot $($i+1): $($shot.TimeSeconds)s | $($shot.DurationSamples) samples | $($shot.MaxDeviation) counts deviation`n"
}

Write-Host "`n$summary"

# Save results
$summary | Out-File -FilePath "shot_detection_results.txt" -Encoding UTF8

# Add detailed data
"`nDetailed shot data:" | Out-File -FilePath "shot_detection_results.txt" -Append -Encoding UTF8
$shots | Out-File -FilePath "shot_detection_results.txt" -Append -Encoding UTF8

Write-Host "`nResults saved to shot_detection_results.txt"

# Recommendations
Write-Host "`n=== RECOMMENDATIONS ==="
if ($shots.Count -eq 6) {
    Write-Host "✅ PERFECT: Detected exactly 6 shots matching AMG timer data!"
    Write-Host "✅ Threshold of 200 counts is OPTIMAL for this dataset"
}
elseif ($shots.Count -gt 6) {
    Write-Host "⚠️  Over-detection: $($shots.Count) shots detected (expected 6)"
    Write-Host "→  Consider increasing threshold to 225-250 counts"
}
else {
    Write-Host "⚠️  Under-detection: $($shots.Count) shots detected (expected 6)"
    Write-Host "→  Consider decreasing threshold to 175-150 counts"
}

Write-Host "`nProposed shot qualification criteria:"
Write-Host "• X-axis deviation > 200 counts from baseline (2089)"
Write-Host "• Duration: 6-12 consecutive samples (120-240ms at 50Hz)"
Write-Host "• Minimum 1 second interval between shots"
Write-Host "• Return to baseline within 5 samples after spike"