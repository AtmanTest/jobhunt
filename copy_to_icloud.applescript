tell application "Finder"
	try
		set sourceFile to POSIX file "/Users/jahangir/jobhunt/jobhunt-postman.json"
		set targetFolder to (path to iCloud Drive) as text
		if exists folder targetFolder then
			set destFolder to (targetFolder & "TEST API") as text
			if not (exists folder destFolder) then
				make new folder at targetFolder with properties {name:"TEST API"}
			end if
			duplicate sourceFile to folder destFolder with replacing
			return "OK: copied to iCloud Drive"
		else
			return "ERROR: iCloud Drive folder not found"
		end if
	on error errMsg
		return "ERROR: " & errMsg
	end try
end tell
