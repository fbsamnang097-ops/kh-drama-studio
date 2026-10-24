param([Parameter(Mandatory=$true)][string]$Version, [string]$Message = "release")
[System.IO.File]::WriteAllText("$PWD\VERSION", "$Version`n", (New-Object System.Text.UTF8Encoding $false))
node -e "const fs=require('fs');const p=JSON.parse(fs.readFileSync('package.json','utf8').replace(/^\uFEFF/,''));p.version=process.argv[1];fs.writeFileSync('package.json',JSON.stringify(p,null,2)+'\n')" $Version
git add -u
git commit -m "$Message"
git pull --rebase origin main
git push origin main
git tag "v$Version"
git push origin "v$Version"