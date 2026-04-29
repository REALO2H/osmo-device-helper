[CmdletBinding()]
param(
    [string]$Port = "COM1",
    [int]$BaudRate = 9600,
    [switch]$AutoAck = $true,
    [string]$CsvPath = "C:\OSMO\Osmo6070\OM6070_Parsed_Live.csv",
    [string]$LogPath = "C:\OSMO\Osmo6070\capture.log",
    [string]$HeartbeatFile = "C:\OSMO\Osmo6070\capture_heartbeat.json",
    [string]$StopFile = "C:\OSMO\Osmo6070\stop_capture.flag"
)

# -----------------------------
# Setup / Utilities
# -----------------------------

$script:LastActivity = Get-Date
$script:CsvInitialized = $false

function Ensure-Folder {
    param([string]$FilePath)

    $folder = Split-Path -Parent $FilePath
    if ($folder -and -not (Test-Path $folder)) {
        New-Item -ItemType Directory -Path $folder -Force | Out-Null
    }
}

function Write-Colored {
    param([string]$Text, [string]$Color = 'Gray')
    try {
        Write-Host $Text -ForegroundColor $Color
        [Console]::Out.Flush()
    } catch {}
}

function Write-Log {
    param([string]$Message)

    $ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss.fff")
    $line = "[$ts] $Message"
    try {
        Add-Content -Path $LogPath -Value $line -Encoding UTF8
    } catch {}
}

function Update-Heartbeat {
    param(
        [string]$State = "running",
        [string]$Details = ""
    )

    try {
        $obj = [PSCustomObject]@{
            pid           = $PID
            port          = $Port
            baud_rate     = $BaudRate
            auto_ack      = [bool]$AutoAck
            state         = $State
            details       = $Details
            last_seen     = (Get-Date).ToString("s")
            last_activity = $script:LastActivity.ToString("s")
            csv_path      = $CsvPath
            log_path      = $LogPath
        }

        $obj | ConvertTo-Json -Depth 3 | Set-Content -Path $HeartbeatFile -Encoding UTF8
    }
    catch {}
}

function Initialize-Csv {
    if (-not (Test-Path $CsvPath)) {
        $header = [PSCustomObject]@{
            MeasurementTimestamp = ""
            SampleID             = ""
            MeasurementNo        = ""
            ResultType           = ""
            ResultValue          = ""
            Unit                 = ""
            Flags                = ""
            SampleType           = ""
            ErrorOrComment       = ""
            OperatorID           = ""
            RawResultRecord      = ""
        }

        $header |
            Select-Object MeasurementTimestamp, SampleID, MeasurementNo, ResultType, ResultValue, Unit, Flags, SampleType, ErrorOrComment, OperatorID, RawResultRecord |
            Export-Csv -Path $CsvPath -NoTypeInformation -Encoding UTF8

        # Remove the fake first row, keep only header
        $lines = Get-Content $CsvPath
        if ($lines.Count -ge 2) {
            $lines[0] | Set-Content -Path $CsvPath -Encoding UTF8
        }
    }

    $script:CsvInitialized = $true
}

function Add-CsvRow {
    param(
        [string]$MeasurementTimestamp,
        [string]$SampleID,
        [string]$MeasurementNo,
        [string]$ResultType,
        [string]$ResultValue,
        [string]$Unit,
        [string]$Flags,
        [string]$SampleType,
        [string]$ErrorOrComment,
        [string]$OperatorID,
        [string]$RawResultRecord
    )

    if (-not $script:CsvInitialized) {
        Initialize-Csv
    }

    $row = [PSCustomObject]@{
        MeasurementTimestamp = $MeasurementTimestamp
        SampleID             = $SampleID
        MeasurementNo        = $MeasurementNo
        ResultType           = $ResultType
        ResultValue          = $ResultValue
        Unit                 = $Unit
        Flags                = $Flags
        SampleType           = $SampleType
        ErrorOrComment       = $ErrorOrComment
        OperatorID           = $OperatorID
        RawResultRecord      = $RawResultRecord
    }

    try {
        $row |
            Select-Object MeasurementTimestamp, SampleID, MeasurementNo, ResultType, ResultValue, Unit, Flags, SampleType, ErrorOrComment, OperatorID, RawResultRecord |
            Export-Csv -Path $CsvPath -NoTypeInformation -Append -Encoding UTF8
    }
    catch {
        Write-Log "ERROR writing CSV row: $($_.Exception.Message)"
    }
}

function Bytes-ToHex([byte[]] $Bytes) {
    ($Bytes | ForEach-Object { $_.ToString('X2') }) -join ' '
}

function Bytes-ToSafeAscii([byte[]] $Bytes) {
    -join ($Bytes | ForEach-Object {
        switch ($_){
            0x02 { '<STX>' }
            0x03 { '<ETX>' }
            0x04 { '<EOT>' }
            0x05 { '<ENQ>' }
            0x06 { '<ACK>' }
            0x15 { '<NAK>' }
            0x17 { '<ETB>' }
            0x0D { '<CR>' }
            0x0A { '<LF>' }
            default {
                if ($_ -ge 0x20 -and $_ -le 0x7E) { [char]$_ }
                else { '.' }
            }
        }
    })
}

function Send-Ack {
    param([System.IO.Ports.SerialPort] $SerialPort)
    try {
        $ack = [byte[]]@(0x06)
        $SerialPort.Write($ack, 0, $ack.Length)
    }
    catch {
        Write-Log "ERROR sending ACK: $($_.Exception.Message)"
    }
}

function Get-Field {
    param(
        [string[]]$Fields,
        [int]$Index
    )
    if ($null -ne $Fields -and $Fields.Count -gt $Index) {
        return $Fields[$Index].Trim()
    }
    return ""
}

function Try-ExtractFrame {
    param([System.Collections.Generic.List[byte]]$Rx)

    if ($Rx.Count -lt 7) { return $null }

    $start = $Rx.IndexOf([byte]0x02)  # STX
    if ($start -lt 0) { return $null }

    # discard garbage before STX
    if ($start -gt 0) {
        $Rx.RemoveRange(0, $start)
    }

    if ($Rx.Count -lt 7) { return $null }

    for ($i = 2; $i -le $Rx.Count - 5; $i++) {
        $b = $Rx[$i]
        if ($b -eq 0x17 -or $b -eq 0x03) {   # ETB or ETX
            if ($i + 4 -lt $Rx.Count) {
                if ($Rx[$i+3] -eq 0x0D -and $Rx[$i+4] -eq 0x0A) {
                    $len = $i + 5
                    $frame = New-Object byte[] $len
                    $Rx.CopyTo(0, $frame, 0, $len)
                    $Rx.RemoveRange(0, $len)
                    return $frame
                }
            }
        }
    }

    return $null
}

# -----------------------------
# Prepare files/folders
# -----------------------------

Ensure-Folder $CsvPath
Ensure-Folder $LogPath
Ensure-Folder $HeartbeatFile
Ensure-Folder $StopFile

# Optional: remove stale stop file at startup
if (Test-Path $StopFile) {
    try { Remove-Item $StopFile -Force -ErrorAction SilentlyContinue } catch {}
}

Initialize-Csv
Update-Heartbeat -State "starting" -Details "Initializing serial worker"

# -----------------------------
# Serial setup (OM-6070 standard = 8N1)
# -----------------------------

$sp = [System.IO.Ports.SerialPort]::new(
    $Port,
    $BaudRate,
    [System.IO.Ports.Parity]::None,
    8,
    [System.IO.Ports.StopBits]::One
)
$sp.Handshake   = [System.IO.Ports.Handshake]::None
$sp.ReadTimeout = 100
$sp.Encoding    = [System.Text.Encoding]::ASCII
$sp.DtrEnable   = $false
$sp.RtsEnable   = $false

Write-Colored "Listening on $Port @ $BaudRate (8N1, Handshake=None)" 'White'
Write-Colored "AutoAck: $AutoAck" 'White'
Write-Colored "CSV output: $CsvPath" 'White'
Write-Colored "Log file : $LogPath" 'White'
Write-Colored "Stop file: $StopFile" 'White'
Write-Colored "" 'White'

Write-Log "START capture worker. Port=$Port Baud=$BaudRate AutoAck=$AutoAck CsvPath=$CsvPath"

# Receive buffer
$rx = [System.Collections.Generic.List[byte]]::new()

# Message-state variables
$recordBuffer      = ""
$currentHeader     = $null
$currentSampleID   = ""
$currentMeasNo     = ""
$currentSampleType = ""
$currentComment    = ""
$currentOperator   = ""
$pendingResults    = New-Object System.Collections.Generic.List[object]

function Reset-CurrentMessage {
    $script:recordBuffer      = ""
    $script:currentHeader     = $null
    $script:currentSampleID   = ""
    $script:currentMeasNo     = ""
    $script:currentSampleType = ""
    $script:currentComment    = ""
    $script:currentOperator   = ""
    $script:pendingResults    = New-Object System.Collections.Generic.List[object]
}

Reset-CurrentMessage

$lastHeartbeatWrite = Get-Date

try {
    $sp.Open()
    Write-Log "Serial port opened successfully"

    while ($true) {
        if (Test-Path $StopFile) {
            Write-Log "Stop file detected. Exiting."
            Write-Colored "Stop file detected. Exiting..." 'Yellow'
            break
        }

        if (((Get-Date) - $lastHeartbeatWrite).TotalSeconds -ge 3) {
            Update-Heartbeat -State "running" -Details "Waiting/processing serial data"
            $lastHeartbeatWrite = Get-Date
        }

        $toRead = $sp.BytesToRead
        if ($toRead -gt 0) {
            $tmp = New-Object byte[] $toRead
            [void]$sp.Read($tmp, 0, $toRead)

            $script:LastActivity = Get-Date

            $ts  = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss.fff')
            $hex = Bytes-ToHex $tmp
            $asc = Bytes-ToSafeAscii $tmp

            Write-Colored "[$ts] RAW HEX  : $hex" 'Yellow'
            Write-Colored "[$ts] RAW ASCII: $asc" 'Gray'
            Write-Log "RAW HEX: $hex"
            Write-Log "RAW ASCII: $asc"

            foreach ($b in $tmp) {
                switch ($b) {
                    0x05 {   # ENQ
                        Write-Colored "[$ts] CTRL ENQ" 'Cyan'
                        Write-Log "CTRL ENQ"
                        if ($AutoAck) {
                            Send-Ack $sp
                            Write-Colored "[$ts] -> ACK sent for ENQ" 'Green'
                            Write-Log "ACK sent for ENQ"
                        }
                    }
                    0x04 {   # EOT
                        Write-Colored "[$ts] CTRL EOT" 'Red'
                        Write-Log "CTRL EOT"
                    }
                    0x06 {
                        Write-Colored "[$ts] CTRL ACK" 'Green'
                        Write-Log "CTRL ACK"
                    }
                    0x15 {
                        Write-Colored "[$ts] CTRL NAK" 'Yellow'
                        Write-Log "CTRL NAK"
                    }
                    default {
                        $rx.Add($b)
                    }
                }
            }
        }

        while ($true) {
            $frame = Try-ExtractFrame -Rx $rx
            if ($null -eq $frame) { break }

            $script:LastActivity = Get-Date

            $ts = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss.fff')
            $fhex = Bytes-ToHex $frame
            $fascii = Bytes-ToSafeAscii $frame

            Write-Colored "[$ts] FRAME HEX  : $fhex" 'Magenta'
            Write-Colored "[$ts] FRAME ASCII: $fascii" 'White'
            Write-Log "FRAME HEX: $fhex"
            Write-Log "FRAME ASCII: $fascii"

            # frame structure: STX FN payload ETB/ETX CSH CSL CR LF
            $endIndex = -1
            for ($i = 2; $i -lt $frame.Length; $i++) {
                if ($frame[$i] -eq 0x17 -or $frame[$i] -eq 0x03) {
                    $endIndex = $i
                    break
                }
            }
            if ($endIndex -lt 0) { continue }

            $payloadBytes = if ($endIndex -gt 2) { $frame[2..($endIndex - 1)] } else { @() }
            $payloadText = [System.Text.Encoding]::ASCII.GetString($payloadBytes)

            Write-Colored "[$ts] PAYLOAD: $payloadText" 'Gray'
            Write-Log "PAYLOAD: $payloadText"

            # accumulate text because one ASTM record may theoretically span multiple frames
            $recordBuffer += $payloadText

            # parse complete records terminated by CR
            while ($recordBuffer.Contains("`r")) {
                $crIndex = $recordBuffer.IndexOf("`r")
                $line = $recordBuffer.Substring(0, $crIndex).Trim()
                $recordBuffer = $recordBuffer.Substring($crIndex + 1)

                if ([string]::IsNullOrWhiteSpace($line)) {
                    continue
                }

                $fields = $line -split '\|'
                $recordType = Get-Field $fields 0

                switch ($recordType) {
                    'H' {
                        $currentHeader = $line
                        Write-Colored "[$ts] Parsed H record" 'Cyan'
                        Write-Log "Parsed H record"
                    }

                    'P' {
                        Write-Colored "[$ts] Parsed P record" 'Cyan'
                        Write-Log "Parsed P record"
                    }

                    'O' {
                        $currentSampleID   = Get-Field $fields 2
                        $currentMeasNo     = Get-Field $fields 3
                        $currentSampleType = Get-Field $fields 15
                        $currentComment    = Get-Field $fields 19
                        $currentOperator   = ""

                        Write-Colored "[$ts] Parsed O record: SampleID=$currentSampleID MeasNo=$currentMeasNo SampleType=$currentSampleType Comment=$currentComment" 'Cyan'
                        Write-Log "Parsed O record: SampleID=$currentSampleID MeasNo=$currentMeasNo SampleType=$currentSampleType Comment=$currentComment"
                    }

                    'R' {
                        $resultType   = Get-Field $fields 2
                        $resultValue  = Get-Field $fields 3
                        $unit         = Get-Field $fields 4
                        $flags        = Get-Field $fields 6
                        $measTime     = Get-Field $fields 11

                        $pendingResults.Add([PSCustomObject]@{
                            MeasurementTimestamp = $measTime
                            SampleID             = $currentSampleID
                            MeasurementNo        = $currentMeasNo
                            ResultType           = $resultType
                            ResultValue          = $resultValue
                            Unit                 = $unit
                            Flags                = $flags
                            SampleType           = $currentSampleType
                            ErrorOrComment       = $currentComment
                            OperatorID           = $currentOperator
                            RawResultRecord      = $line
                        }) | Out-Null

                        Write-Colored "[$ts] Parsed R record: Type=$resultType Value=$resultValue Unit=$unit Flags=$flags Time=$measTime" 'Green'
                        Write-Log "Parsed R record: Type=$resultType Value=$resultValue Unit=$unit Flags=$flags Time=$measTime"
                    }

                    'L' {
                        Write-Colored "[$ts] Parsed L record -> flushing message to CSV" 'Magenta'
                        Write-Log "Parsed L record -> flushing message to CSV"

                        foreach ($row in $pendingResults) {
                            Add-CsvRow `
                                -MeasurementTimestamp $row.MeasurementTimestamp `
                                -SampleID             $row.SampleID `
                                -MeasurementNo        $row.MeasurementNo `
                                -ResultType           $row.ResultType `
                                -ResultValue          $row.ResultValue `
                                -Unit                 $row.Unit `
                                -Flags                $row.Flags `
                                -SampleType           $row.SampleType `
                                -ErrorOrComment       $row.ErrorOrComment `
                                -OperatorID           $row.OperatorID `
                                -RawResultRecord      $row.RawResultRecord
                        }

                        Reset-CurrentMessage
                    }

                    default {
                        Write-Colored "[$ts] Unhandled record: $line" 'Yellow'
                        Write-Log "Unhandled record: $line"
                    }
                }
            }

            if ($AutoAck) {
                Send-Ack $sp
                Write-Colored "[$ts] -> ACK sent for FRAME" 'Green'
                Write-Log "ACK sent for FRAME"
            }
        }

        Start-Sleep -Milliseconds 20
    }
}
catch {
    Write-Log "FATAL ERROR: $($_.Exception.Message)"
    Write-Colored "Fatal error: $($_.Exception.Message)" 'Red'
    throw
}
finally {
    Update-Heartbeat -State "stopped" -Details "Capture worker exiting"
    try { if ($sp.IsOpen) { $sp.Close() } } catch {}
    try { $sp.Dispose() } catch {}
    Write-Log "STOP capture worker"
}
