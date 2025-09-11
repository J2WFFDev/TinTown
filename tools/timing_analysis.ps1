# TinTown Timing Analysis Tool (PowerShell Version)
# Analyzes timing patterns between AMG timer events and BT50 sensor impacts

param(
    [string]$LogPath = "logs\remote_backup",
    [int]$WindowMs = 2000,
    [string]$OutputFile = "timing_calibration.json",
    [switch]$Verbose
)

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "TINTOWN TIMING CALIBRATION ANALYSIS" -ForegroundColor Cyan  
Write-Host "============================================================" -ForegroundColor Cyan

Write-Host "Log Path: $LogPath" -ForegroundColor Gray
Write-Host "Correlation Window: $WindowMs ms" -ForegroundColor Gray
Write-Host "Output File: $OutputFile" -ForegroundColor Gray
Write-Host ""

if (!(Test-Path $LogPath)) {
    Write-Host "ERROR: Log path not found: $LogPath" -ForegroundColor Red
    exit 1
}

Write-Host "Analyzing logs in: $LogPath" -ForegroundColor Green

# Find all log files
$logFiles = @()
$logFiles += Get-ChildItem -Path $LogPath -Filter "*.csv" -Recurse -ErrorAction SilentlyContinue
$logFiles += Get-ChildItem -Path $LogPath -Filter "*.ndjson" -Recurse -ErrorAction SilentlyContinue
$logFiles += Get-ChildItem -Path $LogPath -Filter "*.log" -Recurse -ErrorAction SilentlyContinue

Write-Host "Found $($logFiles.Count) log files" -ForegroundColor Yellow

$events = @()
$shotEvents = @()
$impactEvents = @()

foreach ($file in $logFiles) {
    if ($Verbose) {
        Write-Host "  Processing: $($file.Name)" -ForegroundColor Gray
    }
    
    $fileEvents = 0
    
    try {
        if ($file.Extension -eq ".log") {
            # Handle debug log files with Python logging format
            $logLines = Get-Content -Path $file.FullName -ErrorAction Stop
            
            foreach ($line in $logLines) {
                if ($line -match "(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}).*AMG SHOT #(\d+) detected") {
                    $timestampStr = $matches[1]
                    $shotNumber = [int]$matches[2]
                    
                    # Convert Python log timestamp to DateTime
                    $timestamp = [DateTime]::ParseExact($timestampStr, "yyyy-MM-dd HH:mm:ss,fff", $null)
                    
                    $shotEvents += @{
                        Timestamp = $timestamp
                        Type = "shot"
                        DeviceId = "Timer"
                        ShotNumber = $shotNumber
                        Details = "Shot #$shotNumber from debug log"
                    }
                    $fileEvents++
                }
            }
        }
        elseif ($file.Extension -eq ".csv") {
            $csvData = Import-Csv -Path $file.FullName -ErrorAction Stop
            
            foreach ($row in $csvData) {
                try {
                    # Parse CSV datetime format like "9/9/25 11:15:54.63am"
                    $dateTimeStr = $row.Datetime -replace "am", " AM" -replace "pm", " PM"
                    $timestamp = [DateTime]::ParseExact($dateTimeStr, "M/d/yy h:mm:ss.fftt", $null)
                    
                    $deviceType = $row.Device
                    $deviceId = $row.DeviceID  
                    $details = $row.Details
                    
                    # Look for shot events
                    if ($deviceType -eq "Timer" -and $details -like "*shot*") {
                        $shotMatch = [regex]::Match($details, "shot\s*#?(\d+)", [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
                        if ($shotMatch.Success) {
                            $shotNumber = [int]$shotMatch.Groups[1].Value
                            $shotEvents += @{
                                Timestamp = $timestamp
                                Type = "shot"
                                DeviceId = $deviceId
                                ShotNumber = $shotNumber
                                Details = $details
                            }
                            $fileEvents++
                        }
                    }
                    
                    # Look for impact events
                    if ($deviceType -eq "Sensor" -and ($details -like "*impact*" -or $details -like "*detected*")) {
                        $magMatch = [regex]::Match($details, "mag\s*=\s*([\d.]+)", [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
                        if ($magMatch.Success) {
                            $magnitude = [double]$magMatch.Groups[1].Value
                            $impactEvents += @{
                                Timestamp = $timestamp
                                Type = "impact"
                                DeviceId = $deviceId
                                Magnitude = $magnitude
                                Details = $details
                            }
                            $fileEvents++
                        }
                    }
                } catch {
                    # Skip problematic rows
                }
            }
        }
        elseif ($file.Extension -eq ".ndjson") {
            $lines = Get-Content -Path $file.FullName -ErrorAction Stop
            
            foreach ($line in $lines) {
                if ($line.Trim()) {
                    try {
                        $jsonData = $line | ConvertFrom-Json -ErrorAction Stop
                        $timestampStr = $jsonData.timestamp_iso
                        $timestamp = [DateTime]::Parse($timestampStr)
                        
                        # Check for AMG timer shot events
                        if ($jsonData.type -eq "amg_parsed" -and $jsonData.data.shot_number) {
                            $shotNumber = $jsonData.data.shot_number
                            $shotEvents += @{
                                Timestamp = $timestamp
                                Type = "shot"
                                DeviceId = $jsonData.device_id
                                ShotNumber = $shotNumber
                                Details = "Shot #$shotNumber"
                            }
                            $fileEvents++
                        }
                        
                        # Check for BT50 sensor impact events
                        if ($jsonData.type -eq "bt50_parsed" -and $jsonData.data.mag -gt 0.1) {
                            $magnitude = $jsonData.data.mag
                            $impactEvents += @{
                                Timestamp = $timestamp
                                Type = "impact"
                                DeviceId = $jsonData.device_id
                                Magnitude = $magnitude
                                Details = "Impact magnitude $magnitude"
                            }
                            $fileEvents++
                        }
                        
                        # Check for Impact events in latest_test.ndjson format
                        if ($jsonData.type -eq "Impact" -and $jsonData.details -like "*Impact detected*") {
                            $magMatch = [regex]::Match($jsonData.details, "Impact detected: ([\d.]+)", [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
                            if ($magMatch.Success) {
                                $magnitude = [double]$magMatch.Groups[1].Value
                                $impactEvents += @{
                                    Timestamp = $timestamp
                                    Type = "impact"
                                    DeviceId = $jsonData.device_id
                                    Magnitude = $magnitude
                                    Details = $jsonData.details
                                }
                                $fileEvents++
                            }
                        }
                    } catch {
                        # Skip invalid JSON lines
                    }
                }
            }
        }
    } catch {
        Write-Warning "Error processing file $($file.Name): $($_.Exception.Message)"
    }
    
    if ($Verbose) {
        Write-Host "    Events: $fileEvents" -ForegroundColor Gray
    }
}

$totalEvents = $shotEvents.Count + $impactEvents.Count
Write-Host "Total events parsed: $totalEvents" -ForegroundColor White
Write-Host "  - Shot events: $($shotEvents.Count)" -ForegroundColor Yellow
Write-Host "  - Impact events: $($impactEvents.Count)" -ForegroundColor Yellow

if ($shotEvents.Count -eq 0 -or $impactEvents.Count -eq 0) {
    Write-Host "`nNo shot-impact pairs possible with current data" -ForegroundColor Red
    Write-Host "Need both timer shot events and sensor impact events for correlation" -ForegroundColor Yellow
    
    $config = @{
        error = "Insufficient data for correlation"
        shots_found = $shotEvents.Count
        impacts_found = $impactEvents.Count
        analysis_date = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss")
    }
    
    $config | ConvertTo-Json -Depth 3 | Out-File -FilePath $OutputFile -Encoding UTF8
    Write-Host "`nBasic analysis exported to: $OutputFile" -ForegroundColor Green
    exit 0
}

# Sort events by timestamp
$shotEvents = $shotEvents | Sort-Object Timestamp
$impactEvents = $impactEvents | Sort-Object Timestamp

Write-Host "`nAttempting correlation with $WindowMs ms window..." -ForegroundColor Cyan

# Correlate events
$pairs = @()
$usedImpacts = @{}

foreach ($shot in $shotEvents) {
    $bestImpact = $null
    $bestDelay = [double]::MaxValue
    $bestIndex = -1
    
    $windowEnd = $shot.Timestamp.AddMilliseconds($WindowMs)
    
    for ($i = 0; $i -lt $impactEvents.Count; $i++) {
        if ($usedImpacts.ContainsKey($i)) {
            continue
        }
        
        $impact = $impactEvents[$i]
        
        if ($impact.Timestamp -lt $shot.Timestamp) {
            continue
        }
        
        if ($impact.Timestamp -gt $windowEnd) {
            break
        }
        
        $delayMs = ($impact.Timestamp - $shot.Timestamp).TotalMilliseconds
        
        if ($delayMs -lt $bestDelay) {
            $bestDelay = $delayMs
            $bestImpact = $impact
            $bestIndex = $i
        }
    }
    
    if ($bestImpact) {
        $usedImpacts[$bestIndex] = $true
        $pairs += @{
            Shot = $shot
            Impact = $bestImpact
            DelayMs = [int]$bestDelay
        }
    }
}

# Analysis Report
Write-Host "`n============================================================" -ForegroundColor Green
Write-Host "TIMING ANALYSIS REPORT" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green

Write-Host "`nCorrelated pairs: $($pairs.Count)" -ForegroundColor Green

if ($pairs.Count -gt 0) {
    $delays = $pairs | ForEach-Object { $_.DelayMs }
    $magnitudes = $pairs | ForEach-Object { $_.Impact.Magnitude }
    
    $minDelay = ($delays | Measure-Object -Minimum).Minimum
    $maxDelay = ($delays | Measure-Object -Maximum).Maximum
    $meanDelay = [Math]::Round(($delays | Measure-Object -Average).Average, 1)
    
    # Calculate median
    $sortedDelays = $delays | Sort-Object
    $count = $sortedDelays.Count
    if ($count % 2 -eq 0) {
        $medianDelay = ($sortedDelays[$count/2 - 1] + $sortedDelays[$count/2]) / 2
    } else {
        $medianDelay = $sortedDelays[[Math]::Floor($count/2)]
    }
    
    # Calculate standard deviation
    $variance = ($delays | ForEach-Object { [Math]::Pow($_ - $meanDelay, 2) } | Measure-Object -Sum).Sum / ($delays.Count - 1)
    $stdevDelay = [Math]::Round([Math]::Sqrt($variance), 1)
    
    Write-Host "`nTiming Delay Statistics:" -ForegroundColor Cyan
    Write-Host "  - Mean delay: $meanDelay ms" -ForegroundColor White
    Write-Host "  - Median delay: $medianDelay ms" -ForegroundColor White
    Write-Host "  - Min/Max delay: $minDelay - $maxDelay ms" -ForegroundColor White
    Write-Host "  - Standard deviation: $stdevDelay ms" -ForegroundColor White
    
    $minMag = ($magnitudes | Measure-Object -Minimum).Minimum
    $maxMag = ($magnitudes | Measure-Object -Maximum).Maximum
    $meanMag = [Math]::Round(($magnitudes | Measure-Object -Average).Average, 3)
    
    Write-Host "`nImpact Magnitude Statistics:" -ForegroundColor Cyan
    Write-Host "  - Mean magnitude: $meanMag" -ForegroundColor White
    Write-Host "  - Min/Max magnitude: $minMag - $maxMag" -ForegroundColor White
    
    $recommendedWindow = [Math]::Round($meanDelay + (3 * $stdevDelay))
    Write-Host "`nRecommended correlation window: $recommendedWindow ms" -ForegroundColor Green
    
    Write-Host "`nDetailed Pairs (first 10):" -ForegroundColor Cyan
    for ($i = 0; $i -lt [Math]::Min(10, $pairs.Count); $i++) {
        $pair = $pairs[$i]
        $delayMs = $pair.DelayMs
        $mag = $pair.Impact.Magnitude
        $shotNum = $pair.Shot.ShotNumber
        Write-Host "  $($i + 1). Shot #$shotNum -> Impact ${mag}g (${delayMs}ms)" -ForegroundColor White
    }
    
    if ($pairs.Count -gt 10) {
        Write-Host "  ... and $($pairs.Count - 10) more pairs" -ForegroundColor Gray
    }
    
    # Export calibration config
    $config = @{
        timing_calibration = @{
            correlation_window_ms = $recommendedWindow
            expected_delay_ms = [int]$meanDelay
            delay_tolerance_ms = [int]($stdevDelay * 2)
            minimum_magnitude = $meanMag
            analysis_date = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss")
            sample_count = $pairs.Count
        }
        statistics = @{
            shots_analyzed = $shotEvents.Count
            impacts_analyzed = $impactEvents.Count
            pairs_correlated = $pairs.Count
            correlation_rate_percent = [Math]::Round(($pairs.Count / $shotEvents.Count) * 100, 1)
            delay_stats = @{
                min_ms = $minDelay
                max_ms = $maxDelay
                mean_ms = $meanDelay
                median_ms = $medianDelay
                stdev_ms = $stdevDelay
            }
            magnitude_stats = @{
                min = $minMag
                max = $maxMag
                mean = $meanMag
            }
        }
    }
} else {
    Write-Host "`nNo correlated shot-impact pairs found!" -ForegroundColor Red
    Write-Host "This could indicate:" -ForegroundColor Yellow
    Write-Host "  - Timing window too narrow ($WindowMs ms)" -ForegroundColor Yellow
    Write-Host "  - Events from different sessions" -ForegroundColor Yellow
    Write-Host "  - No simultaneous timer and sensor activity" -ForegroundColor Yellow
    
    $config = @{
        error = "No correlations found"
        timing_window_tested_ms = $WindowMs
        shots_analyzed = $shotEvents.Count
        impacts_analyzed = $impactEvents.Count
        analysis_date = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss")
        suggestion = "Try increasing timing window or collecting simultaneous data"
    }
}

$config | ConvertTo-Json -Depth 4 | Out-File -FilePath $OutputFile -Encoding UTF8
Write-Host "`nCalibration config exported to: $OutputFile" -ForegroundColor Green

Write-Host "`nAnalysis complete!" -ForegroundColor Green