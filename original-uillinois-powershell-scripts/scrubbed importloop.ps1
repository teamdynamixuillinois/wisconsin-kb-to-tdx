$scriptPath = Split-Path -parent $MyInvocation.MyCommand.Definition
$scriptName = ($MyInvocation.MyCommand.Name -split '\.')[0]
$logFile = "$scriptPath\$scriptName.log"

$cpappId = ID of the Portal App
$apiBaseUri = "URL FOR API/SBTDWebApi/"
$apiWSBeid = "BE ID FROM PROD OR SB"
$apiWSKey = "WEB SERVICES KEY FROM PROD OR SB"
$dataFilePath = "data\FullProductionImport\"
$kbFilenamePrefix = "KBexport"

# See if PSSQLite is installed. If so, import it. Otherwise, install it and then import it.
if(!(Get-Module -ListAvailable -Name PSSQLite)) {
    
    Write-Host "PSSQLite is not installed. Installing now as this is a required dependency."
    Install-Module PSSQLite -Force

}
Import-Module PSSQLite

function Write-Log {
    
    param (
    
        [ValidateSet('ERROR', 'INFO', 'VERBOSE', 'WARN')]
        [Parameter(Mandatory = $true)]
        [string]$level,

        [Parameter(Mandatory = $true)]
        [string]$string

    )
    
    $logString = (Get-Date).toString("yyyy-MM-dd HH:mm:ss") + " [$level] $string"
    Add-Content -Path $logFile -Value $logString -Force
    
    $foregroundColor = $host.ui.RawUI.ForegroundColor
    $backgroundColor = $host.ui.RawUI.BackgroundColor

    Switch ($level) {
    
        {$_ -eq 'VERBOSE' -or $_ -eq 'INFO'} {
            
            Out-Host -InputObject "$logString"
            
        }

        {$_ -eq 'ERROR'} {

            $host.ui.RawUI.ForegroundColor = "Red"
            $host.ui.RawUI.BackgroundColor = "Black"

            Out-Host -InputObject "$logString"
    
            $host.ui.RawUI.ForegroundColor = $foregroundColor
            $host.UI.RawUI.BackgroundColor = $backgroundColor

        }

        {$_ -eq 'WARN'} {
    
            $host.ui.RawUI.ForegroundColor = "Yellow"
            $host.ui.RawUI.BackgroundColor = "Black"

            Out-Host -InputObject "$logString"
    
            $host.ui.RawUI.ForegroundColor = $foregroundColor
            $host.UI.RawUI.BackgroundColor = $backgroundColor

        }
    
    }
    
}

function ApiAuthenticateAndBuildAuthHeaders {
	param (
		[string]$apiBaseUri,
        [string]$apiWSBeid,
        [string]$apiWSKey
	)
	
	# Set the user authentication URI and create an authentication JSON body.
	$authUri = $apiBaseUri + "api/auth/loginadmin"
	$authBody = @{ 
		BEID=$apiWSBeid; 
		WebServicesKey=$apiWSKey
	} | ConvertTo-Json
	
	# Call the user login API method and store the returned tokenn.
	# If this part fails, display errors and exit the entire script.
	# We cannot proceed without authentication.
	$authToken = try {
		Invoke-RestMethod -Method Post -Uri $authUri -Body $authBody -ContentType "application/json"
	} catch {

		# Display errors and exit script.
		Write-Log -level ERROR -string "API authentication failed:"
		Write-Log -level ERROR -string ("Status Code - " + $_.Exception.Response.StatusCode.value__)
		Write-Log -level ERROR -string ("Status Description - " + $_.Exception.Response.StatusDescription)
		Write-Log -level ERROR -string ("Error Message - " + $_.ErrorDetails.Message)
		Write-Log -level INFO -string " "
		Write-Log -level ERROR -string "The import cannot proceed when API authentication fails. Please check your authentication settings and try again."
		Write-Log -level INFO -string " "
		Write-Log -level INFO -string "Exiting."
		Write-Log -level INFO -string $processingLoopSeparator
		Exit(1)
		
	}

	# Create an API header object containing an Authorization header with a
	# value of "Bearer {tokenReturnedFromAuthCall}".
	$apiHeaders = @{"Authorization"="Bearer " + $authToken}

	# Return the API headers.
	return $apiHeaders
	
}

function RetrieveAllUsersForOrganization {
	param (
        [System.Collections.Hashtable]$apiHeaders,
		[string]$apiBaseUri
    )

    # Build URI to get all users for the organization.
    $getUserListUri = $apiBaseUri + "/api/people/userlist?isActive=&isEmployee=&userType=None"

    # Get the data.
    $userData = try {
		Invoke-WebRequest -Method Get -Headers $apiHeaders -Uri $getUserListUri -ContentType "application/json"
	} catch {

		# Display errors and exit script.
		Write-Log -level ERROR -string "Retrieving all users for the organization failed:"
		Write-Log -level ERROR -string ("Status Code - " + $_.Exception.Response.StatusCode.value__)
		Write-Log -level ERROR -string ("Status Description - " + $_.Exception.Response.StatusDescription)
		Write-Log -level ERROR -string ("Error Message - " + $_.ErrorDetails.Message)
		Write-Log -level INFO -string " "
		Write-Log -level ERROR -string "The import cannot proceed when retrieving user data fails. Please check your authentication settings and try again."
		Write-Log -level INFO -string " "
		Write-Log -level INFO -string "Exiting."
		Write-Log -level INFO -string $processingLoopSeparator
		Exit(1)
		
    }
    
    # All is good. Return the user data. If we have data, sort it by
    # type ID asc, last name asc, first name asc. This prefers users
    # over customers.
    if($userData) {
	    $userData = ($userData | ConvertFrom-Json)
    }

    return $userData

}

$userDataDb = $scriptPath + "\userData.db"
if (-Not ($userDataDb | Test-Path)) {

    Write-Log -level INFO -string "Authenticating to the TeamDynamix Web API with a base URL of $($apiBaseUri)."
    $apiHeaders = ApiAuthenticateAndBuildAuthHeaders -apiBaseUri $apiBaseUri -apiWSBeid $apiWSBeid -apiWSKey $apiWSKey

    Write-Log -level INFO -string "Retrieving all user data for the organization (for owner matching) from the TeamDynamix Web API."
    $userData = RetrieveAllUsersForOrganization -apiHeaders $apiHeaders -apiBaseUri $apiBaseUri
    $userCount = 0
    if($userData -and $userData.length -gt 0) {
        $userCount = $userData.length
    }
    Write-Log -level INFO -string "Found $($userCount) user(s) for this organization."

    if($userCount -gt 0) {    

		Write-Log -level INFO -string "Converting select fields from API data into user info datatable."
        $sqlData = ($userData | Select-Object UID, Username, FirstName, LastName, TypeID | Out-DataTable)
		Write-Log -level INFO -string "User inf datatable created successfully."
        $userTableCreateSql = $scriptPath + "\createUserTable.sql"
        Write-Log -level INFO -string "Creating client-side SQLite database."
		Invoke-SqliteQuery -InputFile $userTableCreateSql -DataSource $userDataDb
		Write-Log -level INFO -string "Client-side SQLite database created successfully."
		Write-Log -level INFO -string "Populating client-side SQLite database."
        Invoke-SQLiteBulkCopy -DataTable $sqlData -DataSource $userDataDb -Table "Users" -NotifyAfter 0 -Force
		Write-Log -level INFO -string "Client-side SQLite database populated successfully."

    }

}

$files = Get-ChildItem $dataFilePath | Select Name
foreach($file in $files) {
    
    $filePath = $dataFilePath + $file.Name
    $filenoext = [System.IO.Path]::GetFileNameWithoutExtension($file.Name)
    $categoryId = $filenoext.replace($kbFilenamePrefix, "")
	Write-Log -level INFO -string "Importing KBs from file '$($filePath)' into category $($categoryId)."
	
    & .\kbimportwithreviewdate.ps1 -fileLocation $filePath -cpappId $cpappId -categoryId $categoryId -apiBaseUri $apiBaseUri -apiWSBeid $apiWSBeid -apiWSKey $apiWSKey
    
	Write-Log -level INFO -string "Import of KBs from file '$($filePath)' complete. Pausing 1 minute for rate-limits."
	
    Start-Sleep -m 60000

}