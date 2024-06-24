# Params
Param(
	[Parameter(Mandatory = $true)]
    [System.IO.FileInfo]$fileLocation,
    [Parameter(Mandatory = $true)]
    [int]$cpAppId,
	[Parameter(Mandatory = $true)]
    [int]$categoryId,
    [Parameter(Mandatory = $true)]
    [string]$apiBaseUri,
    [Parameter(Mandatory = $true)]
    [string]$apiWSBeid,
    [Parameter(Mandatory = $true)]
	[string]$apiWSKey
)

# Example Calls:
# .\kbimport.ps1 -fileLocation "data\KBexport3.json" -cpappId 30 -categoryId 0 -apiBaseUri "https://teamdynamix.umich.edu/TDWebApi/" -apiWSBeid "" -apiWSKey ""
# .\kbimport.ps1 -fileLocation "data\KBexport3.json" -cpappId 30 -categoryId 3 -apiBaseUri "https://teamdynamix.umich.edu/SBTDWebApi/" -apiWSBeid "BE ID" -apiWSKey "WEB KEY"

# Global Variables
$scriptPath = Split-Path -parent $MyInvocation.MyCommand.Definition
$scriptName = ($MyInvocation.MyCommand.Name -split '\.')[0]
$logFile = "$scriptPath\$scriptName.log"
$processingLoopSeparator = "--------------------------------------------------"

# Default Owner (Phuong Hoang)
$DefaultKBOwnerUID = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

#region PS Functions
#############################################################
##                    Helper Functions                     ##
#############################################################

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
	
    if ($userData -and $userData.length -gt 0) {
        
        $userData = $userData | `
            Sort-Object -Property TypeID | `
            Sort-Object -Property LastName | `
            Sort-Object -Property FirstName

    }

    return $userData

}

function GetUidByUsername {
    param (
        $allUserData,
        [ref]$foundUserData,
        [string]$username
    )

    # Bomb out if we have no organization user data or no name to search on.
    if(!$userData -or $userData.length -le 0 -or [string]::IsNullOrWhiteSpace($username)) {
        return $null
    }

    # Initialize the return variable.
    $authorUid = $null

    # Try to search the already found UIDs by name first. This might be much faster than all data for the organization.
    if($foundUserData.Value -and $foundUserData.Value.length -gt 0) {
        
        Write-Log -level INFO -string "Searching already found data for `"$($username)`" UID lookup."
        $authorUid = $foundUserData.Value | Where-Object { $_.Username -eq $username} | Select-Object -ExpandProperty UID -First 1

    } 
    
    # If no match was found, search the entire set of organization user data. If a match is found, add that to the found collection
    # as well to speed up future lookups.
    if($authorUid -and ![string]::IsNullOrWhiteSpace($authorUid)) {
        Write-Log -level INFO -string "Author UID for `"$($username)`" found in already matched data: $($authorUid)"
    } else {

        Write-Log -level INFO -string "No already matched data for `"$($username)`" UID lookup. Searching all user data for UID lookup."
        $authorUid = $userData | Where-Object { $_.Username -eq $username} | Select-Object -ExpandProperty UID -First 1

        # If we found an author UID value, add it to the already found collection.
        if($authorUid -and ![string]::IsNullOrWhiteSpace($authorUid)) {

            Write-Log -level INFO -string "Author UID for `"$($username)`" found in all user data: $($authorUid)"
            $foundUserData.Value += [PSCustomObject]@{
                Username=$username;
                UID=$authorUid
            }

        } else {
            
            # If we cannot find the owner, use a default value for owner instead.
            Write-Log -level INFO -string "No UID found for value `"$($username)`" in all user data. Using default value of `"$($DefaultKBOwnerUID)`" instead."
            $authorUid = $DefaultKBOwnerUID

        }

    }

    # Return the data.
    return $authorUid

}

function SaveKbArticle {
    param (
        $snowKb
    )

    # Attempt to look up the author UID if we have user data for this organization.
    [string]$authorUid = $null
    if ($userData -and $userData.length -gt 0 -and ![string]::IsNullOrEmpty($snowKb.Author)) {

        Write-Log -level INFO -string "Attempting owner UID lookup for value `"$($snowKb.Author)`"."
        $authorUid = GetUidByUsername -allUserData $userData -foundUserData ([ref]$foundUserUids) -username $snowKb.Author

    }

    # Set the next review date if we have it.
    # Use UTC 6 AM because that will always be inside of 1/1/19 for Eastern Time.
    # [string]$nextReviewDate = "2019-01-01T06:00:00Z"

    # Handle tags from the meta field. Split on spaces by default.
    # If the content contains commas though, split on that instead.
    # Then, after splitting, for each item found, replace spaces with hyphens.
    $tags = @()
    $metaCleansed = $snowKb.Meta.Replace("`r`n", "").Trim()
    $delimiter = " "
    if($metaCleansed -like '*,*') {
        $delimiter = ","
    }   
    
    foreach ($tag in $metaCleansed.Split($delimiter, [System.StringSplitOptions]::RemoveEmptyEntries)) {
        $tags += $tag.Trim().Replace(" ", "-").Trim()
    }

    # New up a new KB JSON object.
    # $attributes = @()
    # $attributes += @{ID=0; Value=$snowKb.u_assignment_group.Replace("`r`n", "").Trim()}
    # $attributes += @{ID=0; Value=$snowKb.u_group_author.Replace("`r`n", "").Trim()}
    # $attributes += @{ID=0; Value=$snowKb.number.Replace("`r`n", "").Trim()}
    # $attributes += @{ID=0; Value=$snowKb.kb_category.Replace("`r`n", "").Trim()}
    
    # Remove strange unicode characters.
    $snowKb."Article body" = ($snowKb."Article body" -replace '\u009D', '')
    $snowKb."Article body" = ($snowKb."Article body" -replace '◦', '')

    $newKbJson = @{ 
        CategoryID=$categoryId;
        Subject=$snowKb.Title.Replace("`r`n", "").Trim();
        Body=$snowKb."Article body".Replace("`r`n", "").Trim();
        Status=1; # Not submitted status.
        IsPublished=$false;
        IsPublic=$false;
        InheritPermissions=$true;
        OwnerUid=$authorUid;
        NotifyOwner=$true; #if owner is unknown, then false.
        #ReviewDateUtc=$nextReviewDate;
        Tags=$tags;
        #Attributes=$attributes
    } | ConvertTo-Json
   
    # Now save the data.
    $kbCreateUri = $apiBaseUri + "api/" + $cpAppId + "/knowledgebase/"
    $kbSaveSuccessful = $true
    Write-Log -level INFO -string "Saving KB with subject `"$($snowKb.Title)`"."

    $kbData = try {
        Invoke-RestMethod -Method Post -Headers $apiHeaders -Uri $kbCreateUri -Body $newKbJson -ContentType "application/json; charset=utf-8"        
    } catch {

		# Display errors and exit script.
		Write-Log -level ERROR -string "Error saving KB with subject `"$($snowKb.Title)`":"
		Write-Log -level ERROR -string ("Status Code - " + $_.Exception.Response.StatusCode.value__)
		Write-Log -level ERROR -string ("Status Description - " + $_.Exception.Response.StatusDescription)
		Write-Log -level ERROR -string ("Error Message - " + $_.ErrorDetails.Message)
        Write-Log -level INFO -string " "
        $kbSaveSuccessful = $false
                
    }

    # Return whether or not the save was successful.
    return $kbSaveSuccessful

}

#endregion

Write-Log -level INFO -string $processingLoopSeparator
Write-Log -level INFO -string "Importing process starting."
Write-Log -level INFO -string "Processing file $($fileLocation)."
Write-Log -level INFO -string " "

# Validate that the file location.
if (-Not ($fileLocation | Test-Path)) {
	
	Write-Log -level ERROR -string "The specified file location is invalid."
	Write-Log -level INFO -string " "
	Write-Log -level INFO -string "Exiting."
	Write-Log -level INFO -string $processingLoopSeparator
	Exit(1)
	
}

# Validate that category ID is greater than 0.
if ($categoryId -le 0) {

    Write-Log -level ERROR -string "The specified category ID is invalid. Category ID must be greater than zero."
	Write-Log -level INFO -string " "
	Write-Log -level INFO -string "Exiting."
	Write-Log -level INFO -string $processingLoopSeparator
    Exit(1)
    
}

# Get the KB data from the JSON. The data is nested under a single records property.
# Strip out weird \r\n from the text content.
$kbs = @((Get-Content -Raw -Path $fileLocation | ConvertFrom-Json))
$kbCount = $kbs.length

# Exit out if no data is found to import.
if($kbCount -le 0) {
	
	Write-Log -level INFO -string "No items detected for processing."
	Write-Log -level INFO -string " "
	Write-Log -level INFO -string "Exiting."
	Write-Log -level INFO -string $processingLoopSeparator
	Exit(0)
	
}

# We found data. Proceed.
Write-Log -level INFO -string "Found $($kbCount) KB(s) to import."

# Authenticate to the API with user creds and get an auth token. 
#	If API authentication fails, display error and exit.
#	If API authentication succeeds, store the token in a Headers object.
Write-Log -level INFO -string "Authenticating to the TeamDynamix Web API with a base URL of $($apiBaseUri)."
$apiHeaders = ApiAuthenticateAndBuildAuthHeaders -apiBaseUri $apiBaseUri -apiWSBeid $apiWSBeid -apiWSKey $apiWSKey

# Now get all users for the BE.
Write-Log -level INFO -string "Retrieving all user data for the organization (for owner matching) from the TeamDynamix Web API."
$userData = RetrieveAllUsersForOrganization -apiHeaders $apiHeaders -apiBaseUri $apiBaseUri
$userCount = 0
if($userData -and $userData.length -gt 0) {
    $userCount = $userData.length
}
Write-Log -level INFO -string "Found $($userCount) user(s) for this organization."

# Initialize an already found user UIDs data array.
$foundUserUids = @()

# Loop through the KBs and save them.
Write-Log -level INFO -string "Starting KB import."
$successCount = 0
$failedCount = 0
$failedKbs = @()
ForEach ($kb in $kbs) {
    
    # Log the KB we are on.
    Write-Log -level INFO -string "Processing KB with subject `"$($kb.Title)`"."

    # Attempt the save.
    $kbSaveSuccessful = SaveKbArticle -snowKb $kb

    # If we were successful, log a message and increment the success counter.
    if($kbSaveSuccessful) {
        
        Write-Log -level INFO -string "KB saved successfully."
        $successCount += 1

    } else {
        
        # For KBs which failed to save, store these and increment the failed count.
        $failedCount += 1
        $failedKbs += $kb

    }

    # Wait 1 second to respect rate limits.
    Start-Sleep -m 1000

}

# If we had KBs which failed to save, store those in a new JSON file.
if($failedCount -gt 0) {
    
    # Convert the failed KB collection to a JSON string. Force a JSON collection
    # even if the PS collection only has one item.
    $failedKbJson = $failedKbs | ConvertTo-Json -Depth 100
    if($failedCount -eq 1) {
        $failedKbJson = ConvertTo-Json -InputObject $failedKbs -Depth 100
    }

    # Save the file to "[script path]\[original file name (sans extension)]-failed-yyyyMMddhhss.json".
    $saveLocation = $scriptPath + "\" + $fileLocation.Name.Replace(".json", "-failed-" + (Get-Date).ToString("yyyyMMddhhmmss") + ".json")
    $failedKbJson | Out-File $saveLocation

}

Write-Log -level INFO -string "Processing complete."
Write-Log -level INFO -string "Successfully saved $($successCount) out of $($kbCount) article(s)."
Write-Log -level INFO -string $processingLoopSeparator